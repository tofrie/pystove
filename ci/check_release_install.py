"""Fail closed on namespace collisions; verify a clean install against its wheel.

Run with the target environment's python -I, before (--empty) and after install.
This is a release gate, not a pip conflict mechanism or a runtime import hook.
"""

import argparse
from email.parser import BytesParser
import hashlib
from importlib import import_module, metadata, util
from pathlib import Path
import re
import sys
import sysconfig
import zipfile

NAME = "saynwerk-pystove"
VERSION = "0.3.0rc1"


def normalized(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def check_distributions(*, empty=False):
    """Reject an original distribution before importing the shared namespace."""
    found = [
        dist for dist in metadata.distributions()
        if normalized(dist.metadata["Name"] or "") in {"pystove", NAME}
    ]
    if any(normalized(dist.metadata["Name"]) == "pystove" for dist in found):
        raise ValueError(
            "Original pystove distribution present; use a clean environment"
        )
    if empty:
        if found or util.find_spec("pystove") is not None:
            raise ValueError("Release environment already contains pystove code")
        return None
    if len(found) != 1 or found[0].version != VERSION:
        raise ValueError("Expected exactly one saynwerk-pystove==0.3.0rc1 distribution")
    return found[0]


def verify_install(wheel):
    dist = check_distributions()
    site = Path(sysconfig.get_path("purelib")).resolve()
    if (
        sys.prefix == sys.base_prefix
        or not site.is_relative_to(Path(sys.prefix).resolve())
    ):
        raise ValueError("A private virtual environment is required")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        info = f"saynwerk_pystove-{VERSION}.dist-info/METADATA"
        meta = BytesParser().parsebytes(archive.read(info))
        if meta.get_all("Name") != [NAME] or meta.get_all("Version") != [VERSION]:
            raise ValueError("Wheel identity mismatch")
        expected = {name for name in names if name.startswith("pystove/")}
        if expected != {
            "pystove/__init__.py", "pystove/pystove.py", "pystove/version.py",
        }:
            raise ValueError("Unexpected wheel package inventory")
        actual = {
            "pystove/" + str(path.relative_to(site / "pystove")).replace("\\", "/")
            for path in (site / "pystove").rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        if actual != expected:
            raise ValueError("Installed package inventory differs from wheel")
        for name in expected | {info}:
            path = Path(dist.locate_file(name)).resolve()
            if path != (site / name).resolve() or not path.is_relative_to(site):
                raise ValueError("Installed artifact escaped the private environment")
            if path.read_bytes() != archive.read(name):
                raise ValueError(f"Installed artifact differs from wheel: {name}")
        for name in ("pystove", "pystove.pystove", "pystove.version"):
            module = import_module(name)
            relative = (
                "pystove/__init__.py" if name == "pystove"
                else name.replace(".", "/") + ".py"
            )
            if Path(module.__file__).resolve() != (site / relative).resolve():
                raise ValueError("Import resolved outside the verified artifact")
        if import_module("pystove.version").__version__ != VERSION:
            raise ValueError("Imported version mismatch")
    return hashlib.sha256(Path(wheel).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--empty", action="store_true")
    group.add_argument("--wheel", type=Path)
    args = parser.parse_args()
    if args.empty:
        check_distributions(empty=True)
        print("Release environment: no pystove distribution or namespace present")
    else:
        digest = verify_install(args.wheel)
        print(
            f"Verified {NAME}=={VERSION}; exclusive pystove import; "
            f"wheel SHA256 {digest}"
        )


if __name__ == "__main__":
    main()
