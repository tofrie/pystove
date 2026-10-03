# Baseline development checks

The compatibility reference is published `pystove==0.3a1`, Git commit
`6d2f7844d3fa49a339820c446aa47ba29e60e94a`. This branch identifies itself as
`0.3a2.dev0`; it does not adopt the incompatible runtime changes from `master`.
The exact public contract is recorded in [BASELINE.md](BASELINE.md).

## Supported check matrix

CI checks Python 3.11, 3.12 and 3.13. Python 3.11 matches the repository's existing
development-tool target, Python 3.12 matches its existing devcontainer, and Python
3.13 covers the newer Home Assistant interpreter generation. This is the initial
tested development matrix, not a new runtime `Requires-Python` restriction.
Older Python versions have not been certified by these checks. The pinned build
backend itself requires Python 3.10 or newer.

## Development environment

Use a separate environment, not the production Home Assistant environment:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install --requirement requirements-dev.txt
python -m pip install --no-build-isolation --editable .
```

`requirements-dev.txt` pins development tools and their regular dependencies for
the check matrix. Ruff deliberately remains at the baseline hook's version
`0.6.9`. `requirements.txt` and package metadata retain the unbounded runtime
requirement `aiohttp`. No runtime constraints or dependency upgrades are part of
this phase. An already installed compatible aiohttp is reused by pip; the
unbounded runtime graph can differ between newly created environments.

## Required checks

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest
python -m ruff check .
python -m build
python ci/validate_package.py --dist-dir dist
python ci/check_isolated_build.py
python ci/test_wheel.py --dist-dir dist
```

The ordinary build creates an sdist and then builds the wheel from that sdist,
using an isolated backend. Archive validation checks package metadata, the
reviewed runtime sources, wheel RECORD hashes and the sdist's required files.
The separate isolated check prepares metadata and builds artifacts while proving
that aiohttp is absent from the build environment. It does not install the
package's runtime requirements there.

The wheel check installs the built wheel without dependency resolution into a
temporary environment, copies the tests outside the checkout, checks the import
location and runs the compatibility and known-failure tests. It uses the existing
runtime dependency environment and installs the pinned development tools. It
does not contact a stove.

For an offline build, download the pinned tools once into a temporary wheelhouse
and set `PIP_NO_INDEX=1` and `PIP_FIND_LINKS` to its absolute path. Pass the same
path as `--wheelhouse` to `ci/test_wheel.py`. No wheelhouse or local runtime
dependency snapshot is committed.

## Preserve contracts and separate known failures

`test_contract_api.py` and `test_contract_commands.py` assert behavior that must
remain compatible: public imports and constants, signatures, lifecycle, the
25-key processed dataset, legacy strings and alarm lists, integer truncation,
datetime/time/timedelta values, HTTP methods, endpoints and exact compact JSON
payloads. `tests/fixtures/hwam_contract.json` records the symbols referenced by
Home Assistant commit `2176600eece1c644f594a9608186bf395bb2488b` and the hashes
of the read-only reference sources.

`test_known_failures.py` describes desired later corrections with strict expected
failures, each linked to its audit finding. An unexpected pass fails the suite;
it must not silently convert a defect into part of the required compatibility
contract. The tests use synthetic responses, not captured hardware fixtures.

`ci/compatibility_baseline.json` retains the baseline commit, original distribution
hashes, all original runtime hashes and the historical H3 approval. The separate
H4 approval pins the reviewed `pystove.py` hash and an independent H3-base byte
hash outside `get_data()`'s body. H3 cleanup, module imports, signatures, constants,
transport and every other method remain frozen by that historical approval.
The H6 approval separately pins the complete H4 source: only its new parser and
four exact response return expressions may differ. Request construction remains
byte for byte unchanged, including inside those four setters. `__init__.py` and the CLI remain
byte for byte unchanged; the development version remains `0.3a2.dev0`.

`test_status_validation.py` includes the original 0.3a1 `get_data()` source as a
SHA-256-checked literal. Its valid-fixture comparisons check each of the 25 keys,
values and exact types, including successful legacy edge cases. All 29 H3
regressions remain; the eleven former H4 expected failures now assert `None`.
After the H6 POST response follow-up, two more cases are regular regressions;
the remaining nine strict expected failures are unchanged.

Ruff only checks files. The narrow CLI suppressions preserve existing import and
string-formatting style without excluding the CLI from other lint rules. The
optional pre-commit configuration also only checks; auto-fix, formatting and
pyupgrade hooks are not installed. New test/build files receive the normal rules.

## Phase boundary

The runtime fixes after Phase 1 are H3 initialization cleanup, H4 status input
validation and H6 POST response JSON validation. H4 changes only `get_data()`
failure handling; its successful conversions remain compatible. H6 changes only
malformed/non-object confirmations for four POST setters. No network, timeout,
retry, protocol, HTTP-status, live-data, self-test or file-operation defects are fixed. Runtime dependencies and
the HA integration remain unchanged. Exact validation, logging and limitations
are recorded in [BASELINE.md](BASELINE.md#h4-follow-up). The workflow contains no
publishing, deployment or secret-dependent steps. H3/H4 and the narrow H6 parser scope are checked without
hardware; later communication changes still need the hardware gates from the audit.


The H6 checks are in `tests/test_post_response_validation.py` and run against the
installed wheel too. `tests/fixtures/h4_commands.json` preserves the six H4
command methods with a pinned fixture hash for direct comparisons. See
[H6 POST response follow-up](BASELINE.md#h6-post-response-follow-up) for exact
failure semantics and scope. No new runtime dependency is required.
