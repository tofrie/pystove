# Private info.xml close cleanup

Base: `22b75dd8a6fcd680d2ced8747671207e62be790f`, version `0.3a2.dev0`.
This is an offline-tested backport, not a hardware compatibility certification.
No hwam_stove dependency or source changes are included.

## Protocol boundary

Only after the existing open response has passed `success == 1`:

1. `POST /open_file` with `{"file_name":"info.xml","mode":1}` (unchanged).
2. `POST /read_open_file` with that exact same payload (unchanged).
3. One attempted `GET /close_file`, with no body/query and no redirects/retries.
4. The original XML parsing and result assignments, unchanged.

The existing parallel identification GETs are unchanged. The new GET follows
upstream commit `868e3cea0ab3cd035f5526a01321a95445abc6fd`. Its cleanup placement
also covers a raised read error or cancellation, unlike that upstream commit.
No later context manager, `{}` read payload, write/delete API, public constant,
HTTP-status policy, or unrelated transport change is adopted.

An unconfirmed open gets **no speculative close**. The controller might already
have opened the file when the response is lost or cancelled. This ambiguity is
not resolved by this change. Concurrent access by another client, context
lifetime/ownership and firmware-specific close semantics remain undocumented.

## Owned cleanup

The read is wrapped in `try/finally` after confirmed open. The private helper
retains one cleanup task and waits using the Python 3.14-proven `asyncio.wait`
pattern; it never uses `shield`. Repeated caller cancellation interrupts only
completion waits. The task's outcome is always retrieved before ownership ends.
The existing factory drains identification tasks before closing its session.

A read exception/cancellation remains primary. If the read returned normally,
a first cancellation received during close is remembered and re-raised after
cleanup. Later cancellation cannot replace either original outcome. Exceptions
already raised by the read are retained across a later factory cancellation too:
the new finally delays the child's completion, so identification snapshots that
read error before draining children instead of letting the later cancellation
overtake it. Other identification error handling is unchanged. Exceptions
from the close task, including its timeout, are consumed and logged separately.
Successful reading/parsing is retained when only close fails.

The close attempt has a private five-second deadline covering session setup,
request/body consumption and release. This is a local waiting bound, not an
assumption about firmware latency or proof of controller cleanup. A timeout can
occur after the controller received the request. There is no retry.

## Preventing an implicit GET retry

The tested aiohttp 3.14.3 can internally retry GET after a disconnect, even on a
fresh connection. Changing the main session's retry flag would affect parallel
identification requests. Therefore close uses a short-lived session borrowing
the existing connector, headers and cookie jar with `connector_owner=False`.
Only this close-only session sets aiohttp's private `_retry_connection=False`.
Its disposal never closes the original connector. The original session's retry,
timeout and redirect settings remain unchanged. No extra connection is mandated.

This deliberately localized private aiohttp switch is a dependency compatibility
risk: a future aiohttp change needs revalidation. Tests exercise the actual
aiohttp retry loop with simulated connection failures, not merely a mocked
`get()` call. Dependencies are not repinned in this phase.

No response body is logged by this helper. HTTP status and response body are not
interpreted as a close acknowledgement. An exhausted response proves only that
the request/response completed, not that the firmware released its file context.

## Verification and remaining gate

Tests cover exact payloads and ordering, unconfirmed open, read errors and None,
invalid XML, first/repeated cancellation during read/close, preserved primary
errors, close failure/timeout, borrowed connector ownership, no retries/redirects,
and no pending tasks, loop diagnostics or ResourceWarnings. Network calls are
blocked in the new test module. Installed-wheel tests include this module.
Packaging reconstructs the exact base source and all historical scope hashes.

The six existing strict xfails remain unchanged. Python 3.11, 3.12, 3.13 and
3.14.6 are the required source/build/installed-wheel verification matrix.

The successful wire sequence has changed. The hwam_stove offline migration gate
must be rerun against the new commit/wheel hash. Hardware testing remains blocked
pending a separate controlled authorization; offline tests do not establish
controller file-context safety. No hardware request is part of this work.
