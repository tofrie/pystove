"""Release-only checks: identity, collision rejection and exact installed bytes."""

from email.parser import BytesParser
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

from ci import check_release_install as gate, validate_package as validator

ROOT = Path(__file__).resolve().parents[1]


def distribution(name, version=gate.VERSION, site=None):
    return SimpleNamespace(
        metadata={"Name": name}, version=version,
        locate_file=lambda name: site / name,
    )


@pytest.mark.parametrize("names", [
    ["pystove"], ["PYSTOVE", "saynwerk-pystove"],
    ["saynwerk_pystove", "pystove"],
])
def test_original_distribution_blocks_before_shared_import(monkeypatch, names):
    monkeypatch.setattr(
        gate.metadata, "distributions", lambda: map(distribution, names)
    )
    monkeypatch.setattr(gate, "import_module", lambda _: pytest.fail("unsafe import"))
    with pytest.raises(ValueError, match="Original pystove"):
        gate.verify_install("unused.whl")
    with pytest.raises(ValueError, match="Original pystove"):
        gate.check_distributions(empty=True)


@pytest.mark.parametrize("names", [[], ["saynwerk-pystove", "saynwerk_pystove"]])
def test_missing_or_duplicate_distribution_rejected(monkeypatch, names):
    monkeypatch.setattr(
        gate.metadata, "distributions", lambda: map(distribution, names)
    )
    with pytest.raises(ValueError, match="exactly one"):
        gate.check_distributions()


def test_empty_preflight_rejects_unmanaged_namespace(monkeypatch):
    monkeypatch.setattr(gate.metadata, "distributions", lambda: [])
    monkeypatch.setattr(gate.util, "find_spec", lambda _: object())
    with pytest.raises(ValueError, match="already contains"):
        gate.check_distributions(empty=True)
    monkeypatch.setattr(gate.util, "find_spec", lambda _: None)
    gate.check_distributions(empty=True)


@pytest.mark.parametrize("mutation", [None, "bytes", "extra", "origin", "version"])
def test_installed_artifact_must_match_wheel(tmp_path, monkeypatch, mutation):
    site = tmp_path / "site-packages"
    names = ["pystove/__init__.py", "pystove/pystove.py", "pystove/version.py"]
    info = f"saynwerk_pystove-{gate.VERSION}.dist-info/METADATA"
    content = {name: (ROOT / name).read_bytes() for name in names}
    content[info] = f"Name: {gate.NAME}\nVersion: {gate.VERSION}\n".encode()
    wheel = tmp_path / "release.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, data in content.items():
            archive.writestr(name, data)
            path = site / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    dist = distribution(gate.NAME, site=site)
    monkeypatch.setattr(gate.metadata, "distributions", lambda: [dist])
    monkeypatch.setattr(gate.sysconfig, "get_path", lambda _: str(site))
    monkeypatch.setattr(gate.sys, "prefix", str(tmp_path))
    modules = {
        "pystove": SimpleNamespace(__file__=site / names[0]),
        "pystove.pystove": SimpleNamespace(__file__=site / names[1]),
        "pystove.version": SimpleNamespace(
            __file__=site / names[2], __version__=gate.VERSION,
        ),
    }
    monkeypatch.setattr(gate, "import_module", modules.__getitem__)
    if mutation == "bytes":
        (site / names[1]).write_bytes(b"unreviewed source")
    elif mutation == "extra":
        (site / "pystove/extra.py").write_bytes(b"")
    elif mutation == "origin":
        modules["pystove"].__file__ = tmp_path / "wrong/__init__.py"
    elif mutation == "version":
        dist.version = "0.3a1"
    if mutation is None:
        assert len(gate.verify_install(wheel)) == 64
    else:
        with pytest.raises(ValueError):
            gate.verify_install(wheel)


@pytest.mark.parametrize("field,value", [
    ("Name", "pystove"), ("Version", "0.3a2.dev0"),
    ("Maintainer", ""), ("Project-URL", ""),
])
def test_release_metadata_rejects_wrong_identity(field, value):
    values = {
        "Name": "saynwerk-pystove", "Version": "0.3.0rc2",
        "Maintainer": "Saynwerk", "Requires-Dist": "aiohttp",
        "Project-URL": "Original project, https://github.com/mvn23/pystove",
    }
    values[field] = value
    data = "".join(f"{key}: {value}\n" for key, value in values.items()).encode()
    assert BytesParser().parsebytes(data)[field] == value
    with pytest.raises(validator.ValidationError):
        validator.validate_metadata(data, gate.VERSION, validator.load_baseline())


@pytest.mark.parametrize("change", [None, "failure", "error", "missing", "skip"])
def test_release_xfail_gate_checks_exact_results(tmp_path, change):
    import xml.etree.ElementTree as ET

    from ci.check_test_results import KNOWN, verify

    root = ET.Element("testsuite")
    for name in sorted(KNOWN):
        case = ET.SubElement(
            root, "testcase", classname="tests.test_known_failures", name=name,
        )
        ET.SubElement(case, "skipped", type="pytest.xfail")
    passed = ET.SubElement(root, "testcase", name="a_passing_test")
    if change in {"failure", "error"}:
        ET.SubElement(passed, change)
    elif change == "missing":
        root.remove(root[0])
    elif change == "skip":
        root[0][0].set("type", "pytest.skip")
    path = tmp_path / "results.xml"
    ET.ElementTree(root).write(path)
    if change is None:
        assert verify(path) == 1
    else:
        with pytest.raises(ValueError):
            verify(path)
