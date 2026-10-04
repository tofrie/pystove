"""Offline release guard tests; never request OIDC or call a package index."""

from copy import deepcopy
import gzip
import hashlib
import io
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
    assert "inputs.confirmation == 'publish saynwerk-pystove==0.3.0rc1'" in publish
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
    ("github.ref", "refs/tags/0.3.0rc1"),
    ("inputs.mode", "verify"),
    ("inputs.confirmation", ""),
    ("inputs.confirmation", "publish saynwerk-pystove==0.3.0rc1 "),
])
def test_all_three_upload_gates_require_exact_manual_authorization(changed, value):
    workflow = (ROOT / ".github/workflows/publish-pypi.yml").read_text()
    gates = re.findall(r"if: >-\n((?:[ ]+.+\n)+?)(?= *[a-z-]+:)", workflow)
    assert len(gates) == 3  # Artifact transfer, authorization, and publication.
    values = {
        "github.event_name": "workflow_dispatch",
        "github.repository": "tofrie/pystove",
        "github.ref": f"refs/heads/{release.BRANCH}",
        "inputs.mode": "publish",
        "inputs.confirmation": "publish saynwerk-pystove==0.3.0rc1",
    }
    if changed is not None:
        values[changed] = value
    for gate in gates:
        terms = gate.strip().split("&&")
        assert len(terms) == len(values)
        comparisons = [re.fullmatch(r"([a-z_.]+) == '([^']+)'", term.strip())
                       for term in terms]
        assert all(comparisons), "Unexpected gate expression"
        result = all(values[term[1]] == term[2] for term in comparisons)
        assert result is (changed is None)
