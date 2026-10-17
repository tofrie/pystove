# RC3: manual Trusted Publishing preparation

Workflow: `.github/workflows/publish-pypi.yml`.
Project: `saynwerk-pystove==0.3.0rc3`; import namespace: `pystove`.
Publishing branch: `release/saynwerk-pystove-0.3.0rc3`.
This preparation does not upload distributions, modify PyPI/GitHub account or
Environment settings, or create a tag/release.

## Immutable release input

Only source **9aebfd71a5d58cb00c4b29baf3b308310d9947d3** is packaged.
Workflow HEAD contains only publishing controls/tests/docs and is never packaged.
Python 3.14.6 and the approved source's pinned build tools reproduce the files
in VERIFY mode. Sdist timestamp/order/owner/mode normalization matches the
approved artifact (SOURCE_DATE_EPOCH=1791058066), preserving every member payload.

| File | SHA256 |
| --- | --- |
| `saynwerk_pystove-0.3.0rc3-py3-none-any.whl` | `03dc8a11e0db7a8c2e3acff4a03ae6c0a41030dd8247c690755387a6eaadc85a` |
| `saynwerk_pystove-0.3.0rc3.tar.gz` | `a49548c8c7f11c27cc30679740eda0d4dba06928f474675c570ab9043d420869` |

Any mismatch aborts; never change the approved hashes to accommodate a build.
VERIFY checks source, archive metadata/version/import ownership, the approved
source suite with exactly six xfails, installed-wheel contracts, Ruff and strict
Twine. Runtime, dependencies and version remain unchanged; hwam_stove is untouched.

## Verify once, publish those exact files without rebuilding

1. Push/PR events only run verification. Manual dispatch defaults to `mode=verify`.
   Neither can authorize PyPI upload. A manual VERIFY on the exact publishing
   branch additionally stores the two approved files in the Actions artifact
   `approved-saynwerk-pystove-0.3.0rc3` (seven-day retention). This is not a GitHub
   Release or package-index upload. Both `authorize` and `publish` remain skipped.
2. A later, separately authorized dispatch must select `mode=publish`, enter
   `publish saynwerk-pystove==0.3.0rc3` exactly, and provide `verified_run_id`.
   **No build, release-source checkout, package installation or Twine invocation runs in
   publish mode.** It reuses files that already passed VERIFY and strict Twine.
3. The helper accepts only a completed, successful, first-attempt manual VERIFY
   in `tofrie/pystove`, on the exact release branch and the **same workflow commit**.
   It checks the workflow path, all three job results (verify success; authorize
   and publish skipped), and exactly one unexpired artifact attributed to that
   run/commit/branch. Arbitrary URLs, artifact names and latest-run selection are
   not accepted. Re-runs require a fresh manual VERIFY instead.
4. The files are downloaded by validated artifact/run IDs and both hashes are
   rechecked. Only these files are transferred to the current run's isolated
   publish job, which independently checks exact filenames, regular-file types
   and both hardcoded SHA256 values before upload. Missing/expired artifacts or
   any mismatch stop the run; publication never falls back to a rebuild.

## Permissions and publication gates

- Both authorization and publication require `workflow_dispatch`, repository
  `tofrie/pystove`, branch `release/saynwerk-pystove-0.3.0rc3`, `mode=publish`,
  and the exact confirmation above. Ordinary pushes/PRs cannot publish.
- Verification and authorization have only `contents: read` and `actions: read`.
  The built-in GitHub token is used for GitHub reads, never PyPI authentication.
- Only the publish job has `id-token: write`, with Environment **pypi**. It has
  no source checkout, package installation or build. Actions are pinned by SHA.
  The official PyPA action uploads to production PyPI via Trusted Publishing/OIDC.
- No PyPI token/repository secret, tag/release trigger, `workflow_run`,
  `pull_request_target`, TestPyPI upload, or `skip-existing` is used.
  Publication has a fixed concurrency group and PyPI attestations enabled.
  Partial upload/failure requires inspection, not an automatic retry.

## Manual Environment rule change required

In **tofrie/pystove → Settings → Environments → pypi → Deployment branches and
tags**, keep **Selected branches and tags** and replace the sole Branch rule:

- old: `release/saynwerk-pystove-0.3.0rc2`
- new: **`release/saynwerk-pystove-0.3.0rc3`**, type **Branch**

There must be exactly this one rule: no tags, wildcards or extra branches.
Keep administrator bypass disabled. Independent required reviewers and Prevent
self-review are not prerequisites for this single-maintainer process. Any
optional reviewer rules still apply; the workflow does not bypass or remove them.
The authorization job reads existing policy and fails closed; it never creates
or changes an Environment. These settings are not changed during preparation.

The existing PyPI project/publisher remains: owner `tofrie`, repository `pystove`,
workflow filename `publish-pypi.yml`, Environment `pypi`. No new pending publisher,
project reservation, credentials or account changes are needed for rc3.

## Safe verification and later authorization

The registered workflow supports an explicit branch dispatch:

```sh
gh workflow run publish-pypi.yml --repo tofrie/pystove \
  --ref release/saynwerk-pystove-0.3.0rc3 -f mode=verify
```

Record the exact workflow commit and successful manual VERIFY run ID. Download
its artifact and independently compare both hashes. Before any publish dispatch,
obtain separate user authorization naming rc3, that workflow commit, VERIFY run
ID, source commit and the two approved hashes. Recheck the branch HEAD and
Environment rule. If the artifact expires or the workflow changes, run VERIFY
again and obtain authorization for the applicable commit/run; do not rebuild in
publish mode. No publish dispatch is part of this preparation.
