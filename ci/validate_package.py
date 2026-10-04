"""Validate artifacts against 0.3a1 and the separately reviewed H3/H4/H6 fixes.

This module deliberately uses only the standard library and never imports the
package. The baseline hashes describe the published runtime, not freshly
generated expectations from the code under test. The historical H3 approval is
retained verbatim. The H4 scope hash freezes every byte of that revision outside
the existing get_data body, including all lifecycle and transport code. Each
approval also requires the exact separately reviewed full source hash. H6 restores
only four POST response expressions and removes its private parser to recover
the complete, hash-pinned H4 source; all request construction stays frozen.
The later H6 response-read scope removes only _post_command and restores four
call targets to recover the exact parser-phase source, including its parser.
The Python 3.14 approval restores only two wait expressions and their result
retrieval to recover the exact H6 response-read source, before validating history.
The info.xml approval removes only its private close helper/timeout and restores
the exact old read call, recovering the complete Python 3.14 candidate source.
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
    if "INFO_XML_CLOSE" in reviewed:
        change = reviewed["INFO_XML_CLOSE"]
        if (
            change["base_commit"] != "22b75dd8a6fcd680d2ced8747671207e62be790f"
            or change["path"] != "pystove/pystove.py"
            or change["added_private_method"] != "Stove._close_info_file"
            or change["unchanged_source_sha256"] != (
                "bc969414a87a4c41187c3718f2d9abf260536aaeeb126f4d04a6669ca8406087"
            )
        ):
            raise ValidationError("Reviewed info.xml cleanup scope changed")
        previous = dict(baseline)
        previous["reviewed_runtime_changes"] = {
            key: value for key, value in reviewed.items() if key != "INFO_XML_CLOSE"
        }
        restored = info_file_previous_source(data) if name == change["path"] else data
        validate_runtime_source(name, restored, previous)
        if name == change["path"]:
            if hashlib.sha256(restored).hexdigest() != (
                change["unchanged_source_sha256"]
            ):
                raise ValidationError("Runtime outside info.xml cleanup changed")
            if hashlib.sha256(data).hexdigest() != change["source_sha256"]:
                raise ValidationError(f"Frozen runtime changed: {name}")
        return
    if "PY314_CANCELLATION" in reviewed:
        change = reviewed["PY314_CANCELLATION"]
        if (
            change["base_commit"] != "fcb7e8ac46b1cc5d73de7c5879e49073aa21769b"
            or change["path"] != "pystove/pystove.py"
            or change["wait_sites"] != [
                "_finish_initialization_cleanup", "Stove._identify"
            ]
            or change["unchanged_source_sha256"] != (
                "ad01830a6a9ea2acd37f9271a131f5f6551becbc1fc66e8afafc637975bb5760"
            )
        ):
            raise ValidationError("Reviewed Python 3.14 lifecycle scope changed")
        previous = dict(baseline)
        previous["reviewed_runtime_changes"] = {
            key: value for key, value in reviewed.items()
            if key != "PY314_CANCELLATION"
        }
        restored = data
        if name == change["path"]:
            for current, old in (
                (b"                await asyncio.wait((cleanup,))",
                 b"                await asyncio.shield(cleanup)"),
                (b"            await asyncio.wait((group,))\n"
                 b"            group.result()",
                 b"            await asyncio.shield(group)"),
            ):
                if restored.count(current) != 1:
                    raise ValidationError("Python 3.14 wait sites changed")
                restored = restored.replace(current, old)
        # Validate every historical approval first, without rewriting its hashes.
        validate_runtime_source(name, restored, previous)
        if name == change["path"]:
            if hashlib.sha256(restored).hexdigest() != (
                change["unchanged_source_sha256"]
            ):
                raise ValidationError("Runtime outside Python 3.14 wait sites changed")
            if hashlib.sha256(data).hexdigest() != change["source_sha256"]:
                raise ValidationError(f"Frozen runtime changed: {name}")
        return
    if reviewed:
        if set(reviewed) not in (
            {"H3"}, {"H3", "H4"}, {"H3", "H4", "H6"},
            {"H3", "H4", "H6", "H6_POST_RESPONSE_TRANSPORT"},
        ):
            raise ValidationError(
                "Only the reviewed H3/H4/H6 runtime changes are allowed"
            )
        change = reviewed["H3"]
        if (
            change["path"] != "pystove/pystove.py"
            or change["method_bodies"] != ["Stove.create", "Stove._identify"]
            or change["added_module_function"] != "_finish_initialization_cleanup"
            or change["phase1_commit"]
            != "5876e2d7c381baf1dc72815a110bc2c0b2c2d8c4"
        ):
            raise ValidationError("Reviewed H3 runtime scope changed")
        if "H4" in reviewed:
            if (
                change["source_sha256"]
                != "92043ef713a67a6dc8fa6d4d3f9cea1f386f3f736f97584bb47f8257f35d66ac"
                or change["unchanged_source_sha256"]
                != "37ae04cf80918b39077325f0201a75474d571196f30700b1d44e99dfbd92fb3e"
            ):
                raise ValidationError("Historical H3 approval changed")
            status_change = reviewed["H4"]
            if (
                status_change["path"] != "pystove/pystove.py"
                or status_change["method_bodies"] != ["Stove.get_data"]
                or status_change["h3_commit"]
                != "35cc6bda8c014ca545f90f5b145b716bbcf68593"
                or status_change["h3_source_sha256"] != change["source_sha256"]
                or status_change["unchanged_source_sha256"]
                != "4174cf69733cf7b6cd474c9e009112568ed76ea718e8c9b2e56b42aacda4e02e"
            ):
                raise ValidationError("Reviewed H4 runtime scope changed")
            if "H6" in reviewed:
                if status_change["source_sha256"] != (
                    "5c22524424f60d550b059dc52994640bcfb6941e6a0ad59bec99046408cd9569"
                ):
                    raise ValidationError("Historical H4 approval changed")
                post_change = reviewed["H6"]
                if (
                    post_change["path"] != "pystove/pystove.py"
                    or post_change["h4_commit"]
                    != "82c8438ed046261c2e29bf3af01fe6f65fc89bb5"
                    or post_change["response_expressions"] != POST_RESPONSE_METHODS
                    or post_change["added_module_function"] != "_post_response_ok"
                    or post_change["unchanged_source_sha256"]
                    != status_change["source_sha256"]
                ):
                    raise ValidationError("Reviewed H6 runtime scope changed")
                if "H6_POST_RESPONSE_TRANSPORT" in reviewed:
                    if post_change["source_sha256"] != (
                        "0e01238ef052cdb501674f73e4bac79db22dd6d26c32cfa9f2e74747b435d782"
                    ):
                        raise ValidationError("Historical H6 parser approval changed")
                    transport = reviewed["H6_POST_RESPONSE_TRANSPORT"]
                    if (
                        transport["path"] != post_change["path"]
                        or transport["base_commit"]
                        != "9865615a2509aa13897f5e2b84e6a89310fa0ee3"
                        or transport["command_call_sites"] != POST_RESPONSE_METHODS
                        or transport["added_private_method"] != "Stove._post_command"
                        or transport["unchanged_source_sha256"]
                        != post_change["source_sha256"]
                    ):
                        raise ValidationError("Reviewed H6 response-read scope changed")
                    if name == transport["path"]:
                        if post_transport_scope_hash(data) != (
                            transport["unchanged_source_sha256"]
                        ):
                            raise ValidationError(
                                "Runtime outside H6 POST response reading changed"
                            )
                        expected = transport["source_sha256"]
                elif name == post_change["path"]:
                    if post_response_scope_hash(data) != (
                        post_change["unchanged_source_sha256"]
                    ):
                        raise ValidationError(
                            "Runtime outside H6 POST response decoding changed"
                        )
                    expected = post_change["source_sha256"]
            elif name == status_change["path"]:
                if status_scope_hash(data) != status_change["unchanged_source_sha256"]:
                    raise ValidationError("Runtime outside H4 get_data body changed")
                expected = status_change["source_sha256"]
        elif name == change["path"]:
            if lifecycle_scope_hash(data) != change["unchanged_source_sha256"]:
                raise ValidationError("Runtime outside H3 lifecycle bodies changed")
            expected = change["source_sha256"]
    if baseline_source_hash(name, data, baseline) != expected:
        raise ValidationError(f"Frozen runtime changed: {name}")


def info_file_previous_source(data):
    """Undo only the reviewed close helper, private deadline and read wrapper."""
    current = b'''                read_error = None
                try:
                    xml_str = await self._post(
                        "http://" + self.stove_host + STOVE_READ_OPEN_FILE_URL, data
                    )
                except BaseException as exc:
                    read_error = exc
                    info_read_error = exc
                    raise
                finally:
                    await self._close_info_file(read_error)
'''
    original = b'''                xml_str = await self._post(
                    "http://" + self.stove_host + STOVE_READ_OPEN_FILE_URL, data
                )
'''
    timeout = b"_INFO_FILE_CLOSE_TIMEOUT = 5.0\n\n"
    if data.count(current) != 1 or data.count(timeout) != 1:
        raise ValidationError("Info.xml read/cleanup boundary changed")
    data = data.replace(current, original).replace(timeout, b"")
    for current, original in (
        (b"        info_read_error = None\n\n", b""),
        (b"            nonlocal info_read_error\n", b""),
        (b'''            # A read failure can be waiting for its close when a later
            # factory cancellation arrives. Keep the original failure.
            primary = (
                info_read_error
                if isinstance(cause, asyncio.CancelledError)
                and info_read_error is not None
                else cause
            )

            async def cleanup_tasks(initial_error=primary):''',
         b"            async def cleanup_tasks(initial_error=cause):"),
        (b"            if primary is not cause:\n"
         b"                raise primary from primary.__cause__\n", b""),
    ):
        if data.count(current) != 1:
            raise ValidationError("Info.xml primary-error boundary changed")
        data = data.replace(current, original)
    tree = ast.parse(data.decode())
    stove = next(node for node in tree.body
                 if isinstance(node, ast.ClassDef) and node.name == "Stove")
    helpers = [node for node in stove.body
               if isinstance(node, ast.AsyncFunctionDef)
               and node.name == "_close_info_file"]
    if len(helpers) != 1 or helpers[0].decorator_list:
        raise ValidationError("Info.xml private close helper changed")
    lines = data.splitlines(keepends=True)
    helper = helpers[0]
    start = sum(map(len, lines[:helper.lineno - 1]))
    end = sum(map(len, lines[:helper.end_lineno + 1]))
    if lines[helper.end_lineno] != b"\n":
        raise ValidationError("Info.xml helper boundary changed")
    return data[:start] + data[end:]


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


def status_scope_hash(data):
    """Freeze H3 and all surrounding bytes; exclude only the get_data body."""
    tree = ast.parse(data.decode("utf-8"))
    stoves = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Stove"
    ]
    if len(stoves) != 1:
        raise ValidationError("H4 scope requires exactly one Stove class")
    methods = [
        node
        for node in stoves[0].body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "get_data"
    ]
    if len(methods) != 1:
        raise ValidationError("H4 scope requires one Stove.get_data")
    first, last = methods[0].body[0], methods[0].body[-1]
    lines = data.splitlines(keepends=True)
    start = sum(map(len, lines[: first.lineno - 1])) + first.col_offset
    end = sum(map(len, lines[: last.end_lineno - 1])) + last.end_col_offset
    data = data[:start] + b"<reviewed H4 get_data body>" + data[end:]
    return hashlib.sha256(data).hexdigest()


POST_RESPONSE_METHODS = [
    "Stove.set_burn_level",
    "Stove.set_remote_refill_alarm",
    "Stove.set_night_lowering_hours",
    "Stove.set_time",
]


def post_response_scope_hash(data):
    """Recover H4 bytes, allowing only a parser and four return expressions."""
    tree = ast.parse(data.decode("utf-8"))
    helpers = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_post_response_ok"
    ]
    stoves = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Stove"
    ]
    if len(helpers) != 1 or len(stoves) != 1:
        raise ValidationError("H6 requires one private parser and one Stove class")
    helper = helpers[0]
    following = tree.body[tree.body.index(helper) + 1:]
    if (
        helper.decorator_list
        or not following
        or not isinstance(following[0], ast.AsyncFunctionDef)
        or following[0].name != "_finish_initialization_cleanup"
    ):
        raise ValidationError("H6 parser must immediately precede H3 cleanup")
    lines = data.splitlines(keepends=True)
    start = sum(map(len, lines[:helper.lineno - 1]))
    end = sum(map(len, lines[:following[0].lineno - 1]))
    statement_end = (
        sum(map(len, lines[:helper.end_lineno - 1])) + helper.end_col_offset
    )
    if data[statement_end:end].strip():
        raise ValidationError("H6 parser must have only trailing whitespace")
    ranges = [(start, end, b"")]
    for qualified_name in POST_RESPONSE_METHODS:
        method_name = qualified_name.split(".")[1]
        methods = [
            node for node in stoves[0].body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == method_name
        ]
        if len(methods) != 1:
            raise ValidationError(f"H6 requires exactly one {qualified_name}")
        last = methods[0].body[-1]
        start = sum(map(len, lines[:last.lineno - 1])) + last.col_offset
        end = sum(map(len, lines[:last.end_lineno - 1])) + last.end_col_offset
        if data[start:end] != b"return _post_response_ok(json_str)":
            raise ValidationError("H6 permits only the reviewed response expression")
        ranges.append((
            start, end, b"return json.loads(json_str).get(DATA_RESPONSE) == RESPONSE_OK"
        ))
    for start, end, replacement in sorted(ranges, reverse=True):
        data = data[:start] + replacement + data[end:]
    return hashlib.sha256(data).hexdigest()


def post_transport_scope_hash(data):
    """Recover the parser-phase source, removing only its new command path."""
    tree = ast.parse(data.decode("utf-8"))
    stoves = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Stove"
    ]
    if len(stoves) != 1:
        raise ValidationError("H6 response reading requires exactly one Stove")
    stove = stoves[0]
    helpers = [
        node for node in stove.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_post_command"
    ]
    if len(helpers) != 1:
        raise ValidationError("H6 response reading requires one _post_command")
    helper = helpers[0]
    following = stove.body[stove.body.index(helper) + 1:]
    if (
        helper.decorator_list
        or not following
        or not isinstance(following[0], ast.AsyncFunctionDef)
        or following[0].name != "_post"
    ):
        raise ValidationError("H6 command helper must immediately precede _post")
    lines = data.splitlines(keepends=True)
    start = sum(map(len, lines[:helper.lineno - 1]))
    end = sum(map(len, lines[:following[0].lineno - 1]))
    statement_end = (
        sum(map(len, lines[:helper.end_lineno - 1])) + helper.end_col_offset
    )
    if data[statement_end:end].strip():
        raise ValidationError("H6 command helper must have only trailing whitespace")
    ranges = [(start, end, b"")]
    for qualified_name in POST_RESPONSE_METHODS:
        methods = [
            node for node in stove.body
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == qualified_name.split(".")[1]
        ]
        if len(methods) != 1:
            raise ValidationError(f"H6 requires exactly one {qualified_name}")
        calls = [
            node for node in ast.walk(methods[0])
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name) and node.value.id == "self"
            and node.attr == "_post_command"
        ]
        if len(calls) != 1:
            raise ValidationError("H6 requires one command call per POST setter")
        call = calls[0]
        start = sum(map(len, lines[:call.lineno - 1])) + call.col_offset
        end = sum(map(len, lines[:call.end_lineno - 1])) + call.end_col_offset
        if data[start:end] != b"self._post_command":
            raise ValidationError("H6 permits only the reviewed command call")
        ranges.append((start, end, b"self._post"))
    for start, end, replacement in sorted(ranges, reverse=True):
        data = data[:start] + replacement + data[end:]
    return hashlib.sha256(data).hexdigest()


def validate_sources(repo_root=ROOT):
    repo_root = Path(repo_root)
    baseline = load_baseline(repo_root)
    for name in baseline["runtime_sha256"]:
        validate_runtime_source(name, (repo_root / name).read_bytes(), baseline)
    version = read_version(repo_root)
    if version != "0.3.0rc1":
        raise ValidationError("Release artifacts require version 0.3.0rc1")
    release = json.loads((repo_root / "ci/release_baseline.json").read_text())
    if release["commit"] != "eec0d60a0120140171a7ef2a5b6c6005da04c51b":
        raise ValidationError("Unexpected release runtime baseline")
    for name, expected in release["runtime_sha256"].items():
        digest = baseline_source_hash(name, (repo_root / name).read_bytes(), release)
        if digest != expected:
            raise ValidationError(f"Runtime differs from eec0d60: {name}")
    return baseline, version


def validate_metadata(data, version, baseline):
    metadata = BytesParser().parsebytes(data)
    if metadata.get_all("Name") != ["saynwerk-pystove"]:
        raise ValidationError("Artifact distribution name must be saynwerk-pystove")
    if metadata.get_all("Version") != [version]:
        raise ValidationError("Artifact version differs from pystove/version.py")
    if metadata.get_all("Maintainer") != ["Saynwerk"]:
        raise ValidationError("Artifact maintainer must be Saynwerk")
    if "Original project, https://github.com/mvn23/pystove" not in metadata.get_all(
        "Project-URL", []
    ):
        raise ValidationError("Artifact must credit the original project")
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
    dist_info = f"saynwerk_pystove-{version}.dist-info"
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
        "tests/test_status_validation.py",
        "tests/test_post_response_validation.py",
        "tests/test_post_response_transport.py",
        "tests/fixtures/h6_post_response_commands.json",
        "tests/fixtures/h4_commands.json",
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
    root_name = f"saynwerk_pystove-{version}"
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
