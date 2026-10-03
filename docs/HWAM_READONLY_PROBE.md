# Diagnostic HWAM read-only probe

Base: `fcb7e8ac46b1cc5d73de7c5879e49073aa21769b`, library version
`0.3a2.dev0`. This is a standalone diagnostic, outside `pystove`. It neither
imports nor initializes the library, changes its API, installs a CLI entry
point, nor establishes an HTTP-status policy. The six existing xfails remain
unchanged. The script and tests ship in the source archive, not the library wheel.

## First local run

Use Python 3.11 or newer, on your own computer in the controller's local network.
No installation, Home Assistant changes, extra packages or credentials are needed.
From the repository root, replace the host placeholder with the known controller
address (a bare IP or hostname, without `http://`, credentials or a path):

```sh
python3 diagnostics/hwam_readonly_probe.py --host 'HWAM-IP-ODER-HOST'
```

Run once and return the printed JSON report. **STOP after this read-only run.**
Do not invoke the normal `pystove_cli.py` for this experiment: factory
initialization includes controller file operations. The diagnostic offers no
command mode, file operations, automatic scheduling, retries or output-file flag.

Optional parameters:

- `--port 80`: only change if the known controller uses another HTTP port.
- `--timeout 10`: diagnostic socket timeout and body-read time budget, greater
  than zero and at most 60 seconds. This does not change library timeout behavior.
  DNS resolution and header reads are not governed by a total wall-clock deadline;
  an in-progress body socket read can exceed the body budget by one socket timeout.
- `--show-target`: explicitly include the supplied host/port in the report.
  The default redacts both. Response identity values remain redacted even with
  this option. Review the report before sharing it.
- `--mode readonly`: the only accepted mode and already the default. Any other
  mode, method, command, path, payload or output-file argument is rejected before
  opening a connection.

Ctrl-C closes owned responses/connections and exits 130 with a small redacted
cancellation record. This is a synchronous CLI; no asyncio task or background
thread is left running. Exit 2 means refused arguments. Exit 1 means an
incomplete/unsupported exchange, transport failure or access denial. Exit 0 means
the HTTP exchanges were fully captured, **not** that the stove accepted a command,
the bodies were valid status objects, or all status codes were 2xx.

If a response is 401, 403 or 407, the probe stops before the next endpoint. It
never prompts for or retries credentials. Report that outcome and verify the
correct local controller address/access configuration before a separate run.
Redirects, including login redirects, are recorded but never followed.

## Fixed request inventory

| Order | Method | Path | Category | Existing source |
| --- | --- | --- | --- | --- |
| 1 | GET | `/esp/get_identification` | identification | `STOVE_ID_URL`, `_identify.get_identification` |
| 2 | GET | `/get_stove_data` | status | `STOVE_DATA_URL`, `get_raw_data` / `get_data` |

At most one request per listed path is attempted. A failure on one read is not
retried; the other distinct read is still attempted unless cancelled, denied
access, or terminated by an unexpected internal failure. Each request has a new
HTTP connection. Python's standard-library `http.client` sends no automatic HTTP
request retries and follows no redirects. There is no configurable HTTP method
or endpoint; the low-level reader independently rejects non-allowlisted paths.
No request body is sent. The diagnostic sends `Accept: application/json`,
`Accept-Encoding: identity`, and `Connection: close`. It uses no environment
proxy, cookies, authentication, netrc, or shared application session.

These are the existing ordinary read paths, not a newly inferred protocol.
The diagnostic's connection and encoding headers differ from aiohttp defaults;
observations concern these exact requests and this firmware, not every library
exchange. Firmware behavior cannot be guaranteed merely by inspecting client
code. The client-side guarantee is that only these two fixed read requests can
be emitted, with no follow-up request selected from a response.

The probe deliberately excludes access-point discovery (SSID), live data,
self-tests, every setter, `/start`, and all controller file operations. Although
the library opens `info.xml` in mode 1, `/open_file` changes the controller's
current file transaction. Model/series and algorithm identification currently
depend on that path and therefore remain unavailable in this initial probe.
No alternative model endpoint is guessed.

## Report and privacy

The report includes HTTP reachability (any HTTP response, not authenticated HWAM
identity), method, fixed path/category, HTTP version/status, sanitized media type,
declared content length, observed body bytes, completeness, elapsed time and
generic error categories. A length is the entity-body bytes read after HTTP
transfer framing, not the entire wire exchange. On interruption/error/size cap,
it is only the observed prefix length. Declared length is untrusted metadata.

At most 65,537 entity-body bytes are read per request: 64 KiB plus one byte to
detect overflow. Oversized/partial bodies are not parsed. Compressed replies are
bounded but not decompressed; their structure is marked unavailable. Missing or
wrong Content-Type does not prevent examining a complete JSON body.

JSON output contains only root type, member count, counts of immediate value
types, types of a fixed set of known fields, and the number of unknown fields.
Unknown keys and all nested/string values are omitted. The only selected values
are nonnegative bounded integer firmware/remote-version components, the known
phase index/label, and whether a top-level `response` equals exactly `OK`.
Unrecognized types/values produce `null`, not speculative conversions. No full
body, body hash, raw error, status reason, arbitrary header, cookie, SSID, stove
name, returned IP, mDNS name or token is printed. Media-type parameters and
unrecognized media types/encodings are redacted. There is no body-saving mode.

Example **synthetic excerpt**, not a hardware measurement:

```json
{
  "target": "redacted",
  "http_reachable": true,
  "mutating_requests_sent": 0,
  "http_status_evidence": {
    "http_ge_400_observed": false,
    "http_ge_400_with_response_ok_observed": false,
    "command_status_semantics": "not_tested",
    "firmware_design_intent": "not_determinable_from_readonly_probe"
  }
}
```

## What this can establish about H6

The two unchanged H6 xfails are
`test_command_rejects_http_error_status[post-command]` (`set_burn_level(3)`)
and `[get-command]` (`start()`) in `tests/test_known_failures.py`.
They inject HTTP 500 with `{"response":"OK"}` and demonstrate that the current
client reports success regardless of status. They are synthetic regression
targets, not proof that any HWAM firmware sends that combination, nor proof of
firmware design intent.

The real read-only run can establish which HTTP codes/content-types/shapes the
two read endpoints actually return. An HTTP >= 400 response with a plausible
status body or `response_ok: true` would be evidence of that specific combination;
it would not prove a command succeeded. Conversely, two normal 200 responses do
not establish conventional status handling for command endpoints. Absence of
`response` on reads means the `OK`/status relationship was not exercised there.
`http_ge_400_with_response_ok_observed: false` means only "not observed", including
when transport failed or the body could not be parsed.

Deliberate independence of `response: OK` from HTTP status requires firmware/vendor
documentation or sufficiently specific command observations. Even successful
command tests cannot prove that no error-path exceptions exist. No status policy
should be inferred from this diagnostic alone. No real controller was contacted
while developing or testing this tool.

## Separate manual command-test plan — NOT AUTHORIZED FOR EXECUTION HERE

Only consider this after evaluating the read-only report. The diagnostic cannot
execute this plan. No ready-to-run mutating shell command is supplied. Any later
test needs its own explicit authorization and one-shot capture mechanism, with
redirects/retries disabled, before the owner performs a locally supervised action.
Do not induce HTTP 500, send malformed commands, reset the controller, or interrupt
a burn to manufacture an error response.

For each request, capture method/path category, exact approved payload, HTTP
status, sanitized Content-Type, declared/observed body lengths, completeness and
the top-level `response == "OK"` observation, plus a local before/after state
check. Preserve selected safe values, not full bodies. If the reply is lost,
first inspect the local controller state; **never repeat the command to learn
whether it worked**. A restore is a separate explicit manual action with its
own confirmation and capture, never an automatic cleanup request.

### Exact POST xfail: `set_burn_level(3)`

- Wire command: `POST /set_burn_level`, compact body `{"level":3}`. Retain the
  existing command's request serialization/content type when a capture mechanism
  is reviewed; do not silently switch to a different JSON client convention.
- Required pre-state: owner at the controller; model/firmware and current level
  recorded locally; ordinary stable operation permitted by the stove manual,
  no alarm/self-test/update. Choose only a situation where level 3 is a desired,
  permitted adjustment. If already level 3, it is a same-value acknowledgement
  test and supplies no evidence that a setting changed. Do not invent a new
  starting level just to create a test case.
- Expected change: requested level becomes 3. Confirm on the controller and
  through a separate normal status read; an `OK` body alone is not confirmation.
- Restore: record previous level `L` before testing. If a change occurred and
  restoration remains permitted, manually send exactly one separate
  `POST /set_burn_level` with `{"level":L}`, then verify locally. `L` is the
  recorded supported integer, not a guessed default. Stop if the state is uncertain.
- Risk: the selected level may influence combustion/output; controller response
  loss leaves the setting uncertain. This is not an unconditionally safe or
  consequence-free experiment. Defer unless the owner can make that normal
  adjustment safely under the manufacturer's operating instructions.

### Exact GET xfail: `start()`

- Wire command: `GET /start`, no payload. It is state-changing despite GET.
- Required pre-state: the owner is about to perform an independently planned,
  normal ignition, with the stove ready according to its manual, in the expected
  standby state, and physically supervised. No test on an active burn, fault,
  update, unknown state or unattended stove.
- Expected change: initiation of the ordinary ignition phase. Verify the local
  display and a subsequent normal status read; no automatic second `/start`.
- Restore: **there is no verified reversible restore command in this API**.
  Returning to standby requires the manufacturer's normal supervised operating
  procedure and completion of the normal cycle. Do not add a guessed stop/reset
  request. If immediate restoration is required, this exact test cannot meet
  that condition and must not proceed.
- Risk: actual ignition/combustion control and an effectively irreversible
  transition during the test. Capture only an already intended normal start;
  this phase does not justify an extra ignition solely for diagnostics.

A separately approved reversible GET setting, such as night lowering, could
give evidence about that different endpoint. It would **not** validate `/start`
or resolve the exact GET xfail. Read-only measurements may be enough to rule out
an overly broad proposed policy, but they cannot by themselves close both
command-status defects. Prefer vendor clarification over unnecessary actuation.

## Offline checks

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_hwam_readonly_probe.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest
python -m ruff check .
```

The new tests simulate response objects and also exercise real standard-library
HTTP serialization/parsing with in-memory sockets. No test opens a network socket.
They cover the exact two-request inventory, early refusal of mutating modes and
paths, redirect/credential refusal, disconnects/timeouts without retry, cleanup
on cancellation/failure, body caps, malformed/partial/encoded JSON, sanitized
headers/identity/error output, and independence from installed library packages.
