"""Run the compatibility tests outside the checkout against an installed wheel."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv

if __package__:
    from .validate_package import ROOT, ValidationError, validate_wheel
else:
    from validate_package import ROOT, ValidationError, validate_wheel

CONTRACT_TESTS = (
    "test_contract_api.py",
    "test_contract_commands.py",
    "test_create_lifecycle.py",
    "test_status_validation.py",
    "test_known_failures.py",
)


def runtime_configuration(python, environment, cwd):
    """Capture runtime identity and active package directories under isolation."""
    script = """
import json
import sys
from pathlib import Path
import aiohttp

package_directories = []
for entry in sys.path:
    path = Path(entry).resolve()
    if path.name in {'site-packages', 'dist-packages'} and path.is_dir():
        if str(path) not in package_directories:
            package_directories.append(str(path))
print(json.dumps({
    'identity': [aiohttp.__version__, str(Path(aiohttp.__file__).resolve())],
    'site_packages': package_directories,
}))
"""
    result = subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            script,
        ],
        env=environment,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def runtime_identity(python, environment, cwd):
    return runtime_configuration(python, environment, cwd)["identity"]


def link_parent_site_packages(python, configuration, environment, cwd):
    """Append active parent sites after child-local packages, without .pth code."""
    result = subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            "import json, sys, sysconfig; "
            "print(json.dumps([sys.prefix, sysconfig.get_path('purelib')]))",
        ],
        env=environment,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )
    prefix, site_packages = map(Path, json.loads(result.stdout))
    if not site_packages.resolve().is_relative_to(prefix.resolve()):
        raise RuntimeError("Child site-packages is outside its virtual environment")
    directories = configuration["site_packages"]
    origin = Path(configuration["identity"][1])
    if not any(origin.is_relative_to(Path(directory)) for directory in directories):
        raise RuntimeError("Parent aiohttp is outside its active site-packages")
    if any("\n" in directory or "\r" in directory for directory in directories):
        raise RuntimeError("Parent site-packages path contains a newline")
    site_packages.mkdir(parents=True, exist_ok=True)
    (site_packages / "pystove_parent_runtime.pth").write_text(
        "\n".join(directories) + "\n", encoding="utf-8"
    )
    return site_packages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--wheelhouse", type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    wheels = sorted(args.dist_dir.resolve().glob("*.whl"))
    if len(wheels) != 1:
        raise ValidationError("Wheel test directory must contain exactly one wheel")
    validate_wheel(wheels[0], repo_root)
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    pip_options = []
    if args.wheelhouse:
        pip_options = ["--no-index", "--find-links", str(args.wheelhouse.resolve())]
    with tempfile.TemporaryDirectory(prefix="pystove-wheel-tests-") as directory:
        temporary_root = Path(directory)
        wheel_environment = temporary_root / "venv"
        # No ensurepip is needed: the already pinned parent pip targets this
        # environment with --python. This also works when ensurepip is absent.
        venv.EnvBuilder(with_pip=False, system_site_packages=False).create(
            wheel_environment
        )
        python = wheel_environment / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        work = temporary_root / "contract"
        work.mkdir()
        shutil.copytree(
            repo_root / "tests",
            work / "tests",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        shutil.copy2(repo_root / "pyproject.toml", work / "pyproject.toml")
        parent_runtime = runtime_configuration(sys.executable, environment, work)
        runtime_before = parent_runtime["identity"]
        link_parent_site_packages(python, parent_runtime, environment, work)
        if runtime_identity(python, environment, work) != runtime_before:
            raise RuntimeError("Child environment did not preserve parent aiohttp")
        install = [
            sys.executable,
            "-I",
            "-m",
            "pip",
            "--python",
            str(python),
            "install",
            "--no-deps",
            "--ignore-installed",
            "--no-cache-dir",
            "--disable-pip-version-check",
            "--no-input",
            *pip_options,
        ]
        subprocess.run(
            [*install, "-r", str(repo_root / "requirements-dev.txt")],
            env=environment,
            cwd=work,
            check=True,
        )
        subprocess.run(
            [*install, str(wheels[0])], env=environment, cwd=work, check=True
        )
        if runtime_identity(python, environment, work) != runtime_before:
            raise RuntimeError("Wheel tests changed the pre-existing aiohttp runtime")
        script = """
import json
import sys
import sysconfig
from pathlib import Path
import pystove
import pytest

origin = Path(pystove.__file__).resolve()
site_packages = Path(sysconfig.get_path("purelib")).resolve()
checkout = Path(sys.argv[1]).resolve()
parent_sites = {Path(entry).resolve() for entry in json.loads(sys.argv[2])}
assert site_packages.is_relative_to(Path(sys.prefix).resolve())
assert origin.is_relative_to(site_packages), (origin, site_packages)
assert not origin.is_relative_to(checkout), origin
for entry in sys.path:
    path = Path(entry).resolve()
    assert not path.is_relative_to(checkout) or path in parent_sites, entry
print(f"Testing installed wheel: {origin}", flush=True)
raise SystemExit(pytest.main(sys.argv[3:]))
"""
        subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                script,
                str(repo_root),
                json.dumps(parent_runtime["site_packages"]),
                "-q",
                *(str(work / "tests" / name) for name in CONTRACT_TESTS),
            ],
            env=environment,
            cwd=work,
            check=True,
        )
        if runtime_identity(python, environment, work) != runtime_before:
            raise RuntimeError("Contract tests changed the aiohttp runtime")


if __name__ == "__main__":
    main()
