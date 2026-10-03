"""Standalone, diagnostic-only HWAM reads. No pystove imports or commands.

Run with Python 3.11+; only the standard library is required. Responses are
summarized in memory, never saved. Ctrl-C unwinds the connection context before
the CLI emits a redacted cancellation report. This is a synchronous CLI, not an
async library API. HTTP status codes are observations, never a success policy.
"""

import argparse
from collections import Counter
from contextlib import closing
import http.client
import ipaddress
import json
import math
import re
import sys
import time

BASE_COMMIT = "fcb7e8ac46b1cc5d73de7c5879e49073aa21769b"
BODY_LIMIT = 65536
READS = (("identification", "/esp/get_identification"),
         ("status", "/get_stove_data"))
VERSION_KEYS = ("version_major", "version_minor", "version_build")
REMOTE_KEYS = tuple("remote_" + key for key in VERSION_KEYS)
IDENTITY_KEYS = ("name", "ip", "mdns")
KNOWN_KEYS = (*IDENTITY_KEYS, *VERSION_KEYS, *REMOTE_KEYS, "phase", "response")
PHASES = ("Ignition", "Burn", "Burn", "Burn", "Glow", "Standby")
CONTENT_TYPES = frozenset({"application/json", "text/plain", "text/html",
                           "application/xml", "text/xml",
                           "application/octet-stream"})


class ProbeRefused(ValueError):
    """Invalid configuration or any request outside the fixed read allowlist."""


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's normal error includes supplied arguments, potentially secrets.
        raise ProbeRefused("Invalid arguments; use --help.")


def validate_target(host, port, timeout, mode):
    """Accept only a bare host; no URL, userinfo, query, path or custom command."""
    if mode != "readonly":
        raise ProbeRefused("Only readonly mode exists.")
    if not isinstance(host, str) or not host or len(host) > 253:
        raise ProbeRefused("A bare host is required.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not all(
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", part)
            for part in host.rstrip(".").split(".")
        ):
            raise ProbeRefused("Invalid bare host.") from None
    # IPv6 zone identifiers are deliberately not supported by this probe.
    if "%" in host:
        raise ProbeRefused("Scoped addresses are not supported.")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ProbeRefused("Invalid port.")
    if (
        type(timeout) not in (int, float)
        or not math.isfinite(timeout)
        or not 0 < timeout <= 60
    ):
        raise ProbeRefused("Timeout must be finite and between 0 and 60 seconds.")


def json_kind(value):
    for cls, label in ((dict, "object"), (list, "array"), (str, "string"),
                       (bool, "boolean"), (int, "number"), (float, "number")):
        if type(value) is cls:
            return label
    return "null"


def version_parts(value, keys):
    parts = [value.get(key) for key in keys]
    if all(type(part) is int and 0 <= part <= 2147483647 for part in parts):
        return parts
    return None


def reject_constant(value):
    raise ValueError("Non-JSON constant")


def summarize_body(body, category):
    """Emit only types, counts and tightly selected protocol values, never text."""
    try:
        value = json.loads(body, parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        return {"json": "invalid_or_unsupported"}
    result = {"json": "parsed", "root_type": json_kind(value)}
    if isinstance(value, dict | list):
        items = value.values() if isinstance(value, dict) else value
        result["member_count"] = len(value)
        result["value_types"] = dict(sorted(Counter(map(json_kind, items)).items()))
    if not isinstance(value, dict):
        return result
    result["known_fields"] = {
        key: json_kind(value[key]) for key in KNOWN_KEYS if key in value
    }
    result["unknown_field_count"] = sum(key not in KNOWN_KEYS for key in value)
    result["response_ok"] = value.get("response") == "OK" if (
        "response" in value
    ) else None
    if category == "status":
        result["firmware_version_parts"] = version_parts(value, VERSION_KEYS)
        result["remote_version_parts"] = version_parts(value, REMOTE_KEYS)
        phase = value.get("phase")
        result["phase"] = (
            {"index": phase, "label": PHASES[phase]}
            if type(phase) is int and 0 <= phase < len(PHASES) else None
        )
    if category == "identification":
        result["identity_values"] = "redacted"
    return result


def content_type(header):
    if header is None:
        return "absent"
    media_type = header.split(";", 1)[0].strip().lower()
    return media_type if media_type in CONTENT_TYPES else "other_redacted"


def declared_length(header):
    if header is None:
        return None
    if re.fullmatch(r"[0-9]{1,19}", header) and int(header) <= 2**63 - 1:
        return int(header)
    return "invalid_or_too_large"


def read_once(host, port, timeout, category, path):
    """Exactly one GET to a literal allowlisted path; close on every exit.

    http.client performs neither redirect following nor HTTP request retries.
    A fresh connection per read avoids pooled-connection retry behavior. The
    transport does not use proxies, cookies, netrc, authentication or pystove.
    """
    if (category, path) not in READS:
        raise ProbeRefused("Request outside the readonly allowlist.")
    row = {"method": "GET", "endpoint_category": category, "endpoint": path,
           "http_status": None, "response_structure": None,
           "body_bytes_observed": 0, "body_complete": False}
    started = time.monotonic()
    try:
        with closing(http.client.HTTPConnection(host, port, timeout=timeout)) as conn:
            conn.request("GET", path, headers={"Accept": "application/json",
                         "Accept-Encoding": "identity", "Connection": "close"})
            with closing(conn.getresponse()) as response:
                row["http_status"] = response.status
                row["http_version"] = {10: "1.0", 11: "1.1"}.get(
                    response.version, "other"
                )
                row["content_type"] = content_type(response.getheader("Content-Type"))
                row["content_length_declared"] = declared_length(
                    response.getheader("Content-Length")
                )
                encoding = response.getheader("Content-Encoding", "identity").lower()
                row["content_encoding"] = (
                    "identity" if encoding == "identity" else "other_redacted"
                )
                body = bytearray()
                deadline = time.monotonic() + timeout
                while len(body) <= BODY_LIMIT:
                    if time.monotonic() >= deadline:
                        raise TimeoutError
                    chunk = response.read1(min(4096, BODY_LIMIT + 1 - len(body)))
                    if not chunk:
                        row["body_complete"] = True
                        break
                    body.extend(chunk)
                    row["body_bytes_observed"] = len(body)
                if not row["body_complete"]:
                    row["body_state"] = "limit_exceeded"
                elif isinstance(row["content_length_declared"], int) and (
                    len(body) != row["content_length_declared"]
                ):
                    row["body_complete"] = False
                    row["body_state"] = "incomplete"
                elif encoding != "identity":
                    row["body_state"] = "encoded_not_parsed"
                else:
                    row["body_state"] = "complete"
                    row["response_structure"] = summarize_body(body, category)
                # No HTTP status is rejected or interpreted as command success.
    except TimeoutError:
        row["error"] = "timeout"
    except (OSError, http.client.HTTPException):
        row["error"] = "transport_or_http_error"
    finally:
        row["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    return row


def probe(host, *, port=80, timeout=10, mode="readonly", show_target=False):
    validate_target(host, port, timeout, mode)
    # All configuration validation precedes the first connection. No generic
    # method, path, payload or mutating mode can be supplied through the CLI.
    requests = []
    for category, path in READS:
        row = read_once(host, port, timeout, category, path)
        requests.append(row)
        if row["http_status"] in (401, 403, 407):
            break  # Authentication/access denial: report, never try credentials.
    statuses = [row["http_status"] for row in requests]
    return {
        "schema_version": 1, "diagnostic_only": True, "mode": "readonly",
        "base_commit": BASE_COMMIT,
        "target": {"host": host, "port": port} if show_target else "redacted",
        "http_reachable": any(status is not None for status in statuses),
        "authentication_or_access_denied": any(
            status in (401, 403, 407) for status in statuses
        ),
        "mutating_requests_sent": 0, "automatic_retries": 0,
        "redirects_followed": 0, "requests": requests,
        "model_series": {"value": None,
                         "reason": "known_path_requires_controller_file_open"},
        "http_status_evidence": {
            "http_ge_400_observed": any(
                status is not None and status >= 400 for status in statuses
            ),
            "http_ge_400_with_response_ok_observed": any(
                row["http_status"] is not None and row["http_status"] >= 400
                and (row["response_structure"] or {}).get("response_ok") is True
                for row in requests
            ),
            "command_status_semantics": "not_tested",
            "firmware_design_intent": "not_determinable_from_readonly_probe",
        },
    }


def main(argv=None):
    parser = SafeParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--host", required=True, help="Bare local HWAM IP or hostname")
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--timeout", type=float, default=10,
                        help="Diagnostic socket timeout/body budget in seconds (0,60]")
    parser.add_argument("--mode", default="readonly", choices=["readonly"])
    parser.add_argument("--show-target", action="store_true",
                        help="Opt in to printing the supplied host and port")
    try:
        args = parser.parse_args(argv)
        report = probe(**vars(args))
    except ProbeRefused:
        print(json.dumps({"error": "probe_refused", "hint": "Use --help."}))
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"error": "cancelled", "connections_closed": True}))
        return 130
    except Exception:
        # Never print an exception/reason string, traceback, URL or raw response.
        print(json.dumps({"error": "diagnostic_failed"}))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if (
        not report["authentication_or_access_denied"]
        and all(row.get("body_state") == "complete" for row in report["requests"])
    ) else 1


if __name__ == "__main__":
    sys.exit(main())
