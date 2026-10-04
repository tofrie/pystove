"""First-RC preparation only: reproduce approved bytes and fail closed; no upload."""

import argparse
import copy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

SOURCE = "ca58cb39c0c5eb800156f1ffb8b43b373a3391c3"
BRANCH = "release/saynwerk-pystove-0.3.0rc1"
EPOCH = 1791058066
APPROVED = {
    "saynwerk_pystove-0.3.0rc1-py3-none-any.whl":
        "6017d0b14dfc904cbda82f899b99d2f45c9bf705361355a368a9526a6aad3044",
    "saynwerk_pystove-0.3.0rc1.tar.gz":
        "fcaec778ba9c0beadcf9dfea69d92bde178b583c9b6423bd05b914838f3764cc",
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
    normalize_sdist(destination / "saynwerk_pystove-0.3.0rc1.tar.gz")
    verify_artifacts(destination)
    subprocess.run(
        [sys.executable, "ci/validate_package.py", "--dist-dir", str(destination)],
        cwd=source, env=env, check=True,
    )


def verify_environment(config, branches):
    """A missing or unprotected environment must not be silently auto-created."""
    if config.get("name") != "pypi":
        raise ValueError("The pre-existing pypi environment is required")
    reviewers = [r for r in config.get("protection_rules", [])
                 if r.get("type") == "required_reviewers"]
    if (
        len(reviewers) != 1 or not reviewers[0].get("reviewers")
        or reviewers[0].get("prevent_self_review") is not True
    ):
        raise ValueError("Require reviewers and prevent self-review")
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
    # Disabling admin bypass must additionally be checked by the human reviewer.


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
    args = parser.parse_args()
    if args.command == "build":
        reproduce(args.source, args.dist_dir)
        print(json.dumps(APPROVED, indent=2))
    elif args.command == "verify":
        print(json.dumps(verify_artifacts(args.dist_dir), indent=2))
    else:
        verify_environment(json.loads(args.config.read_text()),
                           json.loads(args.branches.read_text()))
        print("Environment policy verified; admin bypass requires manual UI check")


if __name__ == "__main__":
    main()
