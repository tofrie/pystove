"""Validate release artifacts against the working 0.3a1 contract and H3 fix.

This module deliberately uses only the standard library and never imports the
package. The baseline hashes describe the published runtime, not freshly
generated expectations from the code under test. The separately reviewed H3
source hash permits only that exact revision; its scope hash additionally freezes
all bytes outside the two existing lifecycle method bodies and their new private
cleanup helper.
"""

import argparse
import ast
import base64
import csv
from email.parser import BytesParser
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class ValidationError(ValueError):
    """An artifact or source tree violates the compatibility baseline."""


def load_baseline(repo_root=ROOT):
    return json.loads(
        (Path(repo_root) / "ci" / "compatibility_baseline.json").read_text(
            encoding="utf-8"
        )
    )


def version_assignment(data):
    """Find exactly one literal version assignment without executing Python."""
    tree = ast.parse(data.decode("utf-8"))
    values = [
        statement.value
        for statement in tree.body
        if isinstance(statement, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in statement.targets
        )
    ]
    if len(values) != 1:
        raise ValidationError("Version source must have one __version__ assignment")
    value = values[0]
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        raise ValidationError("Version source must contain a literal string")
    return value


def read_version(repo_root=ROOT):
    return version_assignment(
        (Path(repo_root) / "pystove" / "version.py").read_bytes()
    ).value


def baseline_source_hash(name, data, baseline):
    """Allow the version value to change while freezing all surrounding bytes."""
    if name == "pystove/version.py":
        assignment = version_assignment(data)
        lines = data.splitlines(keepends=True)
        start = sum(map(len, lines[: assignment.lineno - 1])) + assignment.col_offset
        end = (
            sum(map(len, lines[: assignment.end_lineno - 1]))
            + assignment.end_col_offset
        )
        literal = data[start:end]
        quoted = assignment.value.encode("utf-8")
        if literal not in (b'"' + quoted + b'"', b"'" + quoted + b"'"):
            raise ValidationError("Version must retain its plain quoted literal")
        replacement = literal[:1] + baseline["version"].encode("utf-8") + literal[-1:]
        data = data[:start] + replacement + data[end:]
    return hashlib.sha256(data).hexdigest()


def validate_runtime_source(name, data, baseline):
    expected = baseline["runtime_sha256"][name]
    reviewed = baseline.get("reviewed_runtime_changes", {})
    if reviewed:
        if set(reviewed) != {"H3"}:
            raise ValidationError("Only the reviewed H3 runtime change is allowed")
        change = reviewed["H3"]
        if (
            change["path"] != "pystove/pystove.py"
            or change["method_bodies"] != ["Stove.create", "Stove._identify"]
            or change["added_module_function"] != "_finish_initialization_cleanup"
            or change["phase1_commit"]
            != "5876e2d7c381baf1dc72815a110bc2c0b2c2d8c4"
        ):
            raise ValidationError("Reviewed H3 runtime scope changed")
        if name == change["path"]:
            if lifecycle_scope_hash(data) != change["unchanged_source_sha256"]:
                raise ValidationError("Runtime outside H3 lifecycle bodies changed")
            expected = change["source_sha256"]
    if baseline_source_hash(name, data, baseline) != expected:
        raise ValidationError(f"Frozen runtime changed: {name}")


def lifecycle_scope_hash(data):
    """Freeze surrounding bytes; exclude only two H3 bodies and their helper."""
    tree = ast.parse(data.decode("utf-8"))
    stoves = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Stove"
    ]
    if len(stoves) != 1:
        raise ValidationError("H3 scope requires exactly one Stove class")
    ranges = []
    lines = data.splitlines(keepends=True)
    helpers = [
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "_finish_initialization_cleanup"
    ]
    if helpers:
        if len(helpers) != 1:
            raise ValidationError("H3 scope permits only one private cleanup helper")
        helper = helpers[0]
        if helper.decorator_list or tree.body.index(helper) + 1 != tree.body.index(
            stoves[0]
        ):
            raise ValidationError("H3 cleanup helper must immediately precede Stove")
        start = sum(map(len, lines[: helper.lineno - 1]))
        end = sum(map(len, lines[: stoves[0].lineno - 1]))
        statement_end = (
            sum(map(len, lines[: helper.end_lineno - 1])) + helper.end_col_offset
        )
        if data[statement_end:end].strip():
            raise ValidationError(
                "H3 cleanup helper must have only trailing whitespace"
            )
        # Removing the newly added function, including its trailing blank lines,
        # leaves exactly the original spacing before the existing Stove class.
        ranges.append((start, end, b""))
    for method_name in ("create", "_identify"):
        methods = [
            node
            for node in stoves[0].body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == method_name
        ]
        if len(methods) != 1:
            raise ValidationError(f"H3 scope requires one Stove.{method_name}")
        first, last = methods[0].body[0], methods[0].body[-1]
        start = sum(map(len, lines[: first.lineno - 1])) + first.col_offset
        end = sum(map(len, lines[: last.end_lineno - 1])) + last.end_col_offset
        ranges.append((start, end, b"<reviewed H3 lifecycle body>"))
    for start, end, replacement in sorted(ranges, reverse=True):
        data = data[:start] + replacement + data[end:]
    return hashlib.sha256(data).hexdigest()


def validate_sources(repo_root=ROOT):
    repo_root = Path(repo_root)
    baseline = load_baseline(repo_root)
    for name in baseline["runtime_sha256"]:
        validate_runtime_source(name, (repo_root / name).read_bytes(), baseline)
    version = read_version(repo_root)
    if version == baseline["version"] or not re.search(r"\.dev\d+$", version):
        raise ValidationError("Foundation artifacts require a new development version")
    return baseline, version


def validate_metadata(data, version, baseline):
    metadata = BytesParser().parsebytes(data)
    if metadata.get_all("Name") != ["pystove"]:
        raise ValidationError("Artifact distribution name must be pystove")
    if metadata.get_all("Version") != [version]:
        raise ValidationError("Artifact version differs from pystove/version.py")
    if metadata.get_all("Requires-Python") is not None:
        raise ValidationError("This phase must not introduce Requires-Python")
    requirements = metadata.get_all("Requires-Dist", [])
    if sorted(requirements) != sorted(baseline["runtime_requires_dist"]):
        raise ValidationError("Runtime dependency contract changed")
    if metadata.get_all("Provides-Extra"):
        raise ValidationError("This phase must not introduce package extras")


def safe_archive_name(name):
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or "\0" in name
        or path.is_absolute()
        or ".." in path.parts
        or str(path) in ("", ".")
        or re.match(r"^[A-Za-z]:", name)
        or path.as_posix() != name.rstrip("/")
    ):
        raise ValidationError(f"Unsafe archive path: {name!r}")
    if "__pycache__" in path.parts or path.suffix in (".pyc", ".pyo"):
        raise ValidationError(f"Generated bytecode in archive: {name}")
    return path


def validate_record(files, record_name):
    try:
        rows = list(csv.reader(io.StringIO(files[record_name].decode("utf-8"))))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValidationError("Invalid wheel RECORD") from exc
    entries = {}
    for row in rows:
        if len(row) != 3 or row[0] in entries:
            raise ValidationError("Malformed or duplicate wheel RECORD row")
        entries[row[0]] = row[1:]
    if set(entries) != set(files):
        raise ValidationError("Wheel RECORD does not cover exactly all files")
    for name, data in files.items():
        digest, size = entries[name]
        if name == record_name:
            if digest or size:
                raise ValidationError("RECORD must not hash itself")
            continue
        expected = base64.urlsafe_b64encode(hashlib.sha256(data).digest())
        if digest != "sha256=" + expected.rstrip(b"=").decode("ascii"):
            raise ValidationError(f"Wheel RECORD hash mismatch: {name}")
        if size != str(len(data)):
            raise ValidationError(f"Wheel RECORD size mismatch: {name}")


def validate_wheel(wheel_path, repo_root=ROOT):
    baseline, version = validate_sources(repo_root)
    with zipfile.ZipFile(wheel_path) as archive:
        files = {}
        seen = set()
        for member in archive.infolist():
            safe_archive_name(member.filename)
            if member.filename in seen:
                raise ValidationError("Duplicate wheel archive member")
            seen.add(member.filename)
            if member.is_dir():
                continue
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValidationError("Wheel must not contain symbolic links")
            files[member.filename] = archive.read(member)
    dist_info = f"pystove-{version}.dist-info"
    package_files = {
        name for name in baseline["runtime_sha256"] if name.startswith("pystove/")
    }
    actual_package = {name for name in files if not name.startswith(dist_info + "/")}
    if actual_package != package_files:
        raise ValidationError("Wheel package inventory changed (including CLI)")
    for name in package_files:
        validate_runtime_source(name, files[name], baseline)
        if (
            name == "pystove/version.py"
            and version_assignment(files[name]).value != version
        ):
            raise ValidationError("Wheel runtime version differs from source")
    metadata_name = f"{dist_info}/METADATA"
    wheel_name = f"{dist_info}/WHEEL"
    record_name = f"{dist_info}/RECORD"
    if not {metadata_name, wheel_name, record_name} <= files.keys():
        raise ValidationError("Wheel metadata is incomplete")
    if f"{dist_info}/entry_points.txt" in files:
        raise ValidationError("This phase must not introduce CLI entry points")
    validate_metadata(files[metadata_name], version, baseline)
    wheel_metadata = BytesParser().parsebytes(files[wheel_name])
    if wheel_metadata.get("Root-Is-Purelib") != "true":
        raise ValidationError("Wheel must remain a pure Python library")
    if wheel_metadata.get_all("Tag") != ["py3-none-any"]:
        raise ValidationError("Wheel platform contract changed")
    validate_record(files, record_name)


def required_sdist_sources(repo_root=ROOT):
    """Keep the compatibility evidence and its tooling usable from the sdist."""
    repo_root = Path(repo_root)
    required = {
        "LICENSE",
        "README.md",
        "CHANGELOG.md",
        "MANIFEST.in",
        "setup.py",
        "pyproject.toml",
        "requirements.txt",
        "requirements-dev.txt",
        "pystove_cli.py",
        "ci/compatibility_baseline.json",
        "ci/validate_package.py",
        "ci/check_isolated_build.py",
        "ci/test_wheel.py",
        "docs/BASELINE.md",
        "tests/__init__.py",
        "tests/conftest.py",
        "tests/test_contract_api.py",
        "tests/test_contract_commands.py",
        "tests/test_create_lifecycle.py",
        "tests/test_known_failures.py",
        "tests/test_packaging.py",
        "tests/fixtures/hwam_contract.json",
    }
    for directory, suffixes in (
        ("ci", {".py", ".json"}),
        ("tests", {".py", ".json"}),
        ("docs", {".md"}),
    ):
        required.update(
            path.relative_to(repo_root).as_posix()
            for path in (repo_root / directory).rglob("*")
            if path.is_file()
            and path.suffix in suffixes
            and "__pycache__" not in path.parts
        )
    return required


def validate_sdist(sdist_path, repo_root=ROOT):
    baseline, version = validate_sources(repo_root)
    root_name = f"pystove-{version}"
    files = {}
    seen = set()
    with tarfile.open(sdist_path, "r:gz") as archive:
        for member in archive.getmembers():
            path = safe_archive_name(member.name)
            if member.name in seen:
                raise ValidationError("Duplicate sdist archive member")
            seen.add(member.name)
            if path.parts[0] != root_name:
                raise ValidationError("Sdist members must share the expected root")
            if member.isdir():
                continue
            if not member.isfile():
                raise ValidationError(
                    "Sdist must contain only regular files/directories"
                )
            if len(path.parts) < 2:
                raise ValidationError("Sdist root must be a directory")
            name = PurePosixPath(*path.parts[1:]).as_posix()
            with archive.extractfile(member) as stream:
                files[name] = stream.read()
    required = required_sdist_sources(repo_root) | {
        name for name in baseline["runtime_sha256"] if name.startswith("pystove/")
    }
    missing = required - files.keys()
    if missing:
        raise ValidationError(f"Sdist missing required sources: {sorted(missing)}")
    for name in required_sdist_sources(repo_root):
        if files[name] != (Path(repo_root) / name).read_bytes():
            raise ValidationError(f"Sdist source differs from checkout: {name}")
    for name in baseline["runtime_sha256"]:
        if name in files:
            validate_runtime_source(name, files[name], baseline)
    if version_assignment(files["pystove/version.py"]).value != version:
        raise ValidationError("Sdist runtime version differs from source")
    if "PKG-INFO" not in files:
        raise ValidationError("Sdist is missing PKG-INFO")
    validate_metadata(files["PKG-INFO"], version, baseline)


def distribution_paths(dist_dir):
    dist_dir = Path(dist_dir)
    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValidationError(
            "Distribution directory must contain one wheel and one sdist"
        )
    return wheels[0], sdists[0]


def validate_distributions(dist_dir, repo_root=ROOT):
    wheel, sdist = distribution_paths(dist_dir)
    validate_wheel(wheel, repo_root)
    validate_sdist(sdist, repo_root)
    return wheel, sdist


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args()
    wheel, sdist = validate_distributions(args.dist_dir, args.repo_root)
    print(
        f"Validated frozen runtime, wheel RECORD and sdist: {wheel.name}, {sdist.name}"
    )


if __name__ == "__main__":
    main()
