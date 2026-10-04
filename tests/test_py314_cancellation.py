"""Owned cancellation must leave no loop diagnostics, on Python 3.11 through 3.14."""

import asyncio
import gc
import warnings

import aiohttp
import pytest

from pystove import Stove

from .test_create_lifecycle import (
    _assert_logged_cleanup_error,
    _IdentifyProbe,
    _SessionProbe,
    _wait,
)


async def checkpoint():
    """Advance the ready queue deterministically; no wall-clock sleeps."""
    loop = asyncio.get_running_loop()
    ready = loop.create_future()
    loop.call_soon(ready.set_result, None)
    await ready


@pytest.fixture(autouse=True)
def no_resource_warnings():
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always", ResourceWarning)
        yield
        gc.collect()
    assert not [r for r in records if issubclass(r.category, ResourceWarning)]


@pytest.mark.parametrize("cancellations", [1, 2, 5])
@pytest.mark.parametrize("stage", ["identify", "close"])
@pytest.mark.parametrize("primary_kind", ["cancel", "error"])
def test_cancellation_during_owned_cleanup(
    monkeypatch, cancellations, stage, primary_kind
):
    async def scenario():
        loop = asyncio.get_running_loop()
        contexts = []
        loop.set_exception_handler(lambda loop, context: contexts.append(context))
        before = asyncio.all_tasks()
        cause = RuntimeError("original initialization error")
        probe = _IdentifyProbe(
            failure=cause,
            failing_branch="identity",
            hold_finalization=_IdentifyProbe.branches if stage == "identify" else (),
        )
        probe.install(monkeypatch)
        session = _SessionProbe(
            before_close=probe.assert_finished, hold_close=stage == "close"
        )
        monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: session)
        creator = asyncio.create_task(Stove.create("stove.test"))
        try:
            await _wait(probe.started)
            if primary_kind == "cancel":
                creator.cancel("original cancellation")
            else:
                probe.release["identity"].set()
                # Let the failing branch complete before holding its siblings.
                probe.finish_release["identity"].set()
            if stage == "identify":
                for event in probe.finishing.values():
                    await _wait(event)
            else:
                await _wait(session.close_started)
            for index in range(cancellations - (primary_kind == "cancel")):
                creator.cancel(f"later cancellation {index}")
                await checkpoint()
                assert not creator.done()
                assert not session.closed
            for event in probe.finish_release.values():
                event.set()
            session.close_release.set()
            expected = (
                asyncio.CancelledError if primary_kind == "cancel" else RuntimeError
            )
            with pytest.raises(expected) as caught:
                await creator
            if primary_kind == "cancel":
                assert caught.value.args == ("original cancellation",)
            else:
                assert caught.value is cause
            probe.assert_finished()
            assert session.close_calls == 1
            assert session.closed
            assert asyncio.all_tasks() == before
            await checkpoint()
            gc.collect()
            assert contexts == []
        finally:
            session.close_release.set()
            await probe.drain_after_test(creator)

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["identify", "close"])
def test_cleanup_completion_between_cancellations(monkeypatch, stage):
    async def scenario():
        loop = asyncio.get_running_loop()
        contexts = []
        loop.set_exception_handler(lambda loop, context: contexts.append(context))
        before = asyncio.all_tasks()
        probe = _IdentifyProbe(
            hold_finalization=_IdentifyProbe.branches if stage == "identify" else ()
        )
        probe.install(monkeypatch)
        session = _SessionProbe(before_close=probe.assert_finished, hold_close=True)
        monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: session)
        creator = asyncio.create_task(Stove.create("stove.test"))
        try:
            await _wait(probe.started)
            creator.cancel("original cancellation")
            if stage == "identify":
                for event in probe.finishing.values():
                    await _wait(event)
                # Queue cancellation directly from the final child's completion:
                # cleanup observes completed children and a cancelled caller.
                probe.tasks["version"].add_done_callback(
                    lambda task: creator.cancel("completion cancellation")
                )
                for event in probe.finish_release.values():
                    event.set()
            await _wait(session.close_started)
            if stage == "close":
                # close sets closed=True before its task's done callbacks run.
                close_task = next(t for t in asyncio.all_tasks() if t is not creator
                                  and t.get_coro().__name__ == "close_session")
                close_task.add_done_callback(
                    lambda task: creator.cancel("completion cancellation")
                )
            session.close_release.set()
            with pytest.raises(asyncio.CancelledError) as caught:
                await creator
            assert caught.value.args == ("original cancellation",)
            probe.assert_finished()
            assert session.closed and session.close_calls == 1
            assert asyncio.all_tasks() == before
            await checkpoint()
            gc.collect()
            assert contexts == []
            assert creator.cancel("already finished") is False
        finally:
            session.close_release.set()
            await probe.drain_after_test(creator)

    asyncio.run(scenario())


@pytest.mark.parametrize("primary_kind", ["cancel", "error"])
@pytest.mark.parametrize("cleanup_type", [RuntimeError, asyncio.CancelledError])
@pytest.mark.parametrize("stage", ["identify", "close"])
@pytest.mark.parametrize("late_cancellations", [0, 3])
def test_cleanup_error_is_consumed_without_loop_report(
    monkeypatch, caplog, primary_kind, cleanup_type, stage, late_cancellations
):
    async def scenario():
        loop = asyncio.get_running_loop()
        contexts = []
        loop.set_exception_handler(lambda loop, context: contexts.append(context))
        before = asyncio.all_tasks()
        primary = ValueError("primary initialization error")
        secondary = cleanup_type("secondary cleanup error")
        probe = _IdentifyProbe(
            failure=primary,
            failing_branch="identity",
            hold_finalization=_IdentifyProbe.branches if stage == "identify" else (),
            finalization_errors={"ssid": secondary} if stage == "identify" else {},
        )
        probe.install(monkeypatch)
        session = _SessionProbe(
            before_close=probe.assert_finished,
            hold_close=stage == "close",
            error=secondary if stage == "close" else None,
        )
        monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: session)
        creator = asyncio.create_task(Stove.create("stove.test"))
        try:
            await _wait(probe.started)
            if primary_kind == "cancel":
                creator.cancel("primary cancellation")
            else:
                probe.release["identity"].set()
                probe.finish_release["identity"].set()
            if stage == "identify":
                for event in probe.finishing.values():
                    await _wait(event)
            else:
                await _wait(session.close_started)
            for index in range(late_cancellations):
                creator.cancel(f"late {index}")
                await checkpoint()
                assert not creator.done()
            for event in probe.finish_release.values():
                event.set()
            session.close_release.set()
            expected = (
                asyncio.CancelledError if primary_kind == "cancel" else ValueError
            )
            with pytest.raises(expected) as caught:
                await creator
            if primary_kind == "cancel":
                assert caught.value.args == ("primary cancellation",)
            else:
                assert caught.value is primary
            probe.assert_finished()
            assert session.closed and session.close_calls == 1
            assert asyncio.all_tasks() == before
            if stage == "close" or cleanup_type is not asyncio.CancelledError:
                _assert_logged_cleanup_error(caplog, secondary)
            await checkpoint()
            gc.collect()
            assert contexts == []
        finally:
            session.close_release.set()
            await probe.drain_after_test(creator)

    asyncio.run(scenario())
