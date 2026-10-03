"""H6 POST confirmation parsing; no transport, retry or protocol changes."""

import asyncio
from copy import deepcopy
from datetime import datetime, time
import hashlib
import json
from pathlib import Path
import textwrap

import aiohttp
import pytest

from pystove import Stove, pystove as runtime
from tests.conftest import FakeSession

POST_CASES = [
    ("set_burn_level", (3,)),
    ("set_remote_refill_alarm", (True,)),
    ("set_night_lowering_hours", (time(22, 15), time(6, 30))),
    ("set_time", (datetime(2024, 2, 29, 23, 57, 58),)),
]
POST_IDS = [name for name, _ in POST_CASES]

REPLIES = [
    ('{"response":"OK"}', True),
    (' { "response" : "OK", "extra": 1 } ', True),
    ('{"response":"NOT_OK"}', False),
    ("{}", False),
    ('{"response":null}', False),
    ('{"response":true}', False),
    ('{"response":1}', False),
    ('{"response":["OK"]}', False),
    ('{"response":"ok"}', False),
    ('{"response":" OK "}', False),
    ('{"response":', False),
    ("not JSON", False),
    ("", False),
    ("[]", False),
    ('[{"response":"OK"}]', False),
    ('"OK"', False),
    ("42", False),
    ("2.5", False),
    ("null", False),
    ("true", False),
    ("false", False),
]
REPLY_IDS = [
    "ok", "extra-fields", "not-ok", "missing-response", "null-response",
    "bool-response", "number-response", "list-response", "lowercase-response",
    "padded-response", "truncated-json", "invalid-json", "empty-body",
    "empty-list", "nonempty-list", "string", "integer", "float", "null",
    "true", "false",
]


@pytest.mark.parametrize(("method", "arguments"), POST_CASES, ids=POST_IDS)
@pytest.mark.parametrize(("body", "expected"), REPLIES, ids=REPLY_IDS)
def test_post_confirmation_matrix(stove, session, method, arguments, body, expected):
    response = session.queue_text(body, method="POST")
    assert asyncio.run(getattr(stove, method)(*arguments)) is expected
    assert len(session.calls) == 1  # An invalid confirmation must never retry.
    assert response.entered and response.exited
    assert not session.responses


@pytest.mark.parametrize(("method", "arguments"), POST_CASES, ids=POST_IDS)
@pytest.mark.parametrize(
    "error_type", [asyncio.CancelledError, MemoryError, RuntimeError, TypeError]
)
def test_unexpected_decoder_errors_propagate(
    stove, session, monkeypatch, method, arguments, error_type
):
    error = error_type("decoder failure")

    def fail_decode(body):
        raise error

    session.queue_text('{"response":"OK"}', method="POST")
    # Patch only after queuing; request serialization uses json.dumps, not loads.
    monkeypatch.setattr(runtime.json, "loads", fail_decode)
    with pytest.raises(error_type) as raised:
        asyncio.run(getattr(stove, method)(*arguments))
    assert raised.value is error
    assert len(session.calls) == 1


@pytest.mark.parametrize(("method", "arguments"), POST_CASES, ids=POST_IDS)
@pytest.mark.parametrize(
    "error_type",
    [aiohttp.ClientPayloadError, aiohttp.ServerDisconnectedError, TimeoutError,
     asyncio.CancelledError],
)
def test_transport_errors_remain_outside_response_parser(
    stove, session, method, arguments, error_type
):
    error = error_type("response read failure")
    session.queue_text("", method="POST", text_error=error)
    with pytest.raises(error_type) as raised:
        asyncio.run(getattr(stove, method)(*arguments))
    assert raised.value is error
    assert len(session.calls) == 1


@pytest.fixture
def h4_stove_class(monkeypatch):
    """Load six literal H4 commands; never generate expectations from current code."""
    source = (Path(__file__).parent / "fixtures" / "h4_commands.json").read_bytes()
    assert hashlib.sha256(source).hexdigest() == (
        "68507ad1e561dcf982e3de132356f2c9a705ab3d12bfa549470e1f7b7150795d"
    )
    fixture = json.loads(source)
    assert fixture["commit"] == "82c8438ed046261c2e29bf3af01fe6f65fc89bb5"
    assert fixture["source_sha256"] == (
        "5c22524424f60d550b059dc52994640bcfb6941e6a0ad59bec99046408cd9569"
    )

    class FixedDateTime(datetime):
        @classmethod
        def now(cls):
            return cls(2024, 2, 29, 23, 57, 58)

    monkeypatch.setattr(runtime, "datetime", FixedDateTime)
    methods = {}
    for name, literal in fixture["methods"].items():
        namespace = vars(runtime).copy()
        exec(compile(textwrap.dedent(literal), f"<H4 {name}>", "exec"), namespace)
        methods[name] = namespace[name]
    return type("H4Commands", (Stove,), methods)


COMMAND_CASES = [
    *[("set_burn_level", (level,), False) for level in range(6)],
    ("set_remote_refill_alarm", (True,), False),
    ("set_remote_refill_alarm", (False,), False),
    ("set_remote_refill_alarm", (), True),
    ("set_remote_refill_alarm", (None,), True),
    ("set_night_lowering_hours", (time(22, 15), time(6, 30)), False),
    ("set_night_lowering_hours", (time(0, 0), time(0, 0)), False),
    ("set_night_lowering_hours", (), True),
    ("set_night_lowering_hours", (time(21, 0), None), True),
    ("set_night_lowering_hours", (None, time(7, 0)), True),
    ("set_time", (datetime(2024, 1, 31, 23, 59, 58),), False),
    ("set_time", (datetime(2024, 12, 31, 23, 59, 58),), False),
    ("set_time", (), False),
    ("set_time", (None,), False),
    ("set_night_lowering", (True,), False),
    ("set_night_lowering", (False,), False),
    ("set_night_lowering", (), True),
    ("start", (), False),
]


@pytest.mark.parametrize(("method", "arguments", "reads_status"), COMMAND_CASES)
@pytest.mark.parametrize(
    "body",
    ['{"response":"OK"}', ' { "response" : "OK", "extra": 1 } ',
     '{"response":"NOT_OK"}', "{}", '{"response":null}'],
)
def test_command_results_and_exact_requests_match_h4(
    h4_stove_class, raw_data, method, arguments, reads_status, body
):
    observed = []
    for cls in (h4_stove_class, Stove):
        session = FakeSession()
        instance = cls()
        instance.stove_host = "stove.test"
        instance._session = session
        if reads_status:
            session.queue_json(deepcopy(raw_data), method="GET")
        session.queue_text(body)
        result = asyncio.run(getattr(instance, method)(*arguments))
        assert not session.responses
        observed.append((result, type(result), session.calls))
    assert observed[0] == observed[1]
