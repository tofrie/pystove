"""RC2 verification only: reproduce approved bytes and fail closed; no upload."""

import argparse
import copy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile

SOURCE = "0ddf5fa413969ff9037b54575a1be46bb91ece04"
BRANCH = "release/saynwerk-pystove-0.3.0rc2"
REPOSITORY = "tofrie/pystove"
ARTIFACT = "approved-saynwerk-pystove-0.3.0rc2"
EPOCH = 1791058066
APPROVED = {
    "saynwerk_pystove-0.3.0rc2-py3-none-any.whl":
        "1aa40ab8a5a53e31f999b0dd98c2742a37890269196b3fcb38faef81a9c09028",
    "saynwerk_pystove-0.3.0rc2.tar.gz":
        "8ed8600f302d2d18c4e8c48ade93612752ba53f65a46472a467e5ab8452886be",
}


def verify_artifacts(directory):
    directory = Path(directory)
    if {p.name for p in directory.iterdir()} != set(APPROVED):
        raise ValueError("Require exactly the two approved release files")
    for name, digest in APPROVED.items():
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Release files must be regular files, not symlinks")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Approved SHA256 mismatch: {name}; STOP, never upload")
    return APPROVED


def normalize_sdist(path):
    """Match the approved normalization without changing any member payload."""
    with tarfile.open(path, "r:gz") as archive:
        entries = [
            (copy.copy(m), archive.extractfile(m).read() if m.isfile() else None)
            for m in archive.getmembers()
        ]
    buffer = io.BytesIO()
    with gzip.GzipFile(
        filename="", mode="wb", fileobj=buffer, mtime=EPOCH, compresslevel=9
    ) as gz, tarfile.open(mode="w", fileobj=gz, format=tarfile.PAX_FORMAT) as archive:
        for member, data in sorted(entries, key=lambda pair: pair[0].name):
            if not (member.isfile() or member.isdir()):
                raise ValueError("Unexpected sdist member type")
            member.uid = member.gid = 0
            member.uname = member.gname = ""
            member.mtime = EPOCH
            member.pax_headers = {}
            member.mode = 0o755 if member.isdir() else 0o644
            archive.addfile(member, io.BytesIO(data) if data is not None else None)
    path.write_bytes(buffer.getvalue())
    with tarfile.open(path) as archive:
        after = {m.name: archive.extractfile(m).read()
                 for m in archive.getmembers() if m.isfile()}
    if after != {m.name: data for m, data in entries if data is not None}:
        raise ValueError("Normalization changed sdist file content")


def reproduce(source, destination):
    """Never build workflow HEAD: only the independently approved source commit."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN"):
        raise ValueError("Build job must not have OIDC publishing permission")
    if destination.is_relative_to(source):
        raise ValueError("Build artifacts must be outside the source checkout")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=source, text=True
    ).strip()
    if head != SOURCE or subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=source
    ):
        raise ValueError("Require a clean checkout of the approved release commit")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Build destination must be empty")
    env = {**os.environ, "SOURCE_DATE_EPOCH": str(EPOCH)}
    subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(destination)],
        cwd=source, env=env, check=True,
    )
    normalize_sdist(destination / "saynwerk_pystove-0.3.0rc2.tar.gz")
    verify_artifacts(destination)
    subprocess.run(
        [sys.executable, "ci/validate_package.py", "--dist-dir", str(destination)],
        cwd=source, env=env, check=True,
    )


def verify_environment(config, branches):
    """A missing or unprotected environment must not be silently auto-created."""
    if config.get("name") != "pypi":
        raise ValueError("The pre-existing pypi environment is required")
    # Single-maintainer releases do not require reviewer/self-review rules.
    if config.get("deployment_branch_policy") != {
        "protected_branches": False, "custom_branch_policies": True,
    }:
        raise ValueError("Require selected deployment branches")
    policies = branches.get("branch_policies", [])
    if (
        branches.get("total_count") != 1 or len(policies) != 1
        or policies[0].get("name") != BRANCH or policies[0].get("type") != "branch"
    ):
        raise ValueError("Only the exact release branch may deploy; no tags/wildcards")
    # The REST Environment schema does not expose the admin-bypass UI setting.
    # Disabling admin bypass must additionally be checked by the release maintainer.


def verify_run(run_id, head, run, jobs, artifacts):
    """Bind approved files to a successful manual VERIFY of this exact workflow."""
    expected = {
        "id": run_id, "event": "workflow_dispatch", "run_attempt": 1,
        "path": ".github/workflows/publish-pypi.yml", "head_branch": BRANCH,
        "head_sha": head, "status": "completed", "conclusion": "success",
    }
    if any(run.get(key) != value for key, value in expected.items()) or any(
        run.get(key, {}).get("full_name") != REPOSITORY
        for key in ("repository", "head_repository")
    ):
        raise ValueError(
            "Require a successful first-attempt VERIFY of this workflow commit"
        )
    expected_jobs = {"verify": "success", "authorize": "skipped", "publish": "skipped"}
    rows = jobs.get("jobs", [])
    if (
        jobs.get("total_count") != 3 or len(rows) != 3
        or {j.get("name"): j.get("conclusion") for j in rows} != expected_jobs
        or any(j.get("status") != "completed" for j in rows)
    ):
        raise ValueError(
            "Source run must have skipped both authorization and publication"
        )
    rows = artifacts.get("artifacts", [])
    if artifacts.get("total_count") != 1 or len(rows) != 1:
        raise ValueError("Require exactly one approved VERIFY artifact")
    artifact = rows[0]
    if (
        artifact.get("name") != ARTIFACT or artifact.get("expired") is not False
        or type(artifact.get("id")) is not int or artifact["id"] <= 0
        or type(artifact.get("size_in_bytes")) is not int
        or artifact["size_in_bytes"] <= 0
        or any(artifact.get("workflow_run", {}).get(key) != value for key, value in {
            "id": run_id, "head_sha": head, "head_branch": BRANCH,
        }.items())
    ):
        raise ValueError("Invalid, expired or incorrectly attributed VERIFY artifact")
    return artifact["id"]


def resolve_verified_run(run_id, head, output):
    """Read GitHub metadata only; never select latest, rebuild, or publish."""
    if (
        not re.fullmatch(r"[1-9][0-9]*", run_id)
        or not re.fullmatch(r"[0-9a-f]{40}", head)
    ):
        raise ValueError(
            "Require an explicit numeric VERIFY run ID and exact workflow SHA"
        )
    base = f"repos/{REPOSITORY}/actions/runs/{run_id}"

    def read(path):
        return json.loads(subprocess.check_output(["gh", "api", path], text=True))

    artifact_id = verify_run(
        int(run_id), head, read(base), read(base + "/attempts/1/jobs?per_page=100"),
        read(base + "/artifacts?per_page=100"),
    )
    with Path(output).open("a") as stream:
        stream.write(f"run_id={int(run_id)}\nartifact_id={artifact_id}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--dist-dir", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--dist-dir", type=Path, required=True)
    environment = commands.add_parser("environment")
    environment.add_argument("--config", type=Path, required=True)
    environment.add_argument("--branches", type=Path, required=True)
    verified_run = commands.add_parser("verified-run")
    verified_run.add_argument("--run-id", required=True)
    verified_run.add_argument("--head", required=True)
    verified_run.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        reproduce(args.source, args.dist_dir)
        print(json.dumps(APPROVED, indent=2))
    elif args.command == "verify":
        print(json.dumps(verify_artifacts(args.dist_dir), indent=2))
    elif args.command == "verified-run":
        resolve_verified_run(args.run_id, args.head, args.output)
        print("Successful VERIFY run and artifact provenance verified")
    else:
        verify_environment(json.loads(args.config.read_text()),
                           json.loads(args.branches.read_text()))
        print("Environment policy verified; admin bypass requires manual UI check")


if __name__ == "__main__":
    main()
