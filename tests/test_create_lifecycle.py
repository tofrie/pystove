"""Audit H3: own initialization resources are drained before create() exits.

All concurrency is controlled through Events. Assertions run while the loop
is still alive, before asyncio.run() could hide leaked tasks during shutdown.
No test opens a socket or accesses HWAM hardware.
"""

import asyncio
import logging

import aiohttp
import pytest

from pystove import Stove
from tests.conftest import FakeSession


async def _wait(event):
    """Bound only test synchronization, never the runtime request timeout."""
    await asyncio.wait_for(event.wait(), timeout=2)


class _SessionProbe(FakeSession):
    def __init__(self, *, before_close=None, error=None, hold_close=False):
        super().__init__()
        self.before_close = before_close
        self.error = error
        self.close_started = asyncio.Event()
        self.close_release = asyncio.Event()
        if not hold_close:
            self.close_release.set()

    async def close(self):
        self.close_calls += 1
        if self.before_close is not None:
            self.before_close()
        self.close_started.set()
        await self.close_release.wait()
        self.closed = True
        if self.error is not None:
            raise self.error


class _IdentifyProbe:
    """Observe the actual three _identify() children through their I/O calls."""

    branches = ("identity", "ssid", "version")

    def __init__(
        self,
        *,
        failure=None,
        failing_branch=None,
        hold_finalization=(),
        finalization_errors=None,
        read_version=False,
    ):
        self.failure = failure
        self.failing_branch = failing_branch
        self.hold_finalization = set(hold_finalization)
        self.finalization_errors = finalization_errors or {}
        self.read_version = read_version
        self.tasks = {}
        self.started = asyncio.Event()
        self.version_read_started = asyncio.Event()
        self.release = {branch: asyncio.Event() for branch in self.branches}
        self.finishing = {branch: asyncio.Event() for branch in self.branches}
        self.finish_release = {branch: asyncio.Event() for branch in self.branches}
        self.finalized = set()
        self.calls = []

    async def request(self, branch):
        task = asyncio.current_task()
        assert task is not None
        self.tasks[branch] = task
        self.calls.append(branch)
        if len(self.tasks) == 3:
            self.started.set()
        try:
            await self.release[branch].wait()
            if branch == self.failing_branch:
                raise self.failure
            return {
                "identity": {"name": "HWAM", "ip": "192.0.2.1", "mdns": "stove"},
                "ssid": {"ssid": "test-network"},
                "version": '{"success":0}',
            }[branch]
        finally:
            self.finishing[branch].set()
            if branch in self.hold_finalization:
                await self.finish_release[branch].wait()
            self.finalized.add(branch)
            if branch in self.finalization_errors:
                raise self.finalization_errors[branch]

    def install(self, monkeypatch):
        async def get_json(stove, url):
            if url == "http://stove.test/esp/get_identification":
                return await self.request("identity")
            assert url == "http://stove.test/esp/get_current_accesspoint"
            return await self.request("ssid")

        async def post(stove, url, data):
            assert data == {"file_name": "info.xml", "mode": 1}
            if self.read_version and url == "http://stove.test/open_file":
                return '{"success":1}'
            if self.read_version:
                assert url == "http://stove.test/read_open_file"
                self.version_read_started.set()
            else:
                assert url == "http://stove.test/open_file"
            return await self.request("version")

        monkeypatch.setattr(Stove, "_get_json", get_json)
        monkeypatch.setattr(Stove, "_post", post)

    def assert_finished(self):
        assert set(self.tasks) == set(self.branches)
        assert len(set(self.tasks.values())) == 3
        assert all(task.done() for task in self.tasks.values())
        assert self.finalized == set(self.branches)

    async def drain_after_test(self, creator):
        """Release doubles even when an assertion detects the legacy defect."""
        for event in (*self.release.values(), *self.finish_release.values()):
            event.set()
        for task in (creator, *self.tasks.values()):
            if not task.done():
                task.cancel()
        await asyncio.gather(creator, *self.tasks.values(), return_exceptions=True)


def _assert_logged_cleanup_error(caplog, error):
    records = [record for record in caplog.records if record.name == "pystove.pystove"]
    assert any(
        record.levelno >= logging.ERROR
        and record.exc_info is not None
        and record.exc_info[1] is error
        for record in records
    ), "Cleanup failure must be logged with its original exception information"


@pytest.mark.parametrize("skip_ident", [False, True])
def test_successful_factory_keeps_session_usable_until_destroy(
    monkeypatch, session, skip_ident
):
    session.queue_json(
        {"name": "HWAM", "ip": "192.0.2.1", "mdns": "stove"},
        method="GET",
        url="http://stove.test/esp/get_identification",
    )
    session.queue_json(
        {"ssid": "test-network"},
        method="GET",
        url="http://stove.test/esp/get_current_accesspoint",
    )
    session.queue_json(
        {"success": 1}, method="POST", url="http://stove.test/open_file"
    )
    session.queue_text(
        "<Info><Name>Algorithm</Name><StoveType>Series</StoveType></Info>",
        method="POST",
        url="http://stove.test/read_open_file",
    )
    session.queue_json(
        {"response": "OK"}, method="GET", url="http://stove.test/start"
    )
    session.queue_text("", method="GET", url="http://stove.test/close_file")
    monkeypatch.setattr(aiohttp, "ClientSession", session.factory)

    async def scenario():
        stove = await Stove.create("stove.test", skip_ident=skip_ident)
        assert type(stove) is Stove
        assert stove._session is session
        assert not session.closed
        assert session.close_calls == 0
        assert stove.name == ("Unknown" if skip_ident else "HWAM")
        assert stove.algo_version == ("Unknown" if skip_ident else "Algorithm")
        assert await stove.start() is True
        await stove.destroy()
        assert session.closed
        assert session.close_calls == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("outcome", ["success", "error", "cancel"])
def test_real_aiohttp_session_and_connector_are_released_without_network(
    monkeypatch, outcome
):
    actual_factory = aiohttp.ClientSession
    created = []

    def recording_factory(**kwargs):
        session = actual_factory(**kwargs)
        connector = session.connector
        assert connector is not None
        assert not session.closed
        assert not connector.closed
        created.append((session, connector))
        return session

    monkeypatch.setattr(aiohttp, "ClientSession", recording_factory)

    async def scenario():
        tasks_before = asyncio.all_tasks()
        attempts = 1 if outcome == "success" else 3
        try:
            for _ in range(attempts):
                if outcome == "success":
                    stove = await Stove.create("stove.test", skip_ident=True)
                    session, connector = created[-1]
                    assert stove._session is session
                    assert not session.closed
                    assert not connector.closed
                    await stove.destroy()
                else:
                    cause = (
                        asyncio.CancelledError("real session cancellation")
                        if outcome == "cancel"
                        else RuntimeError("real session initialization failure")
                    )

                    async def identify(stove, initial_error=cause):
                        raise initial_error

                    monkeypatch.setattr(Stove, "_identify", identify)
                    with pytest.raises(type(cause)) as caught:
                        await Stove.create("stove.test")
                    assert caught.value is cause
                assert all(session.closed for session, _ in created)
                assert all(connector.closed for _, connector in created)
                assert asyncio.all_tasks() == tasks_before
            assert len(created) == attempts
        finally:
            for session, _ in created:
                if not session.closed:
                    await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
def test_factory_preserves_exact_initialization_exception(monkeypatch, error_type):
    async def scenario():
        session = _SessionProbe()
        cause = error_type("original initialization error")

        async def identify(stove):
            raise cause

        monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: session)
        monkeypatch.setattr(Stove, "_identify", identify)
        with pytest.raises(error_type) as caught:
            await Stove.create("stove.test")
        assert caught.value is cause
        assert session.closed
        assert session.close_calls == 1

    asyncio.run(scenario())


def test_factory_external_cancellation_preserves_message_and_closes_session(
    monkeypatch,
):
    async def scenario():
        session = _SessionProbe()
        identify_started = asyncio.Event()
        never_released = asyncio.Event()

        async def identify(stove):
            identify_started.set()
            await never_released.wait()

        monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: session)
        monkeypatch.setattr(Stove, "_identify", identify)
        creator = asyncio.create_task(Stove.create("stove.test"))
        await _wait(identify_started)
        creator.cancel("original cancellation")
        with pytest.raises(asyncio.CancelledError) as caught:
            await creator
        assert caught.value.args == ("original cancellation",)
        assert session.closed
        assert session.close_calls == 1

    asyncio.run(scenario())


def test_failed_factory_closes_created_session_without_closing_replacement(monkeypatch):
    async def scenario():
        owned_session = _SessionProbe()
        foreign_session = FakeSession()
        cause = RuntimeError("identify replaced its session before failing")

        async def identify(stove):
            stove._session = foreign_session
            raise cause

        monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: owned_session)
        monkeypatch.setattr(Stove, "_identify", identify)
        with pytest.raises(RuntimeError) as caught:
            await Stove.create("stove.test")
        assert caught.value is cause
        assert owned_session.closed
        assert owned_session.close_calls == 1
        assert not foreign_session.closed
        assert foreign_session.close_calls == 0

    asyncio.run(scenario())


@pytest.mark.parametrize("fail_at", [1, 2, 3])
def test_identify_task_startup_failure_closes_unscheduled_coroutine_and_drains_tasks(
    monkeypatch, fail_at
):
    async def scenario():
        loop = asyncio.get_running_loop()
        previous_factory = loop.get_task_factory()
        cause = RuntimeError("identify task factory failed")
        coroutines = []
        created_tasks = []
        session = _SessionProbe()
        monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: session)
        _IdentifyProbe().install(monkeypatch)
        tasks_before = asyncio.all_tasks()

        def task_factory(event_loop, coroutine, **kwargs):
            is_identify = coroutine.__qualname__ in {
                "Stove._identify.<locals>.get_identification",
                "Stove._identify.<locals>.get_ssid",
                "Stove._identify.<locals>.get_version_info",
            }
            if is_identify:
                coroutines.append(coroutine)
                if len(coroutines) == fail_at:
                    raise cause
            task = asyncio.Task(coroutine, loop=event_loop, **kwargs)
            if is_identify:
                created_tasks.append(task)
            return task

        loop.set_task_factory(task_factory)
        try:
            with pytest.raises(RuntimeError) as caught:
                await Stove.create("stove.test")
            assert caught.value is cause
            assert len(coroutines) == fail_at
            assert len(created_tasks) == fail_at - 1
            assert all(task.done() and task.cancelled() for task in created_tasks)
            assert all(coroutine.cr_frame is None for coroutine in coroutines)
            assert session.closed
            assert session.close_calls == 1
            assert asyncio.all_tasks() == tasks_before
        finally:
            loop.set_task_factory(previous_factory)
            for coroutine in coroutines:
                coroutine.close()
            for task in created_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*created_tasks, return_exceptions=True)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("failing_branch", "read_version"),
    [("identity", False), ("ssid", False), ("version", False), ("version", True)],
    ids=["identification", "accesspoint", "open-file", "read-open-file"],
)
def test_identify_failure_drains_only_its_owned_tasks(
    monkeypatch, failing_branch, read_version
):
    async def scenario():
        cause = RuntimeError("identify branch failed")
        probe = _IdentifyProbe(
            failure=cause, failing_branch=failing_branch, read_version=read_version
        )
        probe.install(monkeypatch)
        session = _SessionProbe(before_close=probe.assert_finished)
        foreign_session = FakeSession()
        foreign_release = asyncio.Event()
        foreign_task = asyncio.create_task(foreign_release.wait())
        session.queue_text("", method="GET", url="http://stove.test/close_file")
        monkeypatch.setattr(aiohttp, "ClientSession", session.factory)
        tasks_before = asyncio.all_tasks()
        creator = asyncio.create_task(Stove.create("stove.test"))
        try:
            await _wait(probe.started)
            if read_version:
                assert probe.version_read_started.is_set()
            probe.release[failing_branch].set()
            with pytest.raises(RuntimeError) as caught:
                await creator
            assert caught.value is cause
            probe.assert_finished()
            assert all(
                task.cancelled()
                for branch, task in probe.tasks.items()
                if branch != failing_branch
            )
            assert session.closed
            assert session.close_calls == 1
            assert asyncio.all_tasks() == tasks_before
            assert not foreign_task.done()
            assert not foreign_session.closed
            assert foreign_session.close_calls == 0
        finally:
            await probe.drain_after_test(creator)
            foreign_release.set()
            await foreign_task

    asyncio.run(scenario())


@pytest.mark.parametrize("initial_cancel", [False, True], ids=["error", "cancel"])
@pytest.mark.parametrize("cleanup_type", [RuntimeError, asyncio.CancelledError])
def test_session_cleanup_error_is_logged_without_replacing_initial_cause(
    monkeypatch, caplog, initial_cancel, cleanup_type
):
    async def scenario():
        cause = (
            asyncio.CancelledError("initial cancellation")
            if initial_cancel
            else ValueError("initial error")
        )
        cleanup_error = cleanup_type("session close failed")
        session = _SessionProbe(error=cleanup_error)

        async def identify(stove):
            raise cause

        monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: session)
        monkeypatch.setattr(Stove, "_identify", identify)
        with pytest.raises(type(cause)) as caught:
            await Stove.create("stove.test")
        assert caught.value is cause
        assert session.close_calls == 1
        _assert_logged_cleanup_error(caplog, cleanup_error)

    with caplog.at_level(logging.ERROR, logger="pystove.pystove"):
        asyncio.run(scenario())


def test_sibling_finalizer_error_is_retrieved_and_logged(monkeypatch, caplog):
    async def scenario():
        cause = ValueError("initial branch failure")
        cleanup_error = RuntimeError("sibling finalizer failed")
        probe = _IdentifyProbe(
            failure=cause,
            failing_branch="identity",
            finalization_errors={"ssid": cleanup_error},
        )
        probe.install(monkeypatch)
        session = _SessionProbe(before_close=probe.assert_finished)
        monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: session)
        loop = asyncio.get_running_loop()
        loop_errors = []
        loop.set_exception_handler(lambda loop, context: loop_errors.append(context))
        creator = asyncio.create_task(Stove.create("stove.test"))
        try:
            await _wait(probe.started)
            probe.release["identity"].set()
            with pytest.raises(ValueError) as caught:
                await creator
            assert caught.value is cause
            probe.assert_finished()
            assert session.closed
            _assert_logged_cleanup_error(caplog, cleanup_error)
            await asyncio.sleep(0)
            assert loop_errors == []
        finally:
            await probe.drain_after_test(creator)

    with caplog.at_level(logging.ERROR, logger="pystove.pystove"):
        asyncio.run(scenario())


@pytest.mark.parametrize("initial_cancel", [False, True], ids=["error", "cancel"])
def test_repeated_failed_factories_do_not_accumulate_sessions_or_tasks(
    monkeypatch, initial_cancel
):
    async def scenario():
        tasks_before = asyncio.all_tasks()
        sessions = []
        owned_tasks = []
        loop = asyncio.get_running_loop()
        loop_errors = []
        loop.set_exception_handler(lambda loop, context: loop_errors.append(context))
        for _ in range(20):
            cause = RuntimeError("repeated identification failure")
            probe = _IdentifyProbe(failure=cause, failing_branch="identity")
            probe.install(monkeypatch)
            session = _SessionProbe(before_close=probe.assert_finished)
            sessions.append(session)
            monkeypatch.setattr(
                aiohttp, "ClientSession", lambda current=session, **kwargs: current
            )
            creator = asyncio.create_task(Stove.create("stove.test"))
            try:
                await _wait(probe.started)
                if initial_cancel:
                    creator.cancel("repeated cancellation")
                    with pytest.raises(asyncio.CancelledError):
                        await creator
                else:
                    probe.release["identity"].set()
                    with pytest.raises(RuntimeError) as caught:
                        await creator
                    assert caught.value is cause
                probe.assert_finished()
                owned_tasks.extend(probe.tasks.values())
                assert asyncio.all_tasks() == tasks_before
                assert all(item.closed and item.close_calls == 1 for item in sessions)
                assert all(task.done() for task in owned_tasks)
            finally:
                await probe.drain_after_test(creator)
        await asyncio.sleep(0)
        assert loop_errors == []
        assert len(sessions) == 20
        assert len(owned_tasks) == 60

    asyncio.run(scenario())


@pytest.mark.parametrize("initial_cancel", [False, True], ids=["error", "cancel"])
def test_repeated_cancellation_cannot_interrupt_identify_task_finalizers(
    monkeypatch, initial_cancel
):
    async def scenario():
        cause = RuntimeError("initial identification failure")
        held = _IdentifyProbe.branches if initial_cancel else ("ssid", "version")
        probe = _IdentifyProbe(
            failure=cause, failing_branch="identity", hold_finalization=held
        )
        probe.install(monkeypatch)
        session = _SessionProbe(before_close=probe.assert_finished)
        monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: session)
        tasks_before = asyncio.all_tasks()
        creator = asyncio.create_task(Stove.create("stove.test"))
        try:
            await _wait(probe.started)
            if initial_cancel:
                creator.cancel("initial cancellation")
            else:
                probe.release["identity"].set()
            for branch in held:
                await _wait(probe.finishing[branch])
            for index in range(3):
                creator.cancel(f"late cancellation {index}")
                await asyncio.sleep(0)
                assert not creator.done()
                assert not session.close_started.is_set()
                assert all(not probe.tasks[branch].done() for branch in held)
            for branch in held:
                probe.finish_release[branch].set()
            if initial_cancel:
                with pytest.raises(asyncio.CancelledError) as caught:
                    await creator
                assert caught.value.args == ("initial cancellation",)
            else:
                with pytest.raises(RuntimeError) as caught:
                    await creator
                assert caught.value is cause
            probe.assert_finished()
            assert session.closed
            assert session.close_calls == 1
            assert asyncio.all_tasks() == tasks_before
        finally:
            await probe.drain_after_test(creator)

    asyncio.run(scenario())


@pytest.mark.parametrize("initial_cancel", [False, True], ids=["error", "cancel"])
def test_repeated_cancellation_cannot_interrupt_session_close(
    monkeypatch, initial_cancel
):
    async def scenario():
        cause = (
            asyncio.CancelledError("initial cancellation")
            if initial_cancel
            else ValueError("initial error")
        )
        session = _SessionProbe(hold_close=True)

        async def identify(stove):
            raise cause

        monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: session)
        monkeypatch.setattr(Stove, "_identify", identify)
        tasks_before = asyncio.all_tasks()
        creator = asyncio.create_task(Stove.create("stove.test"))
        try:
            await _wait(session.close_started)
            for index in range(3):
                creator.cancel(f"late cancellation {index}")
                await asyncio.sleep(0)
                assert not creator.done()
                assert not session.closed
                assert session.close_calls == 1
            session.close_release.set()
            with pytest.raises(type(cause)) as caught:
                await creator
            assert caught.value is cause
            assert session.closed
            assert session.close_calls == 1
            assert asyncio.all_tasks() == tasks_before
        finally:
            session.close_release.set()
            if not creator.done():
                creator.cancel()
            await asyncio.gather(creator, return_exceptions=True)

    asyncio.run(scenario())
