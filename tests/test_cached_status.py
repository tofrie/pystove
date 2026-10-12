"""A05 side snapshot: strict boolean, latest-attempt ownership, no new I/O."""

import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from pystove import Stove

from .test_cached_diagnostics import EXPECTED, OPTIONAL, check


@pytest.mark.parametrize("door", [True, False, None, 0, 1, "true", "false", [], {}])
def test_door_types_and_exact_25_key_contract(stove, session, raw_data, door):
    assert stove.cached_status == {
        "generation": 0, "valid": False, "door_open": None,
    }
    result = check(stove, session, raw_data | OPTIONAL | {"door_open": door})
    assert len(result) == 25 and "door_open" not in result
    assert stove.cached_status == {
        "generation": 1, "valid": True,
        "door_open": door if type(door) is bool else None,
    }
    assert stove.cached_diagnostics == EXPECTED
    copy = stove.cached_status
    copy["door_open"] = "changed"
    assert stove.cached_status["door_open"] is not copy["door_open"]
    with pytest.raises(AttributeError):
        stove.cached_status = {}


def test_equal_status_changed_door_missing_and_invalid(stove, session, raw_data):
    results = []
    for generation, raw in enumerate([
        raw_data | {"door_open": True}, raw_data | {"door_open": False},
        raw_data, raw_data | {"door_open": "false"},
    ], 1):
        results.append(check(stove, session, raw))
        assert stove.cached_status["generation"] == generation
    assert results == [results[0]] * 4
    assert stove.cached_status["door_open"] is None
    assert len(session.calls) == 4


@pytest.mark.parametrize("failure", [None, "invalid", TimeoutError(),
                                     RuntimeError(), asyncio.CancelledError()])
def test_failure_clears_door_preserves_diagnostics(
    stove, session, raw_data, monkeypatch, failure,
):
    check(stove, session, raw_data | OPTIONAL | {"door_open": True})
    mock = AsyncMock()
    if isinstance(failure, BaseException):
        mock.side_effect = failure
    else:
        mock.return_value = None if failure is None else raw_data | {"phase": 999}
    monkeypatch.setattr(stove, "get_raw_data", mock)
    if isinstance(failure, BaseException):
        with pytest.raises(type(failure)) as caught:
            asyncio.run(stove.get_data())
        assert caught.value is failure
    else:
        assert asyncio.run(stove.get_data()) is None
    assert stove.cached_status == {
        "generation": 2, "valid": False, "door_open": None,
    }
    assert stove.cached_diagnostics == EXPECTED
    mock.assert_awaited_once()


@pytest.mark.parametrize("newer", ["failure", "success", "cancel", "destroy"])
def test_overlapping_old_completion_never_revives_status(raw_data, newer):
    async def run():
        stove = Stove()
        stove._session = AsyncMock()
        entered, finish = asyncio.Event(), asyncio.Event()
        count = 0

        async def read():
            nonlocal count
            count += 1
            if count == 1:
                entered.set()
                await finish.wait()
                return deepcopy(raw_data | {"door_open": True})
            if newer == "failure":
                raise TimeoutError
            if newer == "cancel":
                raise asyncio.CancelledError
            return deepcopy(raw_data | {"door_open": False})

        stove.get_raw_data = read
        old = asyncio.create_task(stove.get_data())
        await entered.wait()
        assert stove.cached_status["valid"] is False
        if newer == "destroy":
            await stove.destroy()
        elif newer in {"failure", "cancel"}:
            with pytest.raises(TimeoutError if newer == "failure"
                               else asyncio.CancelledError):
                await stove.get_data()
        else:
            await stove.get_data()
        snapshot = stove.cached_status
        finish.set()
        assert len(await old) == 25
        assert stove.cached_status == snapshot
        assert snapshot["door_open"] is (False if newer == "success" else None)
        assert snapshot["valid"] is (newer == "success")
        assert count == (1 if newer == "destroy" else 2)
    asyncio.run(run())
