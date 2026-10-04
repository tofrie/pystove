# Saynwerk distribution release gate

Prepared distribution: **saynwerk-pystove 0.3.0rc1**, maintained by Saynwerk.
Import/API: `pystove`, unchanged. Original author: Milan van Nugteren;
original project: <https://github.com/mvn23/pystove>. GPLv3+ and copyright
notices remain intact. Fork: <https://github.com/tofrie/pystove>.

## Immutable runtime reference

Reference: `eec0d60a0120140171a7ef2a5b6c6005da04c51b` (`0.3a2.dev0`).
`ci/release_baseline.json` pins the complete package and CLI source bytes.
`ci/validate_package.py` checks those hashes (normalizing only the version
literal), in addition to the unchanged historical compatibility approvals.
No runtime/protocol changes are part of this release preparation. Runtime
requirements remain only `aiohttp`; there is no dependency on `pystove`.

The candidate passed offline and user-run Stage-A checks on HWAM firmware
3.34.0 / remote 1.2.0, including four sequential library lifecycles and isolated
Home Assistant setup/reload with 40 entities and final cleanup. This evidence
belongs to the unchanged candidate runtime; the renamed artifact is verified
separately offline. It is not new hardware testing of this release artifact.
The production Home Assistant manifest remains `pystove==0.3a1`.

## Exclusive environment requirement

The distributions `pystove` and `saynwerk-pystove` own the same Python files.
**Never install them together.** Pip has no enforceable distribution-conflict
metadata. Uninstalling either after a collision can remove the other's files;
recreate such an environment instead of repairing it in place.

For release verification, create a new virtual environment with no inherited
site-packages. Before installing, run with its Python:

```sh
python -I /path/to/checkout/ci/check_release_install.py --empty
```

Install the locally built wheel (and its aiohttp dependency), then run:

```sh
python -I /path/to/checkout/ci/check_release_install.py \
  --wheel /path/to/saynwerk_pystove-0.3.0rc1-py3-none-any.whl
```

The check rejects original/duplicate distributions, wrong metadata/version,
unmanaged code, extra package files, altered installed bytes and imports from
another location. It verifies wheel and installed metadata/package bytes and
all three module origins. It never imports the shared namespace when the
original distribution is present. This is a release/deployment gate, not a
runtime API change or an automatic uninstall tool.

`ci/test_wheel.py` runs both checks in a fresh venv outside the checkout, installs
only the requested dependencies (never links parent site-packages), then runs
the full runtime contract suite. `--wheelhouse` enables wholly offline runs;
the wheelhouse must contain the dev tools and aiohttp dependency wheels for the
target interpreter/platform. It preserves the parent aiohttp version.

## Required verification

For Python 3.11, 3.12, 3.13 and 3.14.6: full pytest with ResourceWarnings as
errors, Ruff, wheel/sdist build and artifact validation, a separate isolated
build with no runtime dependencies, and installed-wheel contract tests.
`ci/check_test_results.py` requires the exact six strict known xfails and no
other failures/skips; XPASS fails pytest. The deferred cases remain unchanged:
HTTP command status semantics (2), live-data decoding/length (3), self-test
empty-response retry budget (1). No deferred runtime fix is included.

## Publication status

No release, tag, upload, reservation or production dependency change is made.
On 2026-10-04 both the PyPI JSON and simple-index URLs for `saynwerk-pystove`
returned HTTP 404. The name has no visible published project; that does not
prove it is unreserved or that PyPI will accept registration. Recheck before
an explicitly authorized publication. Do not install this fork beside the
production pin; a later Home Assistant dependency migration needs its own gate.

## Local verification evidence (2026-10-04)

| Interpreter | Full suite | Installed-wheel contracts | Ruff / build / archives / isolated build |
| --- | --- | --- | --- |
| Python 3.11.17 | 1130 passed, 6 xfailed | 1004 passed, 6 xfailed | PASS |
| Python 3.12.15 | 1130 passed, 6 xfailed | 1004 passed, 6 xfailed | PASS |
| Python 3.13.16 | 1130 passed, 6 xfailed | 1004 passed, 6 xfailed | PASS |
| Python 3.14.6 | 1130 passed, 6 xfailed | 1004 passed, 6 xfailed | PASS |

All runs: 0 XPASS, ResourceWarnings treated as errors; lifecycle tests assert
no pending tasks or loop errors. Source test environments were created empty,
then installed this distribution; wheel tests created separate empty environments.
The collision/tamper tests are synthetic and make no hardware requests.
All four wheel builds have the same SHA256 (SOURCE_DATE_EPOCH=1791058066):

`008fbb31c50ccacb960241830aa22a1929d76461424d5a45bbc501c56cd88938`

Wheel: `saynwerk_pystove-0.3.0rc1-py3-none-any.whl`.
`git diff eec0d60 -- pystove pystove_cli.py` contains only the version literal.
The existing known-failure tests, requirements and historical approval hashes
are unchanged. No hwam_stove file was modified.
