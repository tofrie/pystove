"""Build metadata, wheel and sdist with no runtime dependencies installed."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile

from build import ProjectBuilder
from build.env import DefaultIsolatedEnv
from packaging.requirements import Requirement
from validate_package import (
    ROOT,
    load_baseline,
    read_version,
    validate_distributions,
    validate_metadata,
)


def assert_no_aiohttp(environment, phase):
    subprocess.run(
        [
            environment.python_executable,
            "-I",
            "-c",
            "import importlib.util; "
            "assert importlib.util.find_spec('aiohttp') is None, "
            "'Runtime dependency aiohttp leaked into isolated build'",
        ],
        check=True,
    )
    print(f"Isolated build: aiohttp absent {phase}", flush=True)


def backend_pins(repo_root):
    pins = {}
    for line in (repo_root / "requirements-dev.txt").read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        requirement = Requirement(line)
        if requirement.name in {"setuptools", "wheel"}:
            pins[requirement.name] = requirement
    return pins


def install_backend_tools(environment, requirements, pins):
    locked = set()
    for value in requirements:
        requirement = Requirement(value)
        if requirement.name not in pins or requirement.extras or requirement.url:
            raise RuntimeError(f"Unexpected isolated build requirement: {value}")
        pin = pins[requirement.name]
        versions = list(pin.specifier)
        if len(versions) != 1 or versions[0].operator != "==":
            raise RuntimeError(f"Build tool must be exactly pinned: {pin}")
        if versions[0].version not in requirement.specifier:
            raise RuntimeError(
                f"Build requirement conflicts with development pin: {value}"
            )
        locked.add(str(pin))
    if locked:
        environment.install(locked)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--wheelhouse", type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    dist_dir = args.dist_dir.resolve()
    dist_dir.mkdir(parents=True, exist_ok=True)
    if args.wheelhouse:
        os.environ["PIP_NO_INDEX"] = "1"
        os.environ["PIP_FIND_LINKS"] = str(args.wheelhouse.resolve())
    pins = backend_pins(repo_root)
    with DefaultIsolatedEnv() as environment:
        assert_no_aiohttp(environment, "before installing build tools")
        builder = ProjectBuilder.from_isolated_env(environment, str(repo_root))
        install_backend_tools(environment, builder.build_system_requires, pins)
        assert_no_aiohttp(environment, "after installing build tools")
        for distribution in ("wheel", "sdist"):
            install_backend_tools(
                environment, builder.get_requires_for_build(distribution), pins
            )
        assert_no_aiohttp(environment, "after querying backend requirements")
        with tempfile.TemporaryDirectory(prefix="pystove-metadata-") as metadata_dir:
            prepared = builder.prepare("wheel", metadata_dir)
            if prepared is None:
                raise RuntimeError(
                    "Backend did not implement wheel metadata preparation"
                )
            validate_metadata(
                (Path(prepared) / "METADATA").read_bytes(),
                read_version(repo_root),
                load_baseline(repo_root),
            )
            assert_no_aiohttp(environment, "after preparing metadata")
            builder.build("wheel", str(dist_dir), metadata_directory=prepared)
        assert_no_aiohttp(environment, "after building the wheel")
        builder.build("sdist", str(dist_dir))
        assert_no_aiohttp(environment, "after building the sdist")
    validate_distributions(dist_dir, repo_root)
    print("Isolated metadata, wheel and sdist builds passed without aiohttp")


if __name__ == "__main__":
    main()
