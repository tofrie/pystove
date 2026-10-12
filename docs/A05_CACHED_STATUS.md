# A05 cached door status — 0.3.0rc3 (unpublished)

Base: 0ddf5fa413969ff9037b54575a1be46bb91ece04 / saynwerk-pystove 0.3.0rc2.

`Stove.cached_status` is read-only and copy-returning:

- `generation`: per-client monotonic token, incremented before each `get_data`
  attempt and when `destroy` invalidates the client; not a timestamp/request count.
- `valid`: the latest attempted status read finished existing parsing successfully.
- `door_open`: strict JSON boolean, or None for missing/invalid/unknown data.

Initial and pending/failed/cancelled/closed state has valid=False, door_open=None.
An older overlapping read cannot overwrite a newer generation, even when the newer
attempt failed. A successful response with a missing/non-boolean door has
valid=True, door_open=None. No bool coercion or interpretation of integer 0/1.
A property read performs no I/O; no timestamps, raw bodies or identity values are
retained in this snapshot. Existing cached_diagnostics retains its distinct
last-success behavior unchanged.

The get_data return mapping remains exactly 25 keys and existing types/values.
Status parsing and HTTP request construction are unchanged. Only the existing
/get_stove_data response feeds the added cache; there is no polling, new request,
retry, door command or actual-refill inference. A completed observation is not
continuous sensing: transitions between polls can be missed.

Python 3.14 focused tests cover types, copy isolation, equal public results with
changing door, errors/cancellation, overlaps and destroy invalidation. The existing
full single-version suite and installed-wheel contract tests are also run. Six
known library xfails remain deferred. The package validator reverses only these
additions to recover the exact rc2 source and then validates all older frozen
protocol/lifecycle scopes. No multi-version matrix is asserted for this phase.

No PyPI upload is authorized here. The rc2 publishing workflow is intentionally
unchanged and is not prepared to publish rc3. A later publication needs separate
artifact approval and publishing-workflow preparation.
