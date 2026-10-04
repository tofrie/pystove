# First PyPI RC: manual Trusted Publishing preparation

Workflow: `.github/workflows/publish-pypi.yml`.
Project: `saynwerk-pystove==0.3.0rc1`; import namespace: `pystove`.
This preparation does not create a PyPI project/publisher, configure accounts,
upload distributions, create a GitHub environment, or publish a tag/release.

## Immutable release input

The workflow checks out **ca58cb39c0c5eb800156f1ffb8b43b373a3391c3** into a
separate source directory. It never packages workflow HEAD or the new CI/docs.
Python 3.14.6 and the approved source's pinned build tools are used. The sdist
container uses the same timestamp/order/owner/mode normalization as the approved
artifact (SOURCE_DATE_EPOCH=1791058066); member contents cannot change.

Both exact hashes must match before any artifact transfer or publication:

| File | SHA256 |
| --- | --- |
| `saynwerk_pystove-0.3.0rc1-py3-none-any.whl` | `6017d0b14dfc904cbda82f899b99d2f45c9bf705361355a368a9526a6aad3044` |
| `saynwerk_pystove-0.3.0rc1.tar.gz` | `fcaec778ba9c0beadcf9dfea69d92bde178b583c9b6423bd05b914838f3764cc` |

Any mismatch aborts: do not change the approved hashes to accommodate a build.
The approved runtime suite, exact six xfails, installed-wheel contracts, archive
validation, Ruff and strict Twine checks must pass. Runtime, dependencies and
version are unchanged; no hwam_stove files are involved.

## Permissions and event gates

- Pushes/PRs affecting this workflow run **verification only**. Manual dispatch
  also defaults to `mode=verify`, without OIDC, environment/deployment creation,
  GitHub artifact upload or any package-index upload.
- Publication requires `workflow_dispatch`, repository `tofrie/pystove`, branch
  `release/saynwerk-pystove-0.3.0rc1`, `mode=publish`, and the exact confirmation
  `publish saynwerk-pystove==0.3.0rc1`.
- Verification has only `contents: read`. The separate authorization job also
  has `actions: read` to inspect existing environment policy. Its built-in
  GitHub token is used only for GitHub reads, never for PyPI authentication.
- The publish job alone has `id-token: write` and environment `pypi`. It runs
  on a fresh runner with no source checkout, package installation or builds.
  It downloads this run's verified artifact (no caller-controlled run/URL),
  rejects missing/extra/symlink files, independently rechecks both hardcoded
  SHA256 values, then uses the SHA-pinned official PyPA publishing action.
- No API token, repository secret, release event, tag trigger, `workflow_run`,
  `pull_request_target`, TestPyPI step or `skip-existing` behavior is used.
  A fixed concurrency group prevents concurrent upload jobs. PyPI attestations
  remain enabled. Partial upload/failure requires manual inspection, not retry.

## Manual GitHub setup (not performed by the agent)

In `tofrie/pystove` → Settings → Environments, create **pypi**:

1. Required reviewers and **Prevent self-review** are optional, not publication
   prerequisites. This project uses a single-maintainer release process; the
   explicit manual dispatch and exact confirmation provide release approval.
2. Disable administrator bypass of deployment protection rules. The REST
   Environment response does not expose this UI setting; the release maintainer
   must verify it explicitly before dispatching publication.
3. Under selected deployment branches/tags, permit exactly the **branch**
   `release/saynwerk-pystove-0.3.0rc1`; no tags, wildcards or additional rules.
4. Do not create any PyPI API-token secrets.

The authorization job fails on a missing environment or any other deployment
branch policy. It never creates an environment as a fallback. Optional reviewer
rules, if configured in GitHub, still apply there; the workflow does not remove
or bypass them. Repository administrators can still edit workflow or environment
policy; review changes to these files and the release branch and recheck policy
before manual publication.

The current default branch is `master`. GitHub's manual-run UI requires the
workflow on the default branch. Do not merge the release runtime into master
merely to obtain the button. A separately approved workflow/tooling-only change
can register it there, then select the release branch for dispatch. Once the
workflow is registered, the CLI/API may also permit explicit branch dispatch;
verify-only dispatch is the safe check. No default-branch change is made here.

## Exact PyPI pending publisher (enter manually)

Sign into the intended PyPI owner account, open **Publishing** → add a pending
GitHub publisher (https://pypi.org/manage/account/publishing/):

| Field | Value |
| --- | --- |
| PyPI project name | `saynwerk-pystove` |
| GitHub owner | `tofrie` |
| Repository | `pystove` |
| Workflow filename | `publish-pypi.yml` (filename only) |
| Environment | `pypi` |

Pending publishers do not reserve or create the project before their first
successful upload. No agent-side PyPI setting or registration is performed.

## Safe verification and final authorization

A verify-only dispatch, once available:

```sh
gh workflow run publish-pypi.yml --repo tofrie/pystove \
  --ref release/saynwerk-pystove-0.3.0rc1 -f mode=verify
```

Before the first upload, require explicit user authorization naming
`saynwerk-pystove==0.3.0rc1`, source `ca58cb39c0c5eb800156f1ffb8b43b373a3391c3`,
both hashes above and the reviewed workflow commit. Only then may a human select
`mode=publish` and supply the confirmation string. Review the green verification
job and immutable hashes before the single maintainer dispatches publication.
No independent reviewer is required. No publish-mode dispatch or environment
approval is part of this preparation.

References: [PyPI publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/),
[pending publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/),
[GitHub environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments),
[manual dispatch](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch).
