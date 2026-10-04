"""Offline I/O doubles shared by the compatibility characterization tests."""

from dataclasses import dataclass
import json

import pytest

from pystove import Stove


@dataclass
class FakeResponse:
    """Provide the response behavior that legacy pystove actually consumes."""

    body: str
    status: int = 200
    enter_error: BaseException | None = None
    text_error: BaseException | None = None
    entered: bool = False
    exited: bool = False

    async def __aenter__(self):
        if self.enter_error is not None:
            raise self.enter_error
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.exited = True

    async def text(self):
        if self.text_error is not None:
            raise self.text_error
        return self.body

    async def read(self):
        return (await self.text()).encode()


class FakeSession:
    """Record exact calls and use queued responses without opening a socket."""

    def __init__(self):
        self.calls = []
        self.responses = []
        self.closed = False
        self.close_calls = 0
        self.connector = object()
        self.cookie_jar = object()
        self.headers = {"Accept": "application/json"}
        self.borrowers = []

    def factory(self, **kwargs):
        if kwargs.get("connector_owner") is False:
            assert kwargs == {
                "connector": self.connector,
                "connector_owner": False,
                "cookie_jar": self.cookie_jar,
                "headers": self.headers,
            }
            borrower = BorrowedSession(self)
            self.borrowers.append(borrower)
            return borrower
        assert kwargs == {"headers": {"Accept": "application/json"}}
        return self

    def queue_text(
        self,
        text,
        *,
        method=None,
        url=None,
        status=200,
        enter_error=None,
        text_error=None,
    ):
        response = FakeResponse(text, status, enter_error, text_error)
        self.responses.append((method, url, response))
        return response

    def queue_json(self, value, **kwargs):
        return self.queue_text(json.dumps(value), **kwargs)

    def _request(self, method, url, kwargs):
        self.calls.append((method, url, kwargs))
        for index, queued in enumerate(self.responses):
            expected_method, expected_url, response = queued
            if expected_method is not None and expected_method != method:
                continue
            if expected_url is not None and expected_url != url:
                continue
            self.responses.pop(index)
            return response
        raise AssertionError(f"Unqueued {method} request to {url}")

    def get(self, url, **kwargs):
        return self._request("GET", url, kwargs)

    def post(self, url, **kwargs):
        return self._request("POST", url, kwargs)

    async def close(self):
        self.close_calls += 1
        self.closed = True


class BorrowedSession(FakeSession):
    """A close-only request shares transport but never owns its parent's lifetime."""

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self._retry_connection = True

    def _request(self, method, url, kwargs):
        assert self._retry_connection is False
        assert not self.parent.closed
        return self.parent._request(method, url, kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def stove(session):
    instance = Stove()
    instance.stove_host = "stove.test"
    instance._session = session
    return instance


@pytest.fixture
def raw_data():
    """Literal valid input, independent of constants and implementation code."""
    return {
        "algorithm": 7,
        "burn_level": 3,
        "day": 29,
        "hours": 23,
        "maintenance_alarms": 0,
        "message_id": 42,
        "minutes": 58,
        "month": 2,
        "new_fire_wood_hours": 1,
        "new_fire_wood_minutes": 7,
        "night_begin_hour": 22,
        "night_begin_minute": 15,
        "night_end_hour": 6,
        "night_end_minute": 30,
        "night_lowering": 2,
        "operation_mode": 2,
        "oxygen_level": 2099,
        "phase": 3,
        "refill_alarm": 1,
        "remote_refill_alarm": 0,
        "remote_version_build": 9,
        "remote_version_major": 4,
        "remote_version_minor": 5,
        "room_temperature": 2134,
        "safety_alarms": 0,
        "seconds": 57,
        "stove_temperature": 27349,
        "time_since_remote_msg": 31,
        "updating": 0,
        "valve1_position": 10,
        "valve2_position": 20,
        "valve3_position": 30,
        "version_build": 8,
        "version_major": 1,
        "version_minor": 2,
        "year": 2024,
    }
