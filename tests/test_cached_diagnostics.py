"""Additive cache: unchanged 25-key parsing, one request, no hidden I/O."""

import asyncio
from copy import deepcopy
import socket
from unittest.mock import AsyncMock, Mock

import pytest

from pystove import Stove

from .conftest import FakeSession
from .test_status_validation import _assert_same_data_contract, _baseline_function

OPTIONAL = {
    "wifi_version_major": 14,
    "wifi_version_minor": 4,
    "wifi_version_build": 0,
    "remote_refill_beeps": 3,
}
EXPECTED = {"wifi_version": "14.4.0", "remote_refill_beeps": 3}
BAD = [None, True, False, -1, 3.0, "3", "private value", [], {}, float("nan")]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    for name in ("create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, Mock(side_effect=AssertionError("Network")))
    monkeypatch.setattr(
        socket.socket, "connect", Mock(side_effect=AssertionError("IP"))
    )


def check(stove, session, raw):
    baseline = Stove()
    baseline.stove_host = "stove.test"
    baseline._session = FakeSession()
    baseline._session.queue_json(deepcopy(raw), method="GET")
    session.queue_json(deepcopy(raw), method="GET")
    expected = asyncio.run(_baseline_function()(baseline))
    before = len(session.calls)
    actual = asyncio.run(stove.get_data())
    _assert_same_data_contract(actual, expected)
    assert (
        session.calls[before:]
        == baseline._session.calls
        == [("GET", "http://stove.test/get_stove_data", {})]
    )
    return actual


def test_success_copy_and_no_diagnostic_requests(stove, session, raw_data, monkeypatch):
    assert Stove().cached_diagnostics == {}
    raw = (
        raw_data
        | OPTIONAL
        | {
            "door_open": True,
            "service_date": "private date",
            "ssid": "private ssid",
        }
    )
    check(stove, session, raw)
    assert stove.cached_diagnostics == EXPECTED
    with monkeypatch.context() as patches:
        for name in ("get_data", "get_raw_data", "_get", "_post", "create"):
            patches.setattr(Stove, name, Mock(side_effect=AssertionError("I/O")))
        copy = stove.cached_diagnostics
        copy.clear()
        assert stove.cached_diagnostics == EXPECTED
    assert len(session.calls) == 1
    assert raw == raw_data | OPTIONAL | {
        "door_open": True,
        "service_date": "private date",
        "ssid": "private ssid",
    }
    with pytest.raises(AttributeError):
        stove.cached_diagnostics = {}
    assert Stove().cached_diagnostics == {}  # No cross-client shared cache.


@pytest.mark.parametrize("field", list(OPTIONAL))
@pytest.mark.parametrize("bad", BAD)
def test_malformed_optional_never_changes_status(stove, session, raw_data, field, bad):
    check(stove, session, raw_data | OPTIONAL)
    check(stove, session, raw_data | OPTIONAL | {field: bad})
    expected = dict(EXPECTED)
    expected.pop(
        "remote_refill_beeps" if field == "remote_refill_beeps" else "wifi_version"
    )
    assert stove.cached_diagnostics == expected


@pytest.mark.parametrize("missing", list(OPTIONAL))
def test_partial_and_missing_replace_previous_cache(stove, session, raw_data, missing):
    check(stove, session, raw_data | OPTIONAL)
    fields = dict(OPTIONAL)
    del fields[missing]
    check(stove, session, raw_data | fields)
    assert stove.cached_diagnostics == (
        {"wifi_version": "14.4.0"}
        if missing == "remote_refill_beeps"
        else {"remote_refill_beeps": 3}
    )
    check(stove, session, raw_data)
    assert stove.cached_diagnostics == {}


@pytest.mark.parametrize(
    "parts,beeps", [((0, 0, 0), 0), ((1, 23, 456), 7), ((99, 9, 9), 100)]
)
def test_exact_integer_components_and_updated_values(
    stove, session, raw_data, parts, beeps
):
    check(stove, session, raw_data | OPTIONAL)
    new = dict(
        zip(
            ("wifi_version_major", "wifi_version_minor", "wifi_version_build"),
            parts,
            strict=True,
        )
    )
    check(stove, session, raw_data | new | {"remote_refill_beeps": beeps})
    assert stove.cached_diagnostics == {
        "wifi_version": ".".join(map(str, parts)),
        "remote_refill_beeps": beeps,
    }
    assert type(stove.cached_diagnostics["remote_refill_beeps"]) is int


@pytest.mark.parametrize("failure", ["none", "invalid", "exception", "cancel"])
def test_failed_reads_preserve_last_success_without_retry(
    stove, session, raw_data, failure
):
    check(stove, session, raw_data | OPTIONAL)
    if failure in {"exception", "cancel"}:
        error = (
            RuntimeError("read failure")
            if failure == "exception"
            else asyncio.CancelledError()
        )
        session.queue_text("", method="GET", text_error=error)
        with pytest.raises(type(error)):
            asyncio.run(stove.get_data())
    else:
        session.queue_json(
            None if failure == "none" else raw_data | {"phase": 999}, method="GET"
        )
        assert asyncio.run(stove.get_data()) is None
    assert stove.cached_diagnostics == EXPECTED
    assert len(session.calls) == 2
    check(stove, session, raw_data)
    assert stove.cached_diagnostics == {}


def test_huge_optional_integer_cannot_break_valid_status(stove, raw_data, monkeypatch):
    # Bypass JSON's own integer-length guard, to exercise only optional conversion.
    monkeypatch.setattr(
        stove,
        "get_raw_data",
        AsyncMock(return_value=raw_data | OPTIONAL | {"wifi_version_major": 10**5000}),
    )
    data = asyncio.run(stove.get_data())
    assert len(data) == 25
    assert stove.cached_diagnostics == {"remote_refill_beeps": 3}
