"""Confirmed-open cleanup: deterministic, offline, and observed before loop exit."""

import asyncio
import gc
import socket
from unittest.mock import AsyncMock, Mock
import warnings

import aiohttp
import pytest

from pystove import Stove, pystove as runtime

from .conftest import FakeResponse, FakeSession
from .test_create_lifecycle import _assert_logged_cleanup_error, _wait
from .test_py314_cancellation import checkpoint

XML = "<Info><Name>Algorithm</Name><StoveType>Series</StoveType></Info>"
PAYLOAD = {"data": '{"file_name":"info.xml","mode":1}'}


@pytest.fixture(autouse=True)
def offline_and_no_resource_warnings(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A cleanup test attempted network access")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always", ResourceWarning)
        yield
        gc.collect()
    assert not [r for r in records if issubclass(r.category, ResourceWarning)]


class Response(FakeResponse):
    def __init__(self, body, *, held=False, error=None):
        super().__init__(body)
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.finished = False
        self.error = error
        self.task = None
        if not held:
            self.release.set()

    async def text(self):
        self.task = asyncio.current_task()
        self.started.set()
        try:
            await self.release.wait()
            if self.error is not None:
                raise self.error
            return self.body
        finally:
            self.finished = True


class Probe(FakeSession):
    def __init__(self, *, open_body='{"success":1}', read_body=XML,
                 held=(), errors=None):
        super().__init__()
        errors = errors or {}
        self.stages = {}
        for stage, body in (
            ("open", open_body), ("read", read_body), ("close", "opaque-reply"),
        ):
            response = Response(body, held=stage in held, error=errors.get(stage))
            self.stages[stage] = response
            endpoint = {"open": "open_file", "read": "read_open_file",
                        "close": "close_file"}[stage]
            self.responses.append((
                "GET" if stage == "close" else "POST",
                "http://stove.test/" + endpoint, response,
            ))
        self.queue_json({"name": "HWAM", "ip": "192.0.2.1", "mdns": "stove"},
                        url="http://stove.test/esp/get_identification")
        self.queue_json({"ssid": "test"},
                        url="http://stove.test/esp/get_current_accesspoint")

    async def close(self):
        for response in self.stages.values():
            if response.started.is_set():
                assert response.finished
        assert all(b.closed and b.close_calls == 1 for b in self.borrowers)
        await super().close()

    def assert_file_calls(self, stages):
        calls = [(m, u.rsplit("/", 1)[-1], k) for m, u, k in self.calls
                 if u.endswith(("/open_file", "/read_open_file", "/close_file"))]
        expected = {
            "open": ("POST", "open_file", PAYLOAD),
            "read": ("POST", "read_open_file", PAYLOAD),
            "close": ("GET", "close_file", {"allow_redirects": False}),
        }
        assert calls == [expected[stage] for stage in stages]


def run_checked(scenario):
    async def run():
        loop = asyncio.get_running_loop()
        contexts = []
        loop.set_exception_handler(lambda loop, context: contexts.append(context))
        before = asyncio.all_tasks()
        await scenario()
        await checkpoint()
        gc.collect()
        assert asyncio.all_tasks() == before
        assert contexts == []

    asyncio.run(run())


@pytest.mark.parametrize("body", [XML, "<broken>", "<Info/>"])
def test_success_and_xml_errors_close_once(monkeypatch, body, caplog):
    async def scenario():
        probe = Probe(read_body=body)
        monkeypatch.setattr(aiohttp, "ClientSession", probe.factory)
        stove = await Stove.create("stove.test")
        assert stove.algo_version == ("Algorithm" if body == XML else "Unknown")
        assert stove.series == ("Series" if body == XML else "Unknown")
        probe.assert_file_calls(["open", "read", "close"])
        assert probe.close_calls == 0
        await stove.destroy()
        assert probe.close_calls == 1
        assert "opaque-reply" not in caplog.text
        assert "close succeeded" not in caplog.text

    run_checked(scenario)


@pytest.mark.parametrize("outcome", ["rejected", "none", "lost", "bad_json",
                                     "missing_success", "cancel"])
def test_unconfirmed_open_never_closes(monkeypatch, outcome):
    async def scenario():
        error = aiohttp.ServerDisconnectedError("lost open response")
        probe = Probe(
            open_body={"rejected": '{"success":0}', "bad_json": "{",
                       "missing_success": "{}"}.get(outcome, '{"success":1}'),
            held=("open",) if outcome == "cancel" else (),
            errors={"open": error} if outcome == "lost" else {},
        )
        monkeypatch.setattr(aiohttp, "ClientSession", probe.factory)
        if outcome == "none":
            # _post's connection-error path returns None before confirmation.
            probe.stages["open"].body = None
        creator = asyncio.create_task(Stove.create("stove.test"))
        if outcome == "cancel":
            await _wait(probe.stages["open"].started)
            creator.cancel("open cancellation")
        if outcome in ("rejected", "none"):
            stove = await creator
            await stove.destroy()
        else:
            expected = {"lost": aiohttp.ServerDisconnectedError,
                        "bad_json": ValueError, "missing_success": KeyError,
                        "cancel": asyncio.CancelledError}[outcome]
            with pytest.raises(expected) as caught:
                await creator
            if outcome == "lost":
                assert caught.value is error
        probe.assert_file_calls(["open"])
        assert probe.close_calls == 1 and probe.borrowers == []

    run_checked(scenario)


@pytest.mark.parametrize("outcome", ["none", "exception"])
@pytest.mark.parametrize("close_error", [False, True])
def test_read_failure_keeps_primary(monkeypatch, caplog, outcome, close_error):
    async def scenario():
        primary = aiohttp.ClientPayloadError("read failed")
        secondary = RuntimeError("close failed")
        errors = {"read": primary} if outcome == "exception" else {}
        if close_error:
            errors["close"] = secondary
        probe = Probe(read_body=None if outcome == "none" else XML, errors=errors)
        monkeypatch.setattr(aiohttp, "ClientSession", probe.factory)
        with pytest.raises(type(primary) if outcome == "exception" else TypeError
                           ) as caught:
            await Stove.create("stove.test")
        if outcome == "exception":
            assert caught.value is primary
        if close_error:
            _assert_logged_cleanup_error(caplog, secondary)
        probe.assert_file_calls(["open", "read", "close"])
        assert probe.close_calls == 1

    run_checked(scenario)


@pytest.mark.parametrize("cancel_stage", ["read", "close"])
@pytest.mark.parametrize("extra_cancels", [0, 1, 5])
@pytest.mark.parametrize("close_error", [False, True])
def test_cancellation_drains_one_close(
    monkeypatch, caplog, cancel_stage, extra_cancels, close_error
):
    async def scenario():
        secondary = RuntimeError("secondary close failure")
        probe = Probe(held=(cancel_stage, "close"),
                      errors={"close": secondary} if close_error else {})
        monkeypatch.setattr(aiohttp, "ClientSession", probe.factory)
        creator = asyncio.create_task(Stove.create("stove.test"))
        try:
            await _wait(probe.stages[cancel_stage].started)
            creator.cancel("primary cancellation")
            await _wait(probe.stages["close"].started)
            close_task = probe.stages["close"].task
            for index in range(extra_cancels):
                creator.cancel(f"later {index}")
                # Also exercise cancellation at the owned identify-task boundary.
                probe.stages["read"].task.cancel(f"child {index}")
                await checkpoint()
                assert not creator.done() and not close_task.done()
                assert probe.close_calls == 0
            probe.stages["close"].release.set()
            with pytest.raises(asyncio.CancelledError) as caught:
                await creator
            assert caught.value.args == ("primary cancellation",)
            assert close_task.done()
            assert probe.close_calls == 1
            probe.assert_file_calls(["open", "read", "close"])
            if close_error:
                _assert_logged_cleanup_error(caplog, secondary)
        finally:
            for response in probe.stages.values():
                response.release.set()
            if not creator.done():
                creator.cancel()
            await asyncio.gather(creator, return_exceptions=True)

    run_checked(scenario)


@pytest.mark.parametrize("primary", [False, True])
@pytest.mark.parametrize("target", ["child", "factory"])
def test_late_cancellation_preserves_read_error(monkeypatch, primary, target):
    async def scenario():
        error = ValueError("original read error")
        probe = Probe(held=("close",), errors={"read": error} if primary else {})
        monkeypatch.setattr(aiohttp, "ClientSession", probe.factory)
        creator = asyncio.create_task(Stove.create("stove.test"))
        await _wait(probe.stages["close"].started)
        for index in range(3):
            task = probe.stages["read"].task if target == "child" else creator
            task.cancel(f"late cancel {index}")
            await checkpoint()
        probe.stages["close"].release.set()
        with pytest.raises(ValueError if primary else asyncio.CancelledError
                           ) as caught:
            await creator
        if primary:
            assert caught.value is error
        else:
            assert caught.value.args == ("late cancel 0",)
        assert probe.close_calls == 1
        probe.assert_file_calls(["open", "read", "close"])

    run_checked(scenario)


@pytest.mark.parametrize("primary", [False, True])
@pytest.mark.parametrize("kind", ["timeout", "exception", "cancelled"])
def test_close_failure_consumed_without_false_success(
    monkeypatch, caplog, primary, kind
):
    async def scenario():
        error = ValueError("original read error")
        secondary = (asyncio.CancelledError("close cancelled") if kind == "cancelled"
                     else RuntimeError("close failed"))
        errors = {"read": error} if primary else {}
        if kind != "timeout":
            errors["close"] = secondary
        probe = Probe(held=("close",) if kind == "timeout" else (), errors=errors)
        monkeypatch.setattr(aiohttp, "ClientSession", probe.factory)
        if kind == "timeout":
            monkeypatch.setattr(runtime, "_INFO_FILE_CLOSE_TIMEOUT", 0.01)
        if primary:
            with pytest.raises(ValueError) as caught:
                await Stove.create("stove.test")
            assert caught.value is error
        else:
            stove = await Stove.create("stove.test")
            assert stove.algo_version == "Algorithm"
            await stove.destroy()
        assert "controller close unconfirmed" in caplog.text
        if kind == "timeout":
            assert any(r.exc_info and isinstance(r.exc_info[1], TimeoutError)
                       for r in caplog.records)
        else:
            _assert_logged_cleanup_error(caplog, secondary)
        probe.assert_file_calls(["open", "read", "close"])
        assert probe.close_calls == 1

    run_checked(scenario)


@pytest.mark.parametrize("error_type", [aiohttp.ServerDisconnectedError,
                                        aiohttp.ClientOSError])
def test_actual_aiohttp_get_never_retries_or_closes_parent(
    monkeypatch, caplog, error_type
):
    async def scenario():
        # Exercise aiohttp's real _request retry loop without a socket/DNS call.
        async with aiohttp.ClientSession(headers={"Accept": "application/json"}
                                        ) as parent:
            connector = parent.connector
            connection = Mock()
            connect = AsyncMock(return_value=connection)
            monkeypatch.setattr(connector, "connect", connect)
            send = AsyncMock(side_effect=error_type("connection dropped"))
            monkeypatch.setattr(aiohttp.ClientRequest, "send", send)
            # Control: the same installed transport really would retry a GET.
            with pytest.raises(error_type):
                async with parent.get("http://stove.test/close_file"):
                    pytest.fail("The simulated disconnect must propagate")
            assert send.await_count == connect.await_count == 2
            send.reset_mock()
            connect.reset_mock()
            stove = Stove()
            stove.stove_host = "stove.test"
            stove._session = parent
            await stove._close_info_file(None)
            assert send.await_count == connect.await_count == 1
            request = connect.call_args.args[0]
            assert request.method == "GET"
            assert str(request.url) == "http://stove.test/close_file"
            assert request.headers["Accept"] == "application/json"
            assert not parent.closed and not connector.closed
            assert parent._retry_connection is True
        assert connector.closed
        assert "controller close unconfirmed" in caplog.text

    run_checked(scenario)


@pytest.mark.parametrize("status", [200, 302, 404, 500])
def test_real_close_transport_has_no_redirect_or_status_policy(monkeypatch, status):
    async def scenario():
        async with aiohttp.ClientSession() as parent:
            response = Mock(spec=aiohttp.ClientResponse)
            response.start = AsyncMock()
            response.read = AsyncMock(return_value=b'{"response":"OK"}')
            response.__aenter__ = AsyncMock(return_value=response)
            response.__aexit__ = AsyncMock()
            response.connection = None
            response._raw_cookie_headers = ()
            response.status = status
            response.headers = {"Location": "http://stove.test/not-permitted"}
            connect = AsyncMock(return_value=Mock())
            send = AsyncMock(return_value=response)
            monkeypatch.setattr(parent.connector, "connect", connect)
            monkeypatch.setattr(aiohttp.ClientRequest, "send", send)
            stove = Stove()
            stove.stove_host = "stove.test"
            stove._session = parent
            assert await stove._close_info_file(None) is None
            assert send.await_count == connect.await_count == 1
            assert response.read.await_count == response.__aexit__.await_count == 1
            response.raise_for_status.assert_not_called()
            assert not parent.closed

    run_checked(scenario)


@pytest.mark.parametrize("primary_kind", ["error", "cancel"])
def test_close_deadline_survives_repeated_factory_cancellation(
    monkeypatch, caplog, primary_kind
):
    async def scenario():
        original_timeout = asyncio.timeout
        timeouts = []

        def observed_timeout(delay):
            result = original_timeout(delay)
            timeouts.append(result)
            return result

        monkeypatch.setattr(asyncio, "timeout", observed_timeout)
        error = ValueError("original read error")
        probe = Probe(held=("read", "close") if primary_kind == "cancel"
                      else ("close",),
                      errors={"read": error} if primary_kind == "error" else {})
        monkeypatch.setattr(aiohttp, "ClientSession", probe.factory)
        creator = asyncio.create_task(Stove.create("stove.test"))
        if primary_kind == "cancel":
            await _wait(probe.stages["read"].started)
            creator.cancel("original cancellation")
        await _wait(probe.stages["close"].started)
        for index in range(5):
            creator.cancel(f"late cancellation {index}")
            await checkpoint()
            assert not creator.done() and not probe.closed
        assert len(timeouts) == 1
        # Exercise the real timeout mechanism without waiting five seconds.
        timeouts[0].reschedule(asyncio.get_running_loop().time())
        with pytest.raises(ValueError if primary_kind == "error"
                           else asyncio.CancelledError) as caught:
            await creator
        if primary_kind == "error":
            assert caught.value is error
        else:
            assert caught.value.args == ("original cancellation",)
        assert probe.close_calls == 1 and probe.stages["close"].finished
        probe.assert_file_calls(["open", "read", "close"])
        assert any(r.exc_info and isinstance(r.exc_info[1], TimeoutError)
                   for r in caplog.records)

    run_checked(scenario)


@pytest.mark.parametrize("primary", [False, True])
def test_cancellation_queued_at_close_completion(monkeypatch, primary):
    async def scenario():
        error = ValueError("original read error")
        probe = Probe(held=("close",), errors={"read": error} if primary else {})
        monkeypatch.setattr(aiohttp, "ClientSession", probe.factory)
        creator = asyncio.create_task(Stove.create("stove.test"))
        await _wait(probe.stages["close"].started)
        probe.stages["close"].task.add_done_callback(
            lambda task: probe.stages["read"].task.cancel("completion cancellation")
        )
        probe.stages["close"].release.set()
        with pytest.raises(ValueError if primary else asyncio.CancelledError
                           ) as caught:
            await creator
        if primary:
            assert caught.value is error
        else:
            assert caught.value.args == ("completion cancellation",)
        assert probe.close_calls == 1
        probe.assert_file_calls(["open", "read", "close"])

    run_checked(scenario)
