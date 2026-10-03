import ast
from pathlib import Path

from setuptools import setup

ROOT = Path(__file__).resolve().parent


def read_version():
    """Read the single version source without importing runtime dependencies."""
    tree = ast.parse((ROOT / "pystove" / "version.py").read_text(encoding="utf-8"))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in statement.targets
        ):
            value = ast.literal_eval(statement.value)
            if isinstance(value, str):
                return value
    raise ValueError("pystove/version.py must define a literal __version__ string")


def read(fname):
    return (ROOT / fname).read_text(encoding="utf-8")


setup(
    name="pystove",
    version=read_version(),
    author="Milan van Nugteren",
    author_email="milan@network23.nl",
    description=("A library to interface with HWAM wood burning stoves."),
    license="GPLv3+",
    keywords="stove hwam smartcontrol",
    url="https://github.com/mvn23/pystove",
    packages=["pystove"],
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    install_requires=[
        "aiohttp",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Software Development :: Libraries",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    ],
)
