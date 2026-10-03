"""Preserve the successful 0.3a1 command wire contract used by hwam_stove.

Expected requests are independent literal values. In particular, they are not
created with the runtime constants or its JSON serialization helper.
"""

import asyncio
from datetime import datetime, time, timedelta, timezone

import pytest

from pystove import pystove


@pytest.mark.parametrize(
    ("level", "body"),
    [
        (0, '{"level":0}'),
        (1, '{"level":1}'),
        (2, '{"level":2}'),
        (3, '{"level":3}'),
        (4, '{"level":4}'),
        (5, '{"level":5}'),
    ],
)
def test_burn_level_exact_request(stove, session, level, body):
    session.queue_text('{"response":"OK"}')

    result = asyncio.run(stove.set_burn_level(level))

    assert result is True
    assert session.calls == [
        ("POST", "http://stove.test/set_burn_level", {"data": body})
    ]


@pytest.mark.parametrize(
    ("state", "url"),
    [
        (True, "http://stove.test/set_night_lowering_on"),
        (False, "http://stove.test/set_night_lowering_off"),
    ],
)
def test_night_lowering_explicit_state(stove, session, state, url):
    session.queue_text('{"response":"OK"}')

    result = asyncio.run(stove.set_night_lowering(state))

    assert result is True
    assert session.calls == [("GET", url, {})]


@pytest.mark.parametrize("explicit_none", [False, True])
@pytest.mark.parametrize(
    ("current", "url"),
    [
        (0, "http://stove.test/set_night_lowering_on"),
        (1, "http://stove.test/set_night_lowering_off"),
        (2, "http://stove.test/set_night_lowering_off"),
        (3, "http://stove.test/set_night_lowering_off"),
        (4, "http://stove.test/set_night_lowering_off"),
    ],
)
def test_night_lowering_toggle_reads_raw_state(
    stove, session, explicit_none, current, url
):
    session.queue_json({"night_lowering": current})
    session.queue_text('{"response":"OK"}')

    args = (None,) if explicit_none else ()
    result = asyncio.run(stove.set_night_lowering(*args))

    assert result is True
    assert session.calls == [
        ("GET", "http://stove.test/get_stove_data", {}),
        ("GET", url, {}),
    ]


@pytest.mark.parametrize(
    ("start", "end", "body"),
    [
        (
            time(22, 15, 51),
            time(6, 30, 29),
            '{"begin_hour":22,"begin_minute":15,"end_hour":6,"end_minute":30}',
        ),
        (
            time(0, 0),
            time(0, 0),
            '{"begin_hour":0,"begin_minute":0,"end_hour":0,"end_minute":0}',
        ),
    ],
)
def test_night_hours_explicit_values(stove, session, start, end, body):
    session.queue_text('{"response":"OK"}')

    result = asyncio.run(stove.set_night_lowering_hours(start, end))

    assert result is True
    assert session.calls == [
        ("POST", "http://stove.test/set_night_time", {"data": body})
    ]


@pytest.mark.parametrize(
    ("kwargs", "body"),
    [
        (
            {},
            '{"begin_hour":23,"begin_minute":41,"end_hour":6,"end_minute":17}',
        ),
        (
            {"start": None, "end": None},
            '{"begin_hour":23,"begin_minute":41,"end_hour":6,"end_minute":17}',
        ),
        (
            {"end": time(7, 25)},
            '{"begin_hour":23,"begin_minute":41,"end_hour":7,"end_minute":25}',
        ),
        (
            {"start": None, "end": time(7, 25)},
            '{"begin_hour":23,"begin_minute":41,"end_hour":7,"end_minute":25}',
        ),
        (
            {"start": time(0, 0)},
            '{"begin_hour":0,"begin_minute":0,"end_hour":6,"end_minute":17}',
        ),
        (
            {"start": time(0, 0), "end": None},
            '{"begin_hour":0,"begin_minute":0,"end_hour":6,"end_minute":17}',
        ),
    ],
)
def test_night_hours_missing_components_preserve_current_values(
    stove, session, raw_data, kwargs, body
):
    raw_data.update(
        night_begin_hour=23,
        night_begin_minute=41,
        night_end_hour=6,
        night_end_minute=17,
    )
    session.queue_json(raw_data)
    session.queue_text('{"response":"OK"}')

    result = asyncio.run(stove.set_night_lowering_hours(**kwargs))

    assert result is True
    assert session.calls == [
        ("GET", "http://stove.test/get_stove_data", {}),
        ("POST", "http://stove.test/set_night_time", {"data": body}),
    ]


@pytest.mark.parametrize(
    ("state", "body"),
    [(True, '{"enable":1}'), (False, '{"enable":0}')],
)
def test_remote_refill_explicit_state(stove, session, state, body):
    session.queue_text('{"response":"OK"}')

    result = asyncio.run(stove.set_remote_refill_alarm(state))

    assert result is True
    assert session.calls == [
        ("POST", "http://stove.test/set_remote_refill_alarm", {"data": body})
    ]


@pytest.mark.parametrize("explicit_none", [False, True])
@pytest.mark.parametrize(
    ("current", "body"),
    [(0, '{"enable":1}'), (1, '{"enable":0}'), (2, '{"enable":1}')],
)
def test_remote_refill_toggle_reads_raw_state(
    stove, session, explicit_none, current, body
):
    session.queue_json({"remote_refill_alarm": current})
    session.queue_text('{"response":"OK"}')

    args = (None,) if explicit_none else ()
    result = asyncio.run(stove.set_remote_refill_alarm(*args))

    assert result is True
    assert session.calls == [
        ("GET", "http://stove.test/get_stove_data", {}),
        ("POST", "http://stove.test/set_remote_refill_alarm", {"data": body}),
    ]


@pytest.mark.parametrize(
    ("new_time", "body"),
    [
        (
            datetime(2025, 1, 31, 23, 59, 58, 123456),
            '{"year":2025,"month":0,"day":31,"hours":23,"minutes":59,"seconds":58}',
        ),
        (
            datetime(2025, 12, 1, 0, 2, 3),
            '{"year":2025,"month":11,"day":1,"hours":0,"minutes":2,"seconds":3}',
        ),
        (
            datetime(2025, 7, 4, 19, 8, 9, tzinfo=timezone(timedelta(hours=2))),
            '{"year":2025,"month":6,"day":4,"hours":19,"minutes":8,"seconds":9}',
        ),
    ],
)
def test_set_time_keeps_calendar_fields_and_zero_based_month(
    stove, session, new_time, body
):
    session.queue_text('{"response":"OK"}')

    result = asyncio.run(stove.set_time(new_time))

    assert result is True
    assert session.calls == [
        ("POST", "http://stove.test/set_time", {"data": body})
    ]


@pytest.mark.parametrize("explicit_none", [False, True])
def test_set_time_defaults_to_host_clock(stove, session, monkeypatch, explicit_none):
    clock_calls = []

    class FixedClock:
        @staticmethod
        def now():
            clock_calls.append("now")
            return datetime(2026, 10, 2, 12, 34, 56)

    monkeypatch.setattr(pystove, "datetime", FixedClock)
    session.queue_text('{"response":"OK"}')

    args = (None,) if explicit_none else ()
    result = asyncio.run(stove.set_time(*args))

    assert result is True
    assert clock_calls == ["now"]
    assert session.calls == [
        (
            "POST",
            "http://stove.test/set_time",
            {
                "data": (
                    '{"year":2026,"month":9,"day":2,'
                    '"hours":12,"minutes":34,"seconds":56}'
                )
            },
        )
    ]


def test_start_exact_request(stove, session):
    session.queue_text('{"response":"OK"}')

    result = asyncio.run(stove.start())

    assert result is True
    assert session.calls == [("GET", "http://stove.test/start", {})]


@pytest.mark.parametrize(
    ("method_name", "args", "expected_request"),
    [
        (
            "set_burn_level",
            (3,),
            ("POST", "http://stove.test/set_burn_level", {"data": '{"level":3}'}),
        ),
        (
            "set_night_lowering",
            (True,),
            ("GET", "http://stove.test/set_night_lowering_on", {}),
        ),
        (
            "set_night_lowering_hours",
            (time(22, 15), time(6, 30)),
            (
                "POST",
                "http://stove.test/set_night_time",
                {
                    "data": (
                        '{"begin_hour":22,"begin_minute":15,'
                        '"end_hour":6,"end_minute":30}'
                    )
                },
            ),
        ),
        (
            "set_remote_refill_alarm",
            (False,),
            (
                "POST",
                "http://stove.test/set_remote_refill_alarm",
                {"data": '{"enable":0}'},
            ),
        ),
        (
            "set_time",
            (datetime(2025, 1, 31, 23, 59, 58),),
            (
                "POST",
                "http://stove.test/set_time",
                {
                    "data": (
                        '{"year":2025,"month":0,"day":31,'
                        '"hours":23,"minutes":59,"seconds":58}'
                    )
                },
            ),
        ),
        ("start", (), ("GET", "http://stove.test/start", {})),
    ],
)
@pytest.mark.parametrize(
    "response", ['{"response":"NOT_OK"}', "{}", '{"response":null}']
)
def test_commands_return_false_for_non_ok_or_missing_response(
    stove, session, method_name, args, expected_request, response
):
    session.queue_text(response)

    result = asyncio.run(getattr(stove, method_name)(*args))

    assert result is False
    assert session.calls == [expected_request]
