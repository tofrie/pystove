"""H6: only three errors, only while reading four POST command responses."""

import asyncio
from types import SimpleNamespace

import aiohttp
import pytest

from pystove import pystove as runtime
from tests.conftest import FakeResponse, FakeSession
from tests.test_post_response_validation import POST_CASES, POST_IDS

APPROVED = [aiohttp.ClientPayloadError, aiohttp.ServerDisconnectedError, TimeoutError]


class BoundaryResponse(FakeResponse):
    """Distinguish context entry, body read and context exit."""

    def __init__(self, stage, error, events):
        super().__init__(
            body='{"response":"OK","private":"body-secret"}',
            enter_error=error if stage == "enter" else None,
            text_error=error if stage == "read" else None,
        )
        self.stage, self.error, self.events = stage, error, events

    async def __aenter__(self):
        self.events.append("enter")
        return await super().__aenter__()

    async def text(self):
        self.events.append("read")
        return await super().text()

    async def __aexit__(self, *args):
        self.events.append("exit")
        await super().__aexit__(*args)
        if self.stage == "exit":
            raise self.error


class BoundarySession(FakeSession):
    def __init__(self, stage, error):
        super().__init__()
        self.events = []
        self.stage, self.error = stage, error
        self.response = BoundaryResponse(stage, error, self.events)
        self.responses.append(("POST", None, self.response))

    def _request(self, method, url, kwargs):
        self.events.append("request")
        response = super()._request(method, url, kwargs)
        if self.stage == "request":
            raise self.error
        return response


async def assert_propagates(operation, error):
    # Catch inside the coroutine so KeyboardInterrupt/SystemExit cannot escape
    # through asyncio's runner and abort or contaminate the surrounding suite.
    with pytest.raises(type(error)) as raised:
        await operation
    assert raised.value is error


@pytest.mark.parametrize(("method", "arguments"), POST_CASES, ids=POST_IDS)
@pytest.mark.parametrize("error_type", APPROVED)
@pytest.mark.parametrize("stage", ["request", "enter", "read", "exit"])
def test_only_response_body_errors_are_handled(
    stove, method, arguments, error_type, stage, caplog
):
    error = error_type("error-secret")
    session = BoundarySession(stage, error)
    stove._session = session
    before = vars(stove).copy()
    operation = getattr(stove, method)(*arguments)
    if stage == "read":
        assert asyncio.run(operation) is False
        assert session.response.entered and session.response.exited
        assert len(caplog.records) <= 1
        assert all(record.exc_info is None for record in caplog.records)
        assert "error-secret" not in caplog.text
        assert "body-secret" not in caplog.text
    else:
        asyncio.run(assert_propagates(operation, error))
    expected_events = {
        "request": ["request"],
        "enter": ["request", "enter"],
        "read": ["request", "enter", "read", "exit"],
        "exit": ["request", "enter", "read", "exit"],
    }
    assert session.events == expected_events[stage]
    assert len(session.calls) == 1  # Never resend an unconfirmed command.
    assert vars(stove) == before  # No inferred local stove state.


@pytest.mark.parametrize(("method", "arguments"), POST_CASES, ids=POST_IDS)
@pytest.mark.parametrize("error_type", APPROVED)
def test_request_serialization_errors_propagate(
    stove, session, method, arguments, error_type, monkeypatch
):
    error = error_type("serialization failure")

    def fail_serialization(*args, **kwargs):
        raise error

    monkeypatch.setattr(runtime.json, "dumps", fail_serialization)
    asyncio.run(assert_propagates(getattr(stove, method)(*arguments), error))
    assert session.calls == []


@pytest.mark.parametrize(("method", "arguments"), POST_CASES, ids=POST_IDS)
@pytest.mark.parametrize(
    "error_type",
    [aiohttp.ClientError, aiohttp.ClientOSError, asyncio.CancelledError,
     MemoryError, KeyboardInterrupt, SystemExit, RuntimeError, TypeError],
)
def test_other_body_read_errors_propagate(stove, method, arguments, error_type):
    error = error_type("unapproved failure")
    session = BoundarySession("read", error)
    stove._session = session
    asyncio.run(assert_propagates(getattr(stove, method)(*arguments), error))
    assert session.events == ["request", "enter", "read", "exit"]
    assert session.response.exited
    assert len(session.calls) == 1


@pytest.mark.parametrize("error_type", APPROVED)
@pytest.mark.parametrize("stage", ["request", "enter", "read", "exit"])
def test_non_command_post_still_propagates(stove, error_type, stage):
    error = error_type("file response failure")
    session = BoundarySession(stage, error)
    stove._session = session
    asyncio.run(assert_propagates(
        stove._post("http://stove.test/read_open_file", {"file_name": "info.xml"}),
        error,
    ))
    assert len(session.calls) == 1


@pytest.mark.parametrize("error_type", APPROVED)
@pytest.mark.parametrize(
    ("method", "arguments"),
    [
        ("start", ()),
        ("set_night_lowering", (True,)),
        ("set_remote_refill_alarm", ()),
        ("set_night_lowering_hours", ()),
    ],
)
def test_get_commands_and_preliminary_gets_still_propagate(
    stove, session, error_type, method, arguments
):
    error = error_type("GET failure")
    session.queue_text("", method="GET", text_error=error)
    asyncio.run(assert_propagates(getattr(stove, method)(*arguments), error))
    assert len(session.calls) == 1
    assert session.calls[0][0] == "GET"


@pytest.mark.parametrize(("method", "arguments"), POST_CASES, ids=POST_IDS)
@pytest.mark.parametrize("stage", ["request", "enter", "read", "exit"])
def test_legacy_connector_error_handling_is_preserved(stove, method, arguments, stage):
    connection = SimpleNamespace(host="stove.test", port=80, ssl=False)
    error = aiohttp.ClientConnectorError(connection, ConnectionRefusedError(61, "test"))
    session = BoundarySession(stage, error)
    stove._session = session
    assert asyncio.run(getattr(stove, method)(*arguments)) is False
    assert len(session.calls) == 1


def test_command_request_path_matches_unchanged_post_except_body_catch():
    """Freeze the duplicated request mechanics against the unchanged file path."""
    import ast
    import inspect
    import textwrap

    previous = ast.parse(textwrap.dedent(inspect.getsource(runtime.Stove._post)))
    current = ast.parse(textwrap.dedent(inspect.getsource(runtime.Stove._post_command)))
    legacy_method, command_method = previous.body[0], current.body[0]
    command_method.name = legacy_method.name
    command_method.body[0] = legacy_method.body[0]  # Descriptive docstring only.
    response_context = command_method.body[1].body[0]
    body_catch = response_context.body[0]
    assert isinstance(body_catch, ast.Try)
    assert not body_catch.orelse and not body_catch.finalbody
    assert len(body_catch.handlers) == 1
    handler = body_catch.handlers[0]
    assert ast.unparse(handler.type) == (
        "(aiohttp.ClientPayloadError, aiohttp.ServerDisconnectedError, TimeoutError)"
    )
    assert len(handler.body) == 1
    assert ast.unparse(handler.body[0]) == "return None"
    response_context.body = body_catch.body
    assert ast.dump(current, include_attributes=False) == ast.dump(
        previous, include_attributes=False
    )
