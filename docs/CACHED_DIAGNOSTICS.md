# Optional cached diagnostics — 0.3.0rc2

Base: `289c5492c7afc9331324195afb36b0c7e4cd7159` (published rc1 runtime).

`Stove.cached_diagnostics` is a synchronous read-only property returning a new
plain dictionary. It is empty before the first successful `get_data()` and never
performs I/O. Only `remote_refill_beeps` (non-negative JSON integer, excluding
booleans) and `wifi_version` (three non-negative integer components joined with
literal dots) can appear. Strings, floats, booleans, negative values and partial
version triplets are omitted, not coerced. Integer-to-string conversion limits
cannot turn valid legacy status into a parsing failure. No protocol upper bound
or default count/version is invented.

The existing status request and all 25 returned keys, order, types and values
remain unchanged. The cache is replaced atomically after successful legacy
parsing: missing/malformed optional fields remove old values. Failed, invalid or
cancelled reads retain the last successful snapshot, which is not a freshness
claim. There is no cache timestamp, retry, request or effect on commands. Separate
clients and returned copies cannot modify another snapshot. `get_raw_data()`
retains its old behavior and does not populate this processed diagnostics cache.

No door or service-date field enters this accessor. Door presence on firmware
3.34.0 was reported by the user; transition semantics remain unvalidated. A
third-party fixture contains service_date `2023-09-26`, parsed as YYYY-MM-DD and
labelled last maintenance; no firmware-defined meaning or sentinel contract is
established. Neither field is newly exposed by this change.

The artifact guard removes only both cache methods and the one post-parse call,
then verifies the exact rc1 runtime bytes and every historical scope guard.
Existing 25-key literal-baseline tests remain unchanged. Dedicated tests cover
copy isolation, replacement/clearing, malformed values, read failure/cancellation,
request counts and network denial. Installed-wheel tests include these cases.

A separate hwam_stove rc2 artifact gate consumes only this property for O01.
The existing rc1 publish workflow remains pinned to rc1 and cannot publish rc2.
Publication of rc2 needs separate approval and an artifact-pinned preflight.
