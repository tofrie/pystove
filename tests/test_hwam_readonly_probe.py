"""Diagnostic-only tests. All responses/sockets are simulated; no hardware I/O."""

import asyncio
import http.client
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from diagnostics import hwam_readonly_probe as diag
from pystove import pystove as runtime

SECRET = "PRIVATE-PERSON-SSID-TOKEN"
STATUS = {"version_major": 7, "version_minor": 2, "version_build": 123,
          "remote_version_major": 1, "remote_version_minor": 4,
          "remote_version_build": 56, "phase": 5}


class Response:
    def __init__(self, body=b"{}", *, status=200, headers=None, error=None):
        self.body = body
        self.status = status
        self.version = 11
        self.headers = {"Content-Type": "application/json"} | (headers or {})
        self.error = error
        self.closed = False
        self.read_sizes = []

    def getheader(self, key, default=None):
        return self.headers.get(key, default)

    def read1(self, size):
        self.read_sizes.append(size)
        if self.error:
            raise self.error
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk

    def close(self):
        self.closed = True


@pytest.fixture
def transport(monkeypatch):
    state = SimpleNamespace(responses=[], connections=[], calls=[], fail_at=None,
                            error=None)

    class Connection:
        def __init__(self, host, port, timeout):
            self.closed = False
            state.connections.append(self)
            self.response = state.responses.pop(0) if state.responses else Response()

        def request(self, *args, **kwargs):
            state.calls.append((args, kwargs))
            if state.fail_at == "request":
                raise state.error

        def getresponse(self):
            if state.fail_at == "headers":
                raise state.error
            return self.response

        def close(self):
            self.closed = True

    monkeypatch.setattr(diag.http.client, "HTTPConnection", Connection)
    return state


def test_only_two_existing_safe_reads_and_no_library_initialization(transport):
    report = diag.probe("stove.test")
    assert diag.READS == (
        ("identification", runtime.STOVE_ID_URL), ("status", runtime.STOVE_DATA_URL)
    )
    assert [args for args, _ in transport.calls] == [
        ("GET", "/esp/get_identification"), ("GET", "/get_stove_data")
    ]
    for _, kwargs in transport.calls:
        assert kwargs == {"headers": {"Accept": "application/json",
                          "Accept-Encoding": "identity", "Connection": "close"}}
    assert all(conn.closed and conn.response.closed for conn in transport.connections)
    assert report["mutating_requests_sent"] == 0
    assert report["automatic_retries"] == 0
    assert report["model_series"]["value"] is None


@pytest.mark.parametrize("mode", ["mutating", "write", "commands", "start", "POST"])
def test_other_modes_refused_before_connection(transport, mode):
    with pytest.raises(diag.ProbeRefused):
        diag.probe("stove.test", mode=mode)
    assert not transport.connections


@pytest.mark.parametrize("path", [
    "/start", "/set_burn_level", "/set_night_lowering_on",
    "/set_night_lowering_off", "/set_night_time", "/set_remote_refill_alarm",
    "/set_time", "/start_selftest", "/get_selftest_result", "/open_file",
    "/read_open_file", "/delete_file", "/esp/get_current_accesspoint",
    "/get_stove_data?command=start", "http://stove.test/start",
])
def test_non_allowlisted_requests_refused_before_connection(transport, path):
    with pytest.raises(diag.ProbeRefused):
        diag.read_once("stove.test", 80, 10, "status", path)
    assert not transport.connections


@pytest.mark.parametrize("host", [
    "http://stove.test", "stove.test/start", "user:password@stove.test",
    "stove.test?command=start", "stove.test\r\nInjected: value", "",
    "stove.test:80", "stove.test#start", "fe80::1%en0", "stove test",
])
def test_host_cannot_inject_commands_or_credentials(transport, host):
    with pytest.raises(diag.ProbeRefused):
        diag.probe(host)
    assert not transport.connections


@pytest.mark.parametrize("kwargs", [
    {"port": 0}, {"port": 65536}, {"port": True}, {"timeout": 0},
    {"timeout": -1}, {"timeout": 61}, {"timeout": float("inf")},
    {"timeout": float("nan")}, {"timeout": True},
])
def test_invalid_configuration_cannot_connect(transport, kwargs):
    with pytest.raises(diag.ProbeRefused):
        diag.probe("stove.test", **kwargs)
    assert not transport.connections


@pytest.mark.parametrize("argv", [
    ["--mode", "mutating"], ["--command", "start"], ["--path", "/start"],
    ["--method", "POST"], ["--body", SECRET], ["--output", SECRET],
    ["--timeout", SECRET], ["--port", SECRET], ["--mode", SECRET],
])
def test_cli_refuses_modes_and_arbitrary_requests_without_echo(transport, capsys, argv):
    assert diag.main(["--host", "stove.test", *argv]) == 2
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err
    assert json.loads(output.out)["error"] == "probe_refused"
    assert not transport.connections


@pytest.mark.parametrize("stage", ["request", "headers", "body"])
@pytest.mark.parametrize("error", [
    TimeoutError(SECRET), ConnectionResetError(SECRET),
    http.client.RemoteDisconnected(SECRET), http.client.BadStatusLine(SECRET),
    http.client.IncompleteRead(b"PRIVATE-PERSON-SSID-TOKEN"),
])
def test_errors_close_connections_and_never_repeat_endpoint(transport, stage, error):
    if stage == "body":
        response = Response(error=error)
        transport.responses.append(response)
    else:
        transport.fail_at, transport.error = stage, error
    report = diag.probe("stove.test")
    assert len(transport.connections) == 2
    assert len(transport.calls) == 2
    assert len({args[1] for args, _ in transport.calls}) == 2
    assert all(conn.closed for conn in transport.connections)
    if stage == "body":
        assert response.closed
    assert report["requests"][0]["error"] in ("timeout", "transport_or_http_error")
    assert SECRET not in json.dumps(report)


@pytest.mark.parametrize("stage", ["request", "headers", "body"])
@pytest.mark.parametrize("error", [KeyboardInterrupt(), asyncio.CancelledError(),
                                   RuntimeError(SECRET)])
def test_cancellation_and_unexpected_failure_unwind_before_next_read(
    transport, stage, error
):
    if stage == "body":
        response = Response(error=error)
        transport.responses.append(response)
    else:
        transport.fail_at, transport.error = stage, error
    with pytest.raises(type(error)):
        diag.probe("stove.test")
    assert len(transport.calls) == len(transport.connections) == 1
    assert transport.connections[0].closed
    if stage == "body":
        assert response.closed


@pytest.mark.parametrize(("error", "exit_code", "message"), [
    (KeyboardInterrupt(), 130, "cancelled"),
    (RuntimeError(SECRET), 1, "diagnostic_failed"),
])
def test_cli_cancellation_and_failure_are_redacted(
    transport, capsys, error, exit_code, message
):
    transport.responses.append(Response(error=error))
    assert diag.main(["--host", "private-host.test"]) == exit_code
    captured = capsys.readouterr()
    assert json.loads(captured.out)["error"] == message
    assert not captured.err
    assert SECRET not in captured.out and "private-host" not in captured.out
    assert transport.connections[0].closed


def test_report_records_only_selected_values_and_structures(transport, capsys, caplog):
    identity = {"name": SECRET, "ip": "192.0.2.123", "mdns": SECRET, SECRET: SECRET}
    status = STATUS | {"nested": {SECRET: SECRET}, "response": "OK"}
    transport.responses.extend([
        Response(json.dumps(identity).encode(), headers={
            "Content-Type": f"application/json; private={SECRET}",
            "Set-Cookie": SECRET, "Server": SECRET,
        }),
        Response(json.dumps(status).encode(), status=500),
    ])
    assert diag.main(["--host", "private-host.test"]) == 0
    output = capsys.readouterr()
    assert not output.err and not caplog.text
    for private in (SECRET, "192.0.2.123", "private-host.test", "nested"):
        assert private not in output.out
    report = json.loads(output.out)
    assert report["target"] == "redacted"
    identity_row, status_row = report["requests"]
    assert identity_row["content_type"] == "application/json"
    assert identity_row["response_structure"]["known_fields"] == {
        "name": "string", "ip": "string", "mdns": "string"
    }
    structure = status_row["response_structure"]
    assert structure["firmware_version_parts"] == [7, 2, 123]
    assert structure["remote_version_parts"] == [1, 4, 56]
    assert structure["phase"] == {"index": 5, "label": "Standby"}
    assert structure["unknown_field_count"] == 1
    assert report["http_status_evidence"] == {
        "http_ge_400_observed": True,
        "http_ge_400_with_response_ok_observed": True,
        "command_status_semantics": "not_tested",
        "firmware_design_intent": "not_determinable_from_readonly_probe",
    }


def test_target_only_revealed_by_explicit_option(transport):
    report = diag.probe("stove.test", port=8080, show_target=True)
    assert report["target"] == {"host": "stove.test", "port": 8080}


@pytest.mark.parametrize("value", [SECRET, True, -1, 2**50, [], {}, None, 1.5])
def test_version_values_cannot_leak_arbitrary_fields(value):
    result = diag.summarize_body(json.dumps(STATUS | {
        "version_major": value, "remote_version_build": value, "phase": value,
    }).encode(), "status")
    assert result["firmware_version_parts"] is None
    assert result["remote_version_parts"] is None
    assert result["phase"] is None
    assert SECRET not in json.dumps(result)


@pytest.mark.parametrize("body", [
    b"{", b"PRIVATE-PERSON-SSID-TOKEN", b"\xff", b"NaN",
    b"9" * 5000,
], ids=["truncated", "text", "encoding", "non_json_constant", "huge_number"])
def test_invalid_json_never_logged(body):
    assert diag.summarize_body(body, "status") == {"json": "invalid_or_unsupported"}


def test_deep_json_is_bounded_and_never_echoed():
    body = b"[" * 1500 + json.dumps(SECRET).encode() + b"]" * 1500
    result = diag.summarize_body(body, "status")
    # CPython versions differ in their JSON decoder recursion limit.
    assert result["json"] in ("parsed", "invalid_or_unsupported")
    assert SECRET not in json.dumps(result)
    assert len(json.dumps(result)) < 200


@pytest.mark.parametrize("value", [[], [SECRET, {SECRET: SECRET}], SECRET, 42, None])
def test_non_object_json_only_exposes_structure(value):
    result = diag.summarize_body(json.dumps(value).encode(), "status")
    assert result["json"] == "parsed"
    assert SECRET not in json.dumps(result)
    assert "firmware_version_parts" not in result


@pytest.mark.parametrize("status", [200, 204, 301, 302, 307, 308, 400, 404, 500, 503])
def test_http_status_is_observed_without_policy_or_redirects(transport, status):
    transport.responses.append(Response(b'{"response":"OK"}', status=status,
                                        headers={"Location": "/start"}))
    report = diag.probe("stove.test")
    assert report["requests"][0]["http_status"] == status
    assert report["requests"][0]["response_structure"]["response_ok"] is True
    assert len(transport.calls) == 2
    assert report["redirects_followed"] == 0


@pytest.mark.parametrize("status", [401, 403, 407])
def test_access_denial_stops_before_second_read(transport, status):
    transport.responses.append(Response(status=status))
    report = diag.probe("stove.test")
    assert report["authentication_or_access_denied"] is True
    assert len(transport.calls) == 1


def test_response_body_has_a_hard_memory_read_cap(transport):
    response = Response(b"x" * (diag.BODY_LIMIT + 20000))
    transport.responses.append(response)
    row = diag.probe("stove.test")["requests"][0]
    assert row["body_bytes_observed"] == diag.BODY_LIMIT + 1
    assert row["body_state"] == "limit_exceeded" and not row["body_complete"]
    assert row["response_structure"] is None
    assert all(0 < size <= 4096 for size in response.read_sizes)
    assert response.closed


def test_exact_cap_is_complete(transport):
    transport.responses.append(Response(b" " * (diag.BODY_LIMIT - 2) + b"{}"))
    row = diag.probe("stove.test")["requests"][0]
    assert row["body_bytes_observed"] == diag.BODY_LIMIT
    assert row["body_state"] == "complete"


def test_encoded_body_is_bounded_and_not_decompressed(transport):
    transport.responses.append(Response(b"secret", headers={
        "Content-Encoding": "gzip", "Content-Type": f"private/{SECRET}",
    }))
    row = diag.probe("stove.test")["requests"][0]
    assert row["body_state"] == "encoded_not_parsed"
    assert row["response_structure"] is None
    assert row["content_type"] == "other_redacted"


@pytest.mark.parametrize(("header", "expected"), [
    (None, None), ("123", 123), (SECRET, "invalid_or_too_large"),
    ("9" * 10000, "invalid_or_too_large"), ("-1", "invalid_or_too_large"),
])
def test_declared_length_is_bounded_numeric_metadata(header, expected):
    assert diag.declared_length(header) == expected


class ScriptedSocket:
    """Real http.client serialization/parsing, using memory instead of a network."""

    def __init__(self, response):
        self.response = io.BytesIO(response)
        self.sent = bytearray()
        self.closed = False

    def setsockopt(self, *args):
        pass

    def sendall(self, data):
        self.sent.extend(data)

    def makefile(self, *args):
        return self.response

    def close(self):
        self.closed = True


@pytest.mark.parametrize("response", [
    b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}",
    b"HTTP/1.1 302 Found\r\nLocation: /start\r\nContent-Length: 2\r\n\r\n{}",
    b"HTTP/1.1 500 Error\r\nContent-Length: 17\r\n\r\n{\"response\":\"OK\"}",
    b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n{}",
    b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n9\r\nx",
    b"", b"NOT HTTP\r\n",
])
def test_real_http_transport_has_no_retries_redirects_or_extra_wire_requests(
    monkeypatch, response
):
    sockets = []

    def create_connection(*args, **kwargs):
        sock = ScriptedSocket(response)
        sockets.append(sock)
        assert len(sockets) <= 2, "Unexpected retry"
        return sock

    monkeypatch.setattr(http.client.socket, "create_connection", create_connection)
    report = diag.probe("stove.test")
    assert len(sockets) == 2
    for sock, (_, path) in zip(sockets, diag.READS, strict=True):
        assert sock.closed and sock.response.closed
        assert bytes(sock.sent) == (
            f"GET {path} HTTP/1.1\r\nHost: stove.test\r\n"
            "Accept: application/json\r\nAccept-Encoding: identity\r\n"
            "Connection: close\r\n\r\n"
        ).encode()
    assert report["automatic_retries"] == 0
    if b"Content-Length: 100" in response:
        assert report["requests"][0]["body_state"] == "incomplete"


def test_cli_needs_no_installed_library_or_third_party_dependencies(tmp_path):
    script = Path(diag.__file__).resolve()
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(script), "--help"],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert "--host" in result.stdout and "--mode {readonly}" in result.stdout
    assert not result.stderr


def test_body_read_budget_expires_and_closes(transport, monkeypatch):
    clock = iter([0, 0, 0, 11, 11, 11, 11, 11, 11, 11])
    monkeypatch.setattr(diag.time, "monotonic", lambda: next(clock))
    transport.responses.append(Response(b"{}"))
    row = diag.probe("stove.test")["requests"][0]
    assert row["error"] == "timeout"
    assert row["body_bytes_observed"] == 2
    assert not row["body_complete"]
    assert all(conn.closed and conn.response.closed for conn in transport.connections)


def test_cli_does_not_write_files(transport, monkeypatch, capsys):
    def forbid_file(*args, **kwargs):
        raise AssertionError("Unexpected file operation")

    monkeypatch.setattr("builtins.open", forbid_file)
    monkeypatch.setattr("io.open", forbid_file)
    assert diag.main(["--host", "stove.test"]) == 0
    assert json.loads(capsys.readouterr().out)["diagnostic_only"] is True
