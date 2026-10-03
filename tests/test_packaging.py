"""Exercise packaging safeguards without importing a rebuilt source runtime."""

import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import venv
import zipfile

import pytest

from ci import test_wheel as wheel_runner, validate_package as validator

ROOT = Path(__file__).resolve().parents[1]


def test_wheel_environment_keeps_parent_only_runtime_and_child_package_first(tmp_path):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    parent = tmp_path / "parent"
    child = tmp_path / "child"
    builder = venv.EnvBuilder(with_pip=False, system_site_packages=False)
    builder.create(parent)
    builder.create(child)
    executable = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    parent_python, child_python = parent / executable, child / executable
    result = subprocess.run(
        [
            str(parent_python),
            "-I",
            "-c",
            "import sysconfig; print(sysconfig.get_path('purelib'))",
        ],
        env=environment,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    parent_site = Path(result.stdout.strip())
    (parent_site / "aiohttp").mkdir()
    (parent_site / "aiohttp" / "__init__.py").write_text(
        "from parent_runtime_dependency import VERSION\n__version__ = VERSION\n",
        encoding="utf-8",
    )
    (parent_site / "parent_runtime_dependency.py").write_text(
        "VERSION = 'parent-only-runtime'\n", encoding="utf-8"
    )
    (parent_site / "pystove").mkdir()
    (parent_site / "pystove" / "__init__.py").write_text(
        "ORIGIN = 'parent-package-must-not-win'\n", encoding="utf-8"
    )
    configuration = wheel_runner.runtime_configuration(
        parent_python, environment, tmp_path
    )
    assert configuration["identity"][0] == "parent-only-runtime"
    assert Path(configuration["identity"][1]).is_relative_to(parent_site)
    child_site = wheel_runner.link_parent_site_packages(
        child_python, configuration, environment, tmp_path
    )
    (child_site / "pystove").mkdir()
    (child_site / "pystove" / "__init__.py").write_text(
        "ORIGIN = 'child-wheel'\n", encoding="utf-8"
    )
    identity = wheel_runner.runtime_identity(child_python, environment, tmp_path)
    assert identity == configuration["identity"]
    result = subprocess.run(
        [
            str(child_python),
            "-I",
            "-c",
            "import json, pystove; "
            "print(json.dumps([pystove.ORIGIN, pystove.__file__]))",
        ],
        env=environment,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    label, origin = json.loads(result.stdout)
    assert label == "child-wheel"
    assert Path(origin).is_relative_to(child_site)


def metadata_bytes(*, extra="", requirement="aiohttp"):
    return (
        "Metadata-Version: 2.4\n"
        "Name: pystove\n"
        f"Version: {validator.read_version(ROOT)}\n"
        f"Requires-Dist: {requirement}\n"
        f"{extra}\n"
    ).encode()


def write_wheel(path, *, metadata=None, mutate=None, corrupt_record=None):
    baseline = validator.load_baseline(ROOT)
    version = validator.read_version(ROOT)
    prefix = f"pystove-{version}.dist-info"
    files = {
        name: (ROOT / name).read_bytes()
        for name in baseline["runtime_sha256"]
        if name.startswith("pystove/")
    }
    files[f"{prefix}/METADATA"] = metadata or metadata_bytes()
    files[f"{prefix}/WHEEL"] = (
        b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    )
    if mutate:
        mutate(files)
    record_name = f"{prefix}/RECORD"
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    for name, data in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
        writer.writerow([name, "sha256=" + digest.decode("ascii"), len(data)])
    writer.writerow([record_name, "", ""])
    files[record_name] = buffer.getvalue().encode()
    if corrupt_record:
        corrupt_record(files)
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)


def write_sdist(path, *, omit=None, mutate=None, special=None):
    baseline = validator.load_baseline(ROOT)
    version = validator.read_version(ROOT)
    names = validator.required_sdist_sources(ROOT) | {
        name for name in baseline["runtime_sha256"] if name.startswith("pystove/")
    }
    files = {name: (ROOT / name).read_bytes() for name in names if name != omit}
    files["PKG-INFO"] = metadata_bytes()
    if mutate:
        mutate(files)
    with tarfile.open(path, "w:gz") as archive:
        for name, data in files.items():
            member = tarfile.TarInfo(f"pystove-{version}/{name}")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        if special:
            archive.addfile(special)


def test_runtime_and_cli_match_all_reviewed_scopes():
    baseline, version = validator.validate_sources(ROOT)
    assert version != baseline["version"]
    assert ".dev" in version


def test_historical_baseline_h3_and_h4_hashes_are_preserved():
    baseline = validator.load_baseline(ROOT)
    assert baseline["commit"] == "6d2f7844d3fa49a339820c446aa47ba29e60e94a"
    assert baseline["version"] == "0.3a1"
    assert baseline["runtime_sha256"] == {
        "pystove/__init__.py": (
            "d72dcfa678bc6194a5f3aedb7379d2beb3a1392f9696d22cbca16bb1d5358bdf"
        ),
        "pystove/pystove.py": (
            "728568447d4442b2056f9cc80f12fe43e08f3d97c86160105218f02925ed7445"
        ),
        "pystove/version.py": (
            "f9ed531d812e7ef01ee6a101b74698cc0705647d07a11aca41b748a578828914"
        ),
        "pystove_cli.py": (
            "974234ea3eeb6f7e2a5a2110b4a79a6592df9efd34f6cc9f74dfdb3f52c4da0d"
        ),
    }
    assert baseline["reviewed_runtime_changes"]["H3"]["unchanged_source_sha256"] == (
        "37ae04cf80918b39077325f0201a75474d571196f30700b1d44e99dfbd92fb3e"
    )
    assert baseline["reviewed_runtime_changes"]["H3"]["source_sha256"] == (
        "92043ef713a67a6dc8fa6d4d3f9cea1f386f3f736f97584bb47f8257f35d66ac"
    )
    assert baseline["reviewed_runtime_changes"]["H4"]["unchanged_source_sha256"] == (
        "4174cf69733cf7b6cd474c9e009112568ed76ea718e8c9b2e56b42aacda4e02e"
    )


def test_h3_body_mutation_requires_new_explicit_reviewed_source_hash():
    baseline = validator.load_baseline(ROOT)
    source = (ROOT / "pystove/pystove.py").read_bytes()
    changed = source.replace(
        b'"""Async create the Stove object."""',
        b'"""Unreviewed lifecycle edit."""',
        1,
    )
    assert changed != source
    assert validator.lifecycle_scope_hash(changed) == validator.lifecycle_scope_hash(
        source
    )
    with pytest.raises(
        validator.ValidationError, match="outside H6 POST response reading"
    ):
        validator.validate_runtime_source("pystove/pystove.py", changed, baseline)


def test_historical_h3_approval_cannot_be_rewritten_for_h4():
    baseline = validator.load_baseline(ROOT)
    source = (ROOT / "pystove/pystove.py").read_bytes()
    changed = source.replace(b'DATA_LEVEL = "level"', b'DATA_LEVEL = "changed"', 1)
    assert changed != source
    baseline["reviewed_runtime_changes"]["H3"]["source_sha256"] = hashlib.sha256(
        changed
    ).hexdigest()
    with pytest.raises(
        validator.ValidationError, match="Historical H3 approval changed"
    ):
        validator.validate_runtime_source("pystove/pystove.py", changed, baseline)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("path", "pystove/__init__.py"),
        ("method_bodies", ["Stove.create", "Stove.get_data"]),
        ("added_module_function", "another_helper"),
        ("phase1_commit", "unreviewed"),
    ],
)
def test_h3_review_cannot_be_expanded_to_another_scope(field, value):
    baseline = validator.load_baseline(ROOT)
    baseline["reviewed_runtime_changes"]["H3"][field] = value
    with pytest.raises(validator.ValidationError, match="H3 runtime scope changed"):
        validator.validate_runtime_source(
            "pystove/pystove.py", (ROOT / "pystove/pystove.py").read_bytes(), baseline
        )


def test_artifact_validation_does_not_allow_another_audit_fix():
    baseline = validator.load_baseline(ROOT)
    baseline["reviewed_runtime_changes"]["H5"] = {}
    with pytest.raises(validator.ValidationError, match="Only the reviewed H3/H4"):
        validator.validate_runtime_source(
            "pystove/pystove.py", (ROOT / "pystove/pystove.py").read_bytes(), baseline
        )


def test_h4_body_is_frozen_during_h6():
    baseline = validator.load_baseline(ROOT)
    source = (ROOT / "pystove/pystove.py").read_bytes()
    changed = source.replace(
        b"    async def get_data(self):\n",
        b"    async def get_data(self):\n        pass\n",
        1,
    )
    assert changed != source
    assert validator.status_scope_hash(changed) == validator.status_scope_hash(source)
    with pytest.raises(
        validator.ValidationError, match="outside H6 POST response reading"
    ):
        validator.validate_runtime_source("pystove/pystove.py", changed, baseline)


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        (b'DATA_LEVEL = "level"', b'DATA_LEVEL = "changed"'),
        (
            b'"""Async create the Stove object."""',
            b'"""Unreviewed H3 lifecycle edit."""',
        ),
        (b"async def get_data(self):", b"async def get_data(self, new_argument=None):"),
        (b'"Accept": "application/json"', b'"Accept": "changed"'),
        (b'STOVE_DATA_URL = "/get_stove_data"', b'STOVE_DATA_URL = "/changed"'),
        (
            b'"""Get data from url, interpret as json, return result."""',
            b'"""Unreviewed transport edit."""',
        ),
    ],
)
def test_new_h4_hash_cannot_allow_changes_outside_status_body(original, replacement):
    baseline = validator.load_baseline(ROOT)
    source = (ROOT / "pystove/pystove.py").read_bytes()
    changed = source.replace(original, replacement, 1)
    assert changed != source
    baseline["reviewed_runtime_changes"]["H4"]["source_sha256"] = hashlib.sha256(
        changed
    ).hexdigest()
    with pytest.raises(
        validator.ValidationError, match="Historical H4 approval changed"
    ):
        validator.validate_runtime_source("pystove/pystove.py", changed, baseline)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("path", "pystove/__init__.py"),
        ("method_bodies", ["Stove.get_data", "Stove._get_json"]),
        ("h3_commit", "unreviewed"),
        ("h3_source_sha256", "unreviewed"),
        ("unchanged_source_sha256", "unreviewed"),
    ],
)
def test_h4_review_cannot_be_expanded_to_another_scope(field, value):
    baseline = validator.load_baseline(ROOT)
    baseline["reviewed_runtime_changes"]["H4"][field] = value
    with pytest.raises(validator.ValidationError, match="H4 runtime scope changed"):
        validator.validate_runtime_source(
            "pystove/pystove.py", (ROOT / "pystove/pystove.py").read_bytes(), baseline
        )


def test_setup_metadata_does_not_import_runtime_dependencies(tmp_path):
    # A clean subprocess blocks every package/runtime import. Stubbing only
    # setuptools.setup exposes the real metadata computation in setup.py.
    script = """
import importlib.abc
import json
import runpy
import sys
import types

class BlockRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'aiohttp', 'pystove'}:
            raise RuntimeError(f'Packaging imported runtime dependency: {fullname}')

sys.meta_path.insert(0, BlockRuntime())
module = types.ModuleType('setuptools')
module.setup = lambda **kwargs: print(json.dumps(kwargs))
sys.modules['setuptools'] = module
runpy.run_path(sys.argv[1], run_name='__main__')
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(ROOT / "setup.py")],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    metadata = json.loads(result.stdout)
    assert metadata["name"] == "pystove"
    assert metadata["version"] == validator.read_version(ROOT)
    assert metadata["install_requires"] == ["aiohttp"]
    assert "python_requires" not in metadata
    assert "entry_points" not in metadata


def test_valid_wheel_and_sdist_pass(tmp_path):
    wheel = tmp_path / "pystove.whl"
    sdist = tmp_path / "pystove.tar.gz"
    write_wheel(wheel)
    write_sdist(sdist)
    assert validator.validate_distributions(tmp_path, ROOT) == (wheel, sdist)


def test_sdist_contains_sources_needed_to_validate_the_wheel(tmp_path):
    wheel = tmp_path / "pystove.whl"
    sdist = tmp_path / "pystove.tar.gz"
    write_wheel(wheel)
    write_sdist(sdist)
    validator.validate_sdist(sdist, ROOT)
    extracted = tmp_path / "extracted"
    # Read only regular files from the already validated synthetic archive.
    # This verifies that no checkout-only input is needed by the validators.
    with tarfile.open(sdist, "r:gz") as archive:
        for member in archive.getmembers():
            if member.isfile():
                destination = extracted / member.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as stream:
                    destination.write_bytes(stream.read())
    source_root = extracted / f"pystove-{validator.read_version(ROOT)}"
    validator.validate_sources(source_root)
    validator.validate_wheel(wheel, source_root)
    validator.validate_sdist(sdist, source_root)


@pytest.mark.parametrize(
    "requirement",
    ["aiohttp>=3.10", "aiohttp; python_version >= '3.11'", "aiohttp[speedups]"],
)
def test_wheel_rejects_runtime_dependency_contract_changes(tmp_path, requirement):
    wheel = tmp_path / "pystove.whl"
    write_wheel(wheel, metadata=metadata_bytes(requirement=requirement))
    with pytest.raises(validator.ValidationError, match="dependency contract"):
        validator.validate_wheel(wheel, ROOT)


@pytest.mark.parametrize(
    "field", ["Requires-Python: >=3.11\n", "Provides-Extra: dev\n"]
)
def test_wheel_rejects_new_python_floor_or_extras(tmp_path, field):
    wheel = tmp_path / "pystove.whl"
    write_wheel(wheel, metadata=metadata_bytes(extra=field))
    with pytest.raises(validator.ValidationError, match="must not introduce"):
        validator.validate_wheel(wheel, ROOT)


def test_wheel_rejects_runtime_changes_even_with_valid_record(tmp_path):
    wheel = tmp_path / "pystove.whl"

    def mutate(files):
        files["pystove/pystove.py"] += b"\n# accidental runtime edit\n"

    write_wheel(wheel, mutate=mutate)
    with pytest.raises(
        validator.ValidationError, match="outside H6 POST response reading"
    ):
        validator.validate_wheel(wheel, ROOT)


def test_wheel_rejects_cli_packaging(tmp_path):
    wheel = tmp_path / "pystove.whl"

    def mutate(files):
        files["pystove_cli.py"] = (ROOT / "pystove_cli.py").read_bytes()

    write_wheel(wheel, mutate=mutate)
    with pytest.raises(validator.ValidationError, match="inventory changed"):
        validator.validate_wheel(wheel, ROOT)


@pytest.mark.parametrize("change", ["hash", "size", "coverage"])
def test_wheel_rejects_broken_record(tmp_path, change):
    wheel = tmp_path / "pystove.whl"

    def corrupt(files):
        name = next(name for name in files if name.endswith("/RECORD"))
        rows = list(csv.reader(io.StringIO(files[name].decode())))
        if change == "hash":
            rows[0][1] = "sha256=corrupted"
        elif change == "size":
            rows[0][2] = "999999"
        else:
            rows.pop(0)
        buffer = io.StringIO(newline="")
        csv.writer(buffer).writerows(rows)
        files[name] = buffer.getvalue().encode()

    write_wheel(wheel, corrupt_record=corrupt)
    with pytest.raises(validator.ValidationError, match="RECORD"):
        validator.validate_wheel(wheel, ROOT)


@pytest.mark.parametrize(
    "missing",
    [
        "requirements-dev.txt",
        "pystove_cli.py",
        "tests/test_known_failures.py",
        "tests/test_create_lifecycle.py",
        "tests/test_status_validation.py",
        "tests/test_post_response_validation.py",
        "tests/test_post_response_transport.py",
        "tests/fixtures/h6_post_response_commands.json",
        "tests/fixtures/h4_commands.json",
        "tests/fixtures/hwam_contract.json",
        "ci/compatibility_baseline.json",
        "docs/BASELINE.md",
    ],
)
def test_sdist_rejects_missing_compatibility_evidence(tmp_path, missing):
    sdist = tmp_path / "pystove.tar.gz"
    write_sdist(sdist, omit=missing)
    with pytest.raises(validator.ValidationError, match="missing required sources"):
        validator.validate_sdist(sdist, ROOT)


@pytest.mark.parametrize(
    "name",
    [
        "../escaped",
        "/absolute",
        "pystove/../../escaped",
        "C:escaped",
        "pystove//alias",
    ],
)
def test_sdist_rejects_unsafe_paths_without_extracting(tmp_path, name):
    sdist = tmp_path / "pystove.tar.gz"
    write_sdist(sdist, special=tarfile.TarInfo(name))
    with pytest.raises(validator.ValidationError, match="Unsafe archive path"):
        validator.validate_sdist(sdist, ROOT)
    assert not (tmp_path / "escaped").exists()


def test_sdist_rejects_symbolic_links(tmp_path):
    sdist = tmp_path / "pystove.tar.gz"
    version = validator.read_version(ROOT)
    link = tarfile.TarInfo(f"pystove-{version}/linked-file")
    link.type = tarfile.SYMTYPE
    link.linkname = "../../outside"
    write_sdist(sdist, special=link)
    with pytest.raises(validator.ValidationError, match="only regular files"):
        validator.validate_sdist(sdist, ROOT)


def test_sdist_rejects_changed_cli(tmp_path):
    sdist = tmp_path / "pystove.tar.gz"

    def mutate(files):
        files["pystove_cli.py"] = (
            ROOT / "pystove_cli.py"
        ).read_bytes() + b"\n# changed\n"

    write_sdist(sdist, mutate=mutate)
    with pytest.raises(
        validator.ValidationError, match="differs from checkout: pystove_cli.py"
    ):
        validator.validate_sdist(sdist, ROOT)


def test_sdist_rejects_changed_contract_tests(tmp_path):
    sdist = tmp_path / "pystove.tar.gz"

    def mutate(files):
        files["tests/test_contract_api.py"] += b"\n# changed\n"

    write_sdist(sdist, mutate=mutate)
    with pytest.raises(validator.ValidationError, match="differs from checkout"):
        validator.validate_sdist(sdist, ROOT)


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        (b'DATA_LEVEL = "level"', b'DATA_LEVEL = "changed"'),
        (b'"Accept": "application/json"', b'"Accept": "changed"'),
        (b"data = {DATA_LEVEL: burn_level}", b"data = {DATA_LEVEL: 99}"),
        (b"async def set_time(self, new_time=None):",
         b"async def set_time(self, new_time=False):"),
        (b'url, data=json.dumps(data, separators=(",", ":"))',
         b"url, data=json.dumps(data)"),
        (b"self._session.get(url)", b"self._session.get(url, timeout=1)"),
        (b"return result.get(DATA_RESPONSE) == RESPONSE_OK",
         b"return bool(result.get(DATA_RESPONSE))"),
        (b'"""Call get_raw_data, process result before returning."""',
         b'"""Unreviewed status edit."""'),
        (b'"""Async create the Stove object."""',
         b'"""Unreviewed lifecycle edit."""'),
    ],
)
def test_new_h6_hash_cannot_change_requests_or_other_runtime(original, replacement):
    baseline = validator.load_baseline(ROOT)
    source = (ROOT / "pystove/pystove.py").read_bytes()
    changed = source.replace(original, replacement, 1)
    assert changed != source
    baseline["reviewed_runtime_changes"]["H6"]["source_sha256"] = hashlib.sha256(
        changed
    ).hexdigest()
    with pytest.raises(
        validator.ValidationError, match="Historical H6 parser approval changed"
    ):
        validator.validate_runtime_source("pystove/pystove.py", changed, baseline)


def test_h6_parser_is_frozen_during_response_read_changes():
    baseline = validator.load_baseline(ROOT)
    source = (ROOT / "pystove/pystove.py").read_bytes()
    changed = source.replace(b"except json.JSONDecodeError:", b"except Exception:", 1)
    assert changed != source
    assert validator.post_response_scope_hash(changed) == (
        validator.post_response_scope_hash(source)
    )
    with pytest.raises(
        validator.ValidationError, match="outside H6 POST response reading"
    ):
        validator.validate_runtime_source("pystove/pystove.py", changed, baseline)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("path", "pystove/__init__.py"),
        ("h4_commit", "unreviewed"),
        ("response_expressions", ["Stove._post"]),
        ("added_module_function", "another_helper"),
        ("unchanged_source_sha256", "unreviewed"),
    ],
)
def test_h6_review_cannot_be_expanded(field, value):
    baseline = validator.load_baseline(ROOT)
    baseline["reviewed_runtime_changes"]["H6"][field] = value
    with pytest.raises(validator.ValidationError, match="H6 runtime scope changed"):
        validator.validate_runtime_source(
            "pystove/pystove.py", (ROOT / "pystove/pystove.py").read_bytes(), baseline
        )


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        (b'DATA_LEVEL = "level"', b'DATA_LEVEL = "changed"'),
        (b'"Accept": "application/json"', b'"Accept": "changed"'),
        (b"data = {DATA_LEVEL: burn_level}", b"data = {DATA_LEVEL: 99}"),
        (b"async def set_time(self, new_time=None):",
         b"async def set_time(self, new_time=False):"),
        (b"self._session.get(url)", b"self._session.get(url, timeout=1)"),
        (b"return result.get(DATA_RESPONSE) == RESPONSE_OK",
         b"return bool(result.get(DATA_RESPONSE))"),
        (b'"""Call get_raw_data, process result before returning."""',
         b'"""Unreviewed status edit."""'),
        (b'"""Async create the Stove object."""',
         b'"""Unreviewed lifecycle edit."""'),
        (b"except json.JSONDecodeError:", b"except Exception:"),
        (b'"""Post data to url, return response."""',
         b'"""Unreviewed file transport edit."""'),
    ],
)
def test_new_read_hash_cannot_change_frozen_runtime(original, replacement):
    baseline = validator.load_baseline(ROOT)
    source = (ROOT / "pystove/pystove.py").read_bytes()
    changed = source.replace(original, replacement, 1)
    assert changed != source
    baseline["reviewed_runtime_changes"]["H6_POST_RESPONSE_TRANSPORT"][
        "source_sha256"
    ] = hashlib.sha256(changed).hexdigest()
    with pytest.raises(
        validator.ValidationError, match="outside H6 POST response reading"
    ):
        validator.validate_runtime_source("pystove/pystove.py", changed, baseline)


def test_command_helper_change_requires_explicit_source_hash():
    baseline = validator.load_baseline(ROOT)
    source = (ROOT / "pystove/pystove.py").read_bytes()
    changed = source.replace(
        b"                    aiohttp.ClientPayloadError,",
        b"                    aiohttp.ClientError,",
        1,
    )
    assert changed != source
    assert validator.post_transport_scope_hash(changed) == (
        validator.post_transport_scope_hash(source)
    )
    with pytest.raises(validator.ValidationError, match="Frozen runtime changed"):
        validator.validate_runtime_source("pystove/pystove.py", changed, baseline)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("path", "pystove/__init__.py"),
        ("base_commit", "unreviewed"),
        ("command_call_sites", ["Stove._identify"]),
        ("added_private_method", "Stove._post"),
        ("unchanged_source_sha256", "unreviewed"),
    ],
)
def test_response_read_review_cannot_be_expanded(field, value):
    baseline = validator.load_baseline(ROOT)
    baseline["reviewed_runtime_changes"]["H6_POST_RESPONSE_TRANSPORT"][field] = value
    with pytest.raises(validator.ValidationError, match="H6 response-read scope"):
        validator.validate_runtime_source(
            "pystove/pystove.py", (ROOT / "pystove/pystove.py").read_bytes(), baseline
        )
