"""Offline release guard tests; never request OIDC or call a package index."""

from copy import deepcopy
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

import pytest

from ci import pypi_release as release

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def artifacts(tmp_path, monkeypatch):
    approved = {}
    for name in release.APPROVED:
        data = name.encode()
        (tmp_path / name).write_bytes(data)
        approved[name] = hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(release, "APPROVED", approved)
    return tmp_path


@pytest.mark.parametrize(
    "mutation", ["none", "missing", "extra", "tampered", "symlink"]
)
def test_only_exact_approved_regular_files_can_pass(artifacts, mutation):
    path = next(artifacts.iterdir())
    if mutation == "missing":
        path.unlink()
    elif mutation == "extra":
        (artifacts / "other.whl").write_bytes(b"unexpected")
    elif mutation == "tampered":
        path.write_bytes(b"modified")
    elif mutation == "symlink":
        path.unlink()
        path.symlink_to(artifacts / "nonexistent")
    if mutation == "none":
        assert release.verify_artifacts(artifacts) == release.APPROVED
    else:
        with pytest.raises(ValueError):
            release.verify_artifacts(artifacts)


def test_normalization_preserves_content_and_removes_container_variation(tmp_path):
    outputs = []
    for index in (1, 2):
        path = tmp_path / f"{index}.tar.gz"
        order = ["root/a", "root/b"] if index == 1 else ["root/b", "root/a"]
        with (
            gzip.GzipFile(filename=str(path), mode="wb", mtime=index) as gz,
            tarfile.open(fileobj=gz, mode="w") as archive,
        ):
            for name in order:
                member = tarfile.TarInfo(name)
                data = name.encode()
                member.size = len(data)
                member.mtime = index
                member.uid = index
                archive.addfile(member, io.BytesIO(data))
        release.normalize_sdist(path)
        outputs.append(path.read_bytes())
        with tarfile.open(path) as archive:
            assert {m.name: archive.extractfile(m).read() for m in archive} == {
                "root/a": b"root/a", "root/b": b"root/b",
            }
    assert outputs[0] == outputs[1]


@pytest.fixture
def environment():
    return {
        "name": "pypi",
        "protection_rules": [{
            "type": "required_reviewers", "prevent_self_review": True,
            "reviewers": [{"type": "User", "reviewer": {"id": 123}}],
        }],
        "deployment_branch_policy": {
            "protected_branches": False, "custom_branch_policies": True,
        },
    }


@pytest.fixture
def branches():
    return {"total_count": 1,
            "branch_policies": [{"name": release.BRANCH, "type": "branch"}]}


@pytest.mark.parametrize("change", [
    "none", "missing", "no_rules", "no_review", "self_review",
    "unrestricted", "wildcard", "tag", "extra_branch", "wrong_name",
])
def test_environment_requires_exact_branch_but_not_independent_review(
    environment, branches, change
):
    env = deepcopy(environment)
    if change == "missing":
        env = {}
    elif change == "no_rules":
        env["protection_rules"] = [{"type": "branch_policy"}]
    elif change == "no_review":
        env["protection_rules"][0]["reviewers"] = []
    elif change == "self_review":
        env["protection_rules"][0]["prevent_self_review"] = False
    elif change == "unrestricted":
        env["deployment_branch_policy"] = None
    elif change == "wildcard":
        branches["branch_policies"][0]["name"] = "*"
    elif change == "tag":
        branches["branch_policies"][0]["type"] = "tag"
    elif change == "extra_branch":
        branches["total_count"] = 2
        branches["branch_policies"].append({"name": "master", "type": "branch"})
    elif change == "wrong_name":
        env["name"] = "other"
    if change in {"none", "no_rules", "no_review", "self_review"}:
        release.verify_environment(env, branches)
    else:
        with pytest.raises(ValueError):
            release.verify_environment(env, branches)


def test_builder_rejects_oidc_permission_before_running_any_code(tmp_path, monkeypatch):
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "synthetic-test-sentinel")
    with pytest.raises(ValueError, match="OIDC"):
        release.reproduce(tmp_path / "source", tmp_path / "dist")


@pytest.mark.parametrize(
    "head,status", [("wrong commit", b""), (release.SOURCE, b" M x")]
)
def test_builder_rejects_changed_source_before_build(
    tmp_path, monkeypatch, head, status
):
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", raising=False)
    replies = iter([head + "\n", status])
    monkeypatch.setattr(
        release.subprocess, "check_output", lambda *a, **k: next(replies)
    )
    monkeypatch.setattr(release.subprocess, "run", lambda *a, **k: pytest.fail("built"))
    with pytest.raises(ValueError, match="clean checkout"):
        release.reproduce(tmp_path / "source", tmp_path / "dist")


def test_workflow_keeps_oidc_and_upload_out_of_ordinary_events():
    workflow = (ROOT / ".github/workflows/publish-pypi.yml").read_text()
    before, publish = workflow.split("\n  publish:\n")
    assert "id-token:" not in before
    assert "permissions:\n      id-token: write\n" in publish
    assert "environment:\n      name: pypi\n" in publish
    assert "needs: [verify, authorize]" in publish
    assert "github.event_name == 'workflow_dispatch'" in publish
    assert "github.repository == 'tofrie/pystove'" in publish
    assert f"github.ref == 'refs/heads/{release.BRANCH}'" in publish
    assert "inputs.mode == 'publish'" in publish
    assert "inputs.confirmation == 'publish saynwerk-pystove==0.3.0rc2'" in publish
    assert "default: verify" in before
    assert "actions/checkout@" not in publish and "pip install" not in publish
    assert "secrets." not in workflow and "workflow_run:" not in workflow
    assert "pull_request_target:" not in workflow
    assert workflow.count("pypa/gh-action-pypi-publish@") == 1
    assert "repository-url: https://upload.pypi.org/legacy/" in publish
    assert "skip-existing: false" in publish
    for name, digest in release.APPROVED.items():
        assert f"'{name}': '{digest}'" in publish
    for action in re.findall(r"uses: (.+)", workflow):
        assert re.search(r"@[0-9a-f]{40}(?:\s|$)", action), action


@pytest.mark.parametrize("changed,value", [
    (None, None),
    ("github.event_name", "push"),
    ("github.event_name", "pull_request"),
    ("github.repository", "other/pystove"),
    ("github.ref", "refs/heads/master"),
    ("github.ref", "refs/tags/0.3.0rc2"),
    ("inputs.mode", "verify"),
    ("inputs.confirmation", ""),
    ("inputs.confirmation", "publish saynwerk-pystove==0.3.0rc2 "),
])
def test_both_publication_gates_require_exact_manual_authorization(changed, value):
    workflow = (ROOT / ".github/workflows/publish-pypi.yml").read_text()
    gates = re.findall(r"if: >-\n((?:[ ]+.+\n)+?)(?= *[a-z-]+:)", workflow)
    assert len(gates) == 3  # Artifact transfer, authorization, and publication.
    values = {
        "github.event_name": "workflow_dispatch",
        "github.repository": "tofrie/pystove",
        "github.ref": f"refs/heads/{release.BRANCH}",
        "inputs.mode": "publish",
        "inputs.confirmation": "publish saynwerk-pystove==0.3.0rc2",
    }
    if changed is not None:
        values[changed] = value
    for gate in gates[1:]:
        terms = gate.strip().split("&&")
        assert len(terms) == len(values)
        comparisons = [re.fullmatch(r"([a-z_.]+) == '([^']+)'", term.strip())
                       for term in terms]
        assert all(comparisons), "Unexpected gate expression"
        result = all(values[term[1]] == term[2] for term in comparisons)
        assert result is (changed is None)


def test_verify_storage_is_manual_only_and_publish_never_builds():
    workflow = (ROOT / ".github/workflows/publish-pypi.yml").read_text()
    verify = workflow.split("\n  authorize:\n")[0]
    store = verify.split("      - name: Store verified files")[1]
    assert "github.event_name == 'workflow_dispatch'" in store
    assert "github.repository == 'tofrie/pystove'" in store
    assert f"github.ref == 'refs/heads/{release.BRANCH}'" in store
    assert "(inputs.mode == 'verify' ||" in store
    assert "(inputs.mode == 'publish' &&" in store
    assert "inputs.confirmation == 'publish saynwerk-pystove==0.3.0rc2'))" in store
    for step in verify.split("      - ")[1:]:
        if any(text in step for text in (
            "path: release-source", "pip install", "--source release-source",
            "working-directory: release-source", "python -m twine",
        )):
            assert "if: inputs.mode != 'publish'" in step
    assert f"ref: {release.SOURCE}" in verify
    assert 'verified-run --run-id "$VERIFIED_RUN_ID" --head "$GITHUB_SHA"' in verify
    assert "run-id: ${{ steps.approved.outputs.run_id }}" in verify
    assert "artifact-ids: ${{ steps.approved.outputs.artifact_id }}" in verify
    assert "run-id: ${{ inputs." not in verify
    assert "artifact-ids: ${{ inputs." not in verify
    assert "run: python control/ci/pypi_release.py verify --dist-dir dist" in verify


@pytest.fixture
def prior_verify():
    head = "a" * 40
    run = {
        "id": 123, "event": "workflow_dispatch", "run_attempt": 1,
        "path": ".github/workflows/publish-pypi.yml", "head_branch": release.BRANCH,
        "head_sha": head, "status": "completed", "conclusion": "success",
        "repository": {"full_name": release.REPOSITORY},
        "head_repository": {"full_name": release.REPOSITORY},
    }
    jobs = {"total_count": 3, "jobs": [
        {"name": name, "status": "completed", "conclusion": conclusion}
        for name, conclusion in (
            ("verify", "success"), ("authorize", "skipped"), ("publish", "skipped")
        )
    ]}
    artifacts = {"total_count": 1, "artifacts": [{
        "id": 456, "name": release.ARTIFACT, "expired": False, "size_in_bytes": 500,
        "workflow_run": {"id": 123, "head_sha": head, "head_branch": release.BRANCH},
    }]}
    return head, run, jobs, artifacts


@pytest.mark.parametrize("field,value", [
    ("id", 124), ("event", "push"), ("event", "pull_request"),
    ("run_attempt", 2), ("path", ".github/workflows/other.yml"),
    ("head_branch", "release/saynwerk-pystove-0.3.0rc1"),
    ("head_sha", "b" * 40), ("status", "in_progress"),
    ("conclusion", "failure"), ("conclusion", "cancelled"),
    ("repository", {"full_name": "other/pystove"}),
    ("head_repository", {"full_name": "other/pystove"}),
])
def test_prior_run_provenance_fails_closed(prior_verify, field, value):
    head, run, jobs, artifacts = prior_verify
    run[field] = value
    with pytest.raises(ValueError, match="VERIFY"):
        release.verify_run(123, head, run, jobs, artifacts)


@pytest.mark.parametrize("index,field,value", [
    (0, "conclusion", "failure"), (0, "status", "in_progress"),
    (1, "conclusion", "success"), (2, "conclusion", "success"),
    (2, "conclusion", "failure"), (2, "name", "unknown"),
])
def test_prior_run_must_not_have_published(prior_verify, index, field, value):
    head, run, jobs, artifacts = prior_verify
    jobs["jobs"][index][field] = value
    with pytest.raises(ValueError, match="skipped"):
        release.verify_run(123, head, run, jobs, artifacts)


@pytest.mark.parametrize("field,value", [
    ("id", 0), ("id", "456"), ("name", "other"), ("expired", True),
    ("expired", None), ("size_in_bytes", 0),
    ("workflow_run", {}), ("workflow_run", {"id": 124}),
    ("workflow_run", {"id": 123, "head_sha": "b" * 40, "head_branch": release.BRANCH}),
    ("workflow_run", {"id": 123, "head_sha": "a" * 40, "head_branch": "master"}),
])
def test_prior_artifact_must_be_unexpired_and_bound_to_run(prior_verify, field, value):
    head, run, jobs, artifacts = prior_verify
    artifacts["artifacts"][0][field] = value
    with pytest.raises(ValueError, match="artifact"):
        release.verify_run(123, head, run, jobs, artifacts)


@pytest.mark.parametrize("collection", ["jobs", "artifacts"])
@pytest.mark.parametrize("mutation", ["missing", "extra", "incomplete_page"])
def test_prior_run_inventory_must_be_exact(prior_verify, collection, mutation):
    head, run, jobs, artifacts = prior_verify
    data = jobs if collection == "jobs" else artifacts
    if mutation == "missing":
        data[collection].pop()
    elif mutation == "extra":
        data[collection].append(deepcopy(data[collection][0]))
    else:
        data["total_count"] += 100
    with pytest.raises(ValueError):
        release.verify_run(123, head, run, jobs, artifacts)


def test_resolve_verified_run_reads_only_and_outputs_validated_ids(
    prior_verify, tmp_path, monkeypatch
):
    head, run, jobs, artifacts = prior_verify
    base = f"repos/{release.REPOSITORY}/actions/runs/123"
    replies = {
        base: run, base + "/attempts/1/jobs?per_page=100": jobs,
        base + "/artifacts?per_page=100": artifacts,
    }
    calls = []

    def read(command, **kwargs):
        assert command[:2] == ["gh", "api"]
        assert len(command) == 3
        calls.append(command[2])
        return json.dumps(replies[command[2]])

    monkeypatch.setattr(release.subprocess, "check_output", read)
    output = tmp_path / "output"
    release.resolve_verified_run("123", head, output)
    assert output.read_text() == "run_id=123\nartifact_id=456\n"
    assert calls == list(replies)


@pytest.mark.parametrize("run_id,head", [
    ("", "a" * 40), ("0", "a" * 40), ("../123", "a" * 40),
    ("123?x=y", "a" * 40), ("123\n", "a" * 40),
    ("１２３", "a" * 40), ("123", "not-a-commit"),
])
def test_bad_run_input_never_calls_github(tmp_path, monkeypatch, run_id, head):
    monkeypatch.setattr(
        release.subprocess, "check_output", lambda *a, **k: pytest.fail("network")
    )
    with pytest.raises(ValueError, match="explicit numeric"):
        release.resolve_verified_run(run_id, head, tmp_path / "output")
    assert not (tmp_path / "output").exists()
