"""Strict expected failures for defects retained from compatibility baseline 0.3a1.

These assertions describe later correction goals, not compatibility promises.
Only a specifically observed legacy failure is translated into an expected
failure. An unexpected mock failure, exception or result fails normally. No
test makes requests to a physical stove or opens a network connection.
"""

import asyncio
from types import SimpleNamespace

import aiohttp
import pytest

from pystove import Stove


class _KnownLegacyFailure(AssertionError):
    """Identify only the measured legacy defect, not an arbitrary assertion."""


def _known_failure(condition, message):
    if not condition:
        raise _KnownLegacyFailure(message)


def _expect_rejection(coroutine, legacy_error, *, result=None, error_args=None):
    """Expect safe rejection; recognize exactly the documented current error."""
    try:
        actual = asyncio.run(coroutine)
    except legacy_error as exc:
        assert type(exc) is legacy_error
        if error_args is not None:
            assert exc.args == error_args
        raise _KnownLegacyFailure(
            f"0.3a1 raises {legacy_error.__name__} instead of returning {result!r}"
        ) from exc
    assert actual is result


def test_factory_closes_session_after_identification_failure(monkeypatch, session):
    """Audit H3 regression: failed identification releases its owned session."""
    async def fail_identification(self):
        raise RuntimeError("scripted identification failure")

    monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: session)
    monkeypatch.setattr(Stove, "_identify", fail_identification)
    with pytest.raises(RuntimeError, match="^scripted identification failure$"):
        asyncio.run(Stove.create("stove.test"))
    assert session.close_calls == 1
    assert session.closed


def test_factory_closes_session_after_identification_cancellation(monkeypatch, session):
    """Audit H3 regression: cancelled identification releases its session."""
    async def cancel_identification(self):
        raise asyncio.CancelledError

    monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: session)
    monkeypatch.setattr(Stove, "_identify", cancel_identification)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(Stove.create("stove.test"))
    assert session.close_calls == 1
    assert session.closed


def test_get_data_rejects_unreachable_controller(stove, session):
    """Audit H4 regression: absent status does not enter the status parser."""
    connection_key = SimpleNamespace(host="stove.test", port=80, ssl=False)
    error = aiohttp.ClientConnectorError(
        connection_key, ConnectionRefusedError(111, "scripted connection refusal")
    )
    session.queue_text("", method="GET", enter_error=error)
    assert asyncio.run(stove.get_data()) is None


@pytest.mark.parametrize(
    "body", ["not JSON", '{"phase":'], ids=["invalid", "truncated"]
)
def test_get_data_rejects_malformed_json(stove, session, body):
    """Audit H4 regression: malformed status JSON produces a failed fetch."""
    session.queue_text(body, method="GET")
    assert asyncio.run(stove.get_data()) is None


@pytest.mark.parametrize("missing", ["phase", "year", "stove_temperature"])
def test_get_data_rejects_missing_required_field(stove, session, raw_data, missing):
    """Audit H4 regression: partial status produces a failed fetch."""
    del raw_data[missing]
    session.queue_json(raw_data, method="GET")
    assert asyncio.run(stove.get_data()) is None


@pytest.mark.parametrize("field", ["phase", "operation_mode", "night_lowering"])
def test_get_data_rejects_unknown_state(stove, session, raw_data, field):
    """Audit H4 regression: unrecognized status index fails the entire fetch."""
    raw_data[field] = 99
    session.queue_json(raw_data, method="GET")
    assert asyncio.run(stove.get_data()) is None


def test_get_data_rejects_invalid_calendar_date(stove, session, raw_data):
    """Audit H4 regression: impossible calendar values fail the fetch."""
    raw_data["day"] = 30  # February 2024 has only 29 days.
    session.queue_json(raw_data, method="GET")
    assert asyncio.run(stove.get_data()) is None


def test_get_data_rejects_non_object_json(stove, session):
    """Audit H4 regression: a status JSON array is not a status mapping."""
    session.queue_json([], method="GET")
    assert asyncio.run(stove.get_data()) is None


@pytest.mark.parametrize(
    ("method", "arguments", "body"),
    [
        ("set_burn_level", (3,), '{"response":'),
        ("set_remote_refill_alarm", (True,), "[]"),
    ],
    ids=["malformed-json", "wrong-response-shape"],
)
def test_command_rejects_invalid_response(stove, session, method, arguments, body):
    """Audit H6 regression: invalid POST confirmations return False."""
    session.queue_text(body, method="POST")
    assert asyncio.run(getattr(stove, method)(*arguments)) is False


@pytest.mark.parametrize(
    ("method", "arguments", "http_method"),
    [("set_burn_level", (3,), "POST"), ("start", (), "GET")],
    ids=["post-command", "get-command"],
)
@pytest.mark.xfail(
    strict=True,
    raises=_KnownLegacyFailure,
    reason=(
        "Audit H6; baseline 0.3a1: commands accept HTTP 500 with an OK response body"
    ),
)
def test_command_rejects_http_error_status(
    stove, session, method, arguments, http_method
):
    session.queue_json({"response": "OK"}, method=http_method, status=500)
    result = asyncio.run(getattr(stove, method)(*arguments))
    _known_failure(result is not True, "Command accepted HTTP 500 as success")
    assert result is False


@pytest.mark.parametrize(
    "legacy_error",
    [aiohttp.ClientPayloadError, aiohttp.ServerDisconnectedError, TimeoutError],
    ids=["incomplete-body", "connection-lost", "read-timeout"],
)
def test_command_rejects_response_transport_failure(stove, session, legacy_error):
    """Audit H6 regression: approved POST body-read failures are unconfirmed."""
    error = legacy_error("scripted response transport failure")
    session.queue_text("", method="POST", text_error=error)
    assert asyncio.run(stove.set_burn_level(3)) is False


@pytest.mark.xfail(
    strict=True,
    raises=_KnownLegacyFailure,
    reason="Audit M1; baseline 0.3a1: missing live-data body is passed to bytearray",
)
def test_get_live_data_rejects_missing_body(stove, monkeypatch):
    async def absent_body(url):
        return None

    monkeypatch.setattr(stove, "_get", absent_body)
    _expect_rejection(stove.get_live_data(), TypeError)


@pytest.mark.xfail(
    strict=True,
    raises=_KnownLegacyFailure,
    reason=(
        "Audit M1; baseline 0.3a1: length guard rejects 960 bytes required "
        "by its own indexing"
    ),
)
def test_get_live_data_length_guard_matches_legacy_index_ranges(stove, session):
    # Synthetic ASCII bytes test only the internal size contradiction. They do
    # not establish the encoding or framing of a real HWAM response.
    session.queue_text("0" * 960, method="GET")
    result = asyncio.run(stove.get_live_data())
    _known_failure(
        result is not None, "Legacy guard rejected its required 960-byte range"
    )
    assert set(result) == {"stove_temperature", "oxygen_level"}
    assert len(result["stove_temperature"]) == 120
    assert len(result["oxygen_level"]) == 120


@pytest.mark.xfail(
    strict=True,
    raises=_KnownLegacyFailure,
    reason=(
        "Audit M1; baseline 0.3a1: accepted 120-byte live response "
        "exceeds buffer bounds"
    ),
)
def test_get_live_data_rejects_undersized_accepted_body(stove, session):
    session.queue_text("0" * 120, method="GET")
    _expect_rejection(stove.get_live_data(), IndexError)


@pytest.mark.xfail(
    strict=True,
    raises=_KnownLegacyFailure,
    reason=(
        "Audit M2; baseline 0.3a1: empty self-test replies bypass "
        "the three-attempt retry budget"
    ),
)
def test_self_test_empty_replies_obey_retry_budget(stove, session):
    # A finite terminal response guarantees this characterization cannot spin
    # forever. The four empty replies already exceed the documented budget.
    for _ in range(4):
        session.queue_json({}, method="GET")
    session.queue_json({"o2_sensor": 1}, method="GET")
    result = asyncio.run(stove._self_test_result())
    _known_failure(
        len(session.calls) <= 3, "Empty replies were retried more than three times"
    )
    assert result is None
