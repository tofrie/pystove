"""H4 status validation regressions and literal 0.3a1 data comparisons.

Fixtures are synthetic. No test contacts a controller or changes the wire
contract; invalid status data and transport failures are separate concerns.
"""

import asyncio
from collections import UserDict
from copy import deepcopy
import hashlib
from unittest.mock import AsyncMock

import pytest

from pystove import Stove, pystove as legacy
from tests.conftest import FakeSession

REQUIRED_FIELDS = (
    "algorithm",
    "burn_level",
    "day",
    "hours",
    "maintenance_alarms",
    "message_id",
    "minutes",
    "month",
    "new_fire_wood_hours",
    "new_fire_wood_minutes",
    "night_begin_hour",
    "night_begin_minute",
    "night_end_hour",
    "night_end_minute",
    "night_lowering",
    "operation_mode",
    "oxygen_level",
    "phase",
    "refill_alarm",
    "remote_refill_alarm",
    "remote_version_build",
    "remote_version_major",
    "remote_version_minor",
    "room_temperature",
    "safety_alarms",
    "seconds",
    "stove_temperature",
    "time_since_remote_msg",
    "updating",
    "valve1_position",
    "valve2_position",
    "valve3_position",
    "version_build",
    "version_major",
    "version_minor",
    "year",
)

PROCESSED_FIELDS = (
    "phase",
    "operation_mode",
    "night_lowering",
    "year",
    "month",
    "day",
    "hours",
    "minutes",
    "seconds",
    "night_begin_hour",
    "night_begin_minute",
    "night_end_hour",
    "night_end_minute",
    "new_fire_wood_hours",
    "new_fire_wood_minutes",
    "maintenance_alarms",
    "safety_alarms",
    "stove_temperature",
    "room_temperature",
    "oxygen_level",
)

STATE_TABLES = {
    "phase": ["Ignition", "Burn", "Burn", "Burn", "Glow", "Standby"],
    "operation_mode": [
        "Init", "Self Test", "Normal", "Temperature Fault", "O2 Fault",
        "Calibration", "Safety", "Manual", "MotorTest", "Slow Combustion",
        "Low Voltage",
    ],
    "night_lowering": ["Disabled", "Init", "Day", "Night", "Manual Night"],
}


# Literal method copied from tag 0.3a1, commit 6d2f7844d3fa49a339820c446aa47ba29e60e94a.
# Compile only this frozen method; tables and alarm helpers are protected separately.
BASELINE_GET_DATA = '''\
async def get_data(self):
    """Call get_raw_data, process result before returning."""
    data = await self.get_raw_data()
    if data is None:
        return
    phase = PHASE[data[DATA_PHASE]]
    stove_datetime = datetime(
        data[DATA_YEAR],
        data[DATA_MONTH],
        data[DATA_DAY],
        data[DATA_HOURS],
        data[DATA_MINUTES],
        data[DATA_SECONDS],
    )
    time_to_refuel = timedelta(
        hours=data[DATA_NEW_FIREWOOD_HOURS], minutes=data[DATA_NEW_FIREWOOD_MINUTES]
    )
    refuel_estimate = stove_datetime + time_to_refuel
    maintenance_alarms = self._get_maintenance_alarms_text(
        data[DATA_MAINTENANCE_ALARMS]
    )
    safety_alarms = self._get_safety_alarms_text(data[DATA_SAFETY_ALARMS])
    operation_mode = OPERATION_MODES[data[DATA_OPERATION_MODE]]
    night_lowering = NIGHT_LOWERING_STATES[data[DATA_NIGHT_LOWERING]]
    nighttime_start = time(
        hour=data[DATA_NIGHT_BEGIN_HOUR], minute=data[DATA_NIGHT_BEGIN_MINUTE]
    )
    nighttime_end = time(
        hour=data[DATA_NIGHT_END_HOUR], minute=data[DATA_NIGHT_END_MINUTE]
    )
    stove_version = (
        f"{data[DATA_FIRMWARE_VERSION_MAJOR]}"
        f".{data[DATA_FIRMWARE_VERSION_MINOR]}"
        f".{data[DATA_FIRMWARE_VERSION_BUILD]}"
    )
    remote_version = (
        f"{data[DATA_REMOTE_VERSION_MAJOR]}"
        f".{data[DATA_REMOTE_VERSION_MINOR]}"
        f".{data[DATA_REMOTE_VERSION_BUILD]}"
    )
    for item in (DATA_STOVE_TEMPERATURE, DATA_ROOM_TEMPERATURE, DATA_OXYGEN_LEVEL):
        data[item] = int(data[item] / 100)
    processed_data = {
        DATA_ALGORITHM: data[DATA_ALGORITHM],
        DATA_BURN_LEVEL: data[DATA_BURN_LEVEL],
        DATA_MAINTENANCE_ALARMS: maintenance_alarms,
        DATA_MESSAGE_ID: data[DATA_MESSAGE_ID],
        DATA_NEW_FIREWOOD_ESTIMATE: refuel_estimate,
        DATA_NIGHT_BEGIN_TIME: nighttime_start,
        DATA_NIGHT_END_TIME: nighttime_end,
        DATA_NIGHT_LOWERING: night_lowering,
        DATA_OPERATION_MODE: operation_mode,
        DATA_OXYGEN_LEVEL: data[DATA_OXYGEN_LEVEL],
        DATA_PHASE: phase,
        DATA_REFILL_ALARM: data[DATA_REFILL_ALARM],
        DATA_REMOTE_REFILL_ALARM: data[DATA_REMOTE_REFILL_ALARM],
        DATA_REMOTE_VERSION: remote_version,
        DATA_ROOM_TEMPERATURE: data[DATA_ROOM_TEMPERATURE],
        DATA_SAFETY_ALARMS: safety_alarms,
        DATA_STOVE_TEMPERATURE: data[DATA_STOVE_TEMPERATURE],
        DATA_TIME_SINCE_REMOTE_MSG: data[DATA_TIME_SINCE_REMOTE_MSG],
        DATA_DATE_TIME: stove_datetime,
        DATA_TIME_TO_NEW_FIREWOOD: time_to_refuel,
        DATA_UPDATING: data[DATA_UPDATING],
        DATA_VALVE1_POSITION: data[DATA_VALVE1_POSITION],
        DATA_VALVE2_POSITION: data[DATA_VALVE2_POSITION],
        DATA_VALVE3_POSITION: data[DATA_VALVE3_POSITION],
        DATA_FIRMWARE_VERSION: stove_version,
    }
    return processed_data
'''


def _status_result(stove, monkeypatch, payload):
    monkeypatch.setattr(stove, "get_raw_data", AsyncMock(return_value=payload))
    return asyncio.run(stove.get_data())


@pytest.mark.parametrize("payload", [None, {}, [], [1], "", "status", 1, 1.5, True])
def test_absent_or_non_mapping_status_returns_none(stove, monkeypatch, payload):
    assert _status_result(stove, monkeypatch, payload) is None


@pytest.mark.parametrize("missing", REQUIRED_FIELDS)
def test_every_required_status_field_is_required(
    stove, monkeypatch, raw_data, missing
):
    assert set(raw_data) == set(REQUIRED_FIELDS)
    del raw_data[missing]
    assert _status_result(stove, monkeypatch, raw_data) is None


@pytest.mark.parametrize("field", PROCESSED_FIELDS)
@pytest.mark.parametrize(
    "value", [None, "1", [], {}], ids=["null", "str", "list", "dict"]
)
def test_unprocessable_status_values_return_none(
    stove, monkeypatch, raw_data, field, value
):
    raw_data[field] = value
    assert _status_result(stove, monkeypatch, raw_data) is None


@pytest.mark.parametrize("field", ["phase", "operation_mode", "night_lowering"])
@pytest.mark.parametrize("value", [0.0, 1.5])
def test_state_indices_require_existing_integer_index_semantics(
    stove, monkeypatch, raw_data, field, value
):
    raw_data[field] = value
    assert _status_result(stove, monkeypatch, raw_data) is None


@pytest.mark.parametrize(
    ("field", "value"),
    [(field, value) for field, table in STATE_TABLES.items()
     for value in (len(table), -len(table) - 1, 99)],
)
def test_state_indices_outside_legacy_tables_return_none(
    stove, monkeypatch, raw_data, field, value
):
    raw_data[field] = value
    assert _status_result(stove, monkeypatch, raw_data) is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("year", 0), ("year", 10000), ("year", 10**100),
        ("month", 0), ("month", 13), ("day", 0), ("day", 30),
        ("hours", -1), ("hours", 24), ("minutes", -1), ("minutes", 60),
        ("seconds", -1), ("seconds", 60), ("night_begin_hour", -1),
        ("night_begin_hour", 24), ("night_begin_minute", -1),
        ("night_begin_minute", 60), ("night_end_hour", -1),
        ("night_end_hour", 24), ("night_end_minute", -1),
        ("night_end_minute", 60), ("year", 2024.0), ("seconds", 57.0),
        ("night_begin_minute", 15.0),
    ],
)
def test_invalid_calendar_and_clock_values_return_none(
    stove, monkeypatch, raw_data, field, value
):
    raw_data[field] = value
    assert _status_result(stove, monkeypatch, raw_data) is None


@pytest.mark.parametrize("field", ["new_fire_wood_hours", "new_fire_wood_minutes"])
@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), float("-inf"), 10**100],
    ids=["nan", "inf", "negative-inf", "integer-overflow"],
)
def test_unrepresentable_duration_values_return_none(
    stove, monkeypatch, raw_data, field, value
):
    raw_data[field] = value
    assert _status_result(stove, monkeypatch, raw_data) is None


@pytest.mark.parametrize("year, hours", [(9999, 24), (1, -24)])
def test_refuel_estimate_datetime_overflow_returns_none(
    stove, monkeypatch, raw_data, year, hours
):
    raw_data.update(
        year=year, month=12 if year == 9999 else 1,
        day=31 if year == 9999 else 1,
        new_fire_wood_hours=hours, new_fire_wood_minutes=0,
    )
    assert _status_result(stove, monkeypatch, raw_data) is None


@pytest.mark.parametrize(
    "field", ["stove_temperature", "room_temperature", "oxygen_level"]
)
@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), float("-inf"), 10**311],
    ids=["nan", "inf", "negative-inf", "integer-overflow"],
)
def test_unrepresentable_scaled_values_return_none(
    stove, monkeypatch, raw_data, field, value
):
    raw_data[field] = value
    assert _status_result(stove, monkeypatch, raw_data) is None


@pytest.mark.parametrize("field", ["maintenance_alarms", "safety_alarms"])
@pytest.mark.parametrize("value", [0.0, 1.5, float("nan"), float("inf")])
def test_invalid_alarm_bitmask_values_return_none(
    stove, monkeypatch, raw_data, field, value
):
    raw_data[field] = value
    assert _status_result(stove, monkeypatch, raw_data) is None


@pytest.mark.parametrize(
    "payload", [{"phase": 3}, {"phase": 99, "year": "bad", "safety_alarms": []}]
)
def test_partial_and_multiple_invalid_status_fields_return_none(
    stove, monkeypatch, payload
):
    assert _status_result(stove, monkeypatch, payload) is None


def test_multiple_invalid_complete_status_fields_return_none(
    stove, monkeypatch, raw_data
):
    raw_data.update(phase=99, year="bad", safety_alarms=[], oxygen_level=None)
    assert _status_result(stove, monkeypatch, raw_data) is None


@pytest.mark.parametrize(
    "error",
    [asyncio.CancelledError("status cancelled"), KeyboardInterrupt("interrupt"),
     SystemExit("exit"), BaseException("base failure")],
    ids=["cancelled", "keyboard-interrupt", "system-exit", "base-exception"],
)
def test_status_fetch_base_exceptions_propagate_unchanged(stove, monkeypatch, error):
    monkeypatch.setattr(stove, "get_raw_data", AsyncMock(side_effect=error))
    with pytest.raises(type(error)) as caught:
        asyncio.run(stove.get_data())
    assert caught.value is error


@pytest.mark.parametrize("error_type", [RuntimeError, TypeError, ValueError, KeyError])
def test_internal_fetch_errors_are_not_data_validation_failures(
    stove, monkeypatch, error_type
):
    error = error_type("unexpected internal fetch failure")
    monkeypatch.setattr(stove, "get_raw_data", AsyncMock(side_effect=error))
    with pytest.raises(error_type) as caught:
        asyncio.run(stove.get_data())
    assert caught.value is error


@pytest.mark.parametrize(
    "method", ["_get_maintenance_alarms_text", "_get_safety_alarms_text"]
)
@pytest.mark.parametrize(
    "error_type", [RuntimeError, TypeError, ValueError, IndexError]
)
def test_internal_alarm_helper_errors_on_valid_data_propagate(
    stove, monkeypatch, raw_data, method, error_type
):
    error = error_type("unexpected internal alarm decoder failure")

    def broken_decoder(bitmask):
        assert type(bitmask) is int
        raise error

    monkeypatch.setattr(stove, method, broken_decoder)
    monkeypatch.setattr(stove, "get_raw_data", AsyncMock(return_value=raw_data))
    with pytest.raises(error_type) as caught:
        asyncio.run(stove.get_data())
    assert caught.value is error


@pytest.mark.parametrize("field", ["phase", "year", "safety_alarms", "oxygen_level"])
def test_invalid_status_log_reports_field_or_category_without_value_or_body(
    stove, monkeypatch, raw_data, caplog, field
):
    secret = "CONTROLLER_BODY_SECRET_DO_NOT_LOG"
    raw_data[field] = {"secret": secret, "large_body": "x" * 100000}
    assert _status_result(stove, monkeypatch, raw_data) is None
    records = [record for record in caplog.records if record.name == "pystove.pystove"]
    assert len(records) == 1
    category = "date_time" if field == "year" else field
    assert category in records[0].getMessage()
    assert len(records[0].getMessage()) <= 300
    assert secret not in caplog.text
    assert "large_body" not in caplog.text


def test_multiple_invalid_values_emit_only_one_bounded_status_log(
    stove, monkeypatch, raw_data, caplog
):
    raw_data.update(phase=99, year="bad", safety_alarms=[], oxygen_level=None)
    assert _status_result(stove, monkeypatch, raw_data) is None
    records = [record for record in caplog.records if record.name == "pystove.pystove"]
    assert len(records) == 1
    assert any(
        field in records[0].getMessage()
        for field in ("phase", "year", "safety_alarms", "oxygen_level")
    )
    assert len(records[0].getMessage()) <= 300


def test_missing_field_log_names_field_without_dumping_other_data(
    stove, monkeypatch, raw_data, caplog
):
    del raw_data["year"]
    raw_data["ignored_secret"] = "CONTROLLER_SECRET_DO_NOT_LOG"
    assert _status_result(stove, monkeypatch, raw_data) is None
    records = [record for record in caplog.records if record.name == "pystove.pystove"]
    assert len(records) == 1
    assert "year" in records[0].getMessage()
    assert "missing" in records[0].getMessage().lower()
    assert "CONTROLLER_SECRET_DO_NOT_LOG" not in caplog.text


def test_non_mapping_response_log_does_not_include_response_body(
    stove, monkeypatch, caplog
):
    assert _status_result(stove, monkeypatch, "CONTROLLER_SECRET_DO_NOT_LOG") is None
    records = [record for record in caplog.records if record.name == "pystove.pystove"]
    assert len(records) == 1
    assert len(records[0].getMessage()) <= 300
    assert "CONTROLLER_SECRET_DO_NOT_LOG" not in caplog.text


VALID_VARIANTS = [
    pytest.param({}, id="complete-original-fixture"),
    *[
        pytest.param({field: index}, id=f"{field}-{index}")
        for field, table in STATE_TABLES.items()
        for index in range(len(table))
    ],
    *[
        pytest.param({field: index}, id=f"{field}-negative-{abs(index)}")
        for field, table in STATE_TABLES.items()
        for index in range(-len(table), 0)
    ],
    pytest.param(
        {field: True for field in PROCESSED_FIELDS}, id="processed-booleans"
    ),
    pytest.param(
        {"phase": False, "operation_mode": False, "night_lowering": False},
        id="false-state-indices",
    ),
    *[
        pytest.param({field: value}, id=f"{field}-scaled-{value}")
        for field, value in (
            ("stove_temperature", 12345), ("room_temperature", -2199),
            ("oxygen_level", 1999.5), ("stove_temperature", -199.9),
            ("room_temperature", 99.9), ("oxygen_level", -99.9),
        )
    ],
    *[
        pytest.param({field: 10**309}, id=f"{field}-large-finite-scaled-value")
        for field in ("stove_temperature", "room_temperature", "oxygen_level")
    ],
    pytest.param(
        {"maintenance_alarms": 127, "safety_alarms": 16383}, id="all-alarm-bits"
    ),
    pytest.param(
        {"maintenance_alarms": -1, "safety_alarms": -1}, id="negative-alarm-mask"
    ),
    pytest.param(
        {"maintenance_alarms": 1 << 100, "safety_alarms": 1 << 100},
        id="ignored-higher-alarm-bits",
    ),
    pytest.param(
        {"maintenance_alarms": True, "safety_alarms": False}, id="boolean-alarms"
    ),
    pytest.param(
        {"new_fire_wood_hours": 1.25, "new_fire_wood_minutes": 7.5},
        id="fractional-duration",
    ),
    pytest.param(
        {"new_fire_wood_hours": -1.25, "new_fire_wood_minutes": -7.5},
        id="negative-fractional-duration",
    ),
    pytest.param(
        {"new_fire_wood_hours": 0, "new_fire_wood_minutes": 300},
        id="duration-minutes-over-59",
    ),
    pytest.param(
        {"new_fire_wood_hours": 0, "new_fire_wood_minutes": 0}, id="zero-duration"
    ),
    pytest.param(
        {"version_major": "Unknown", "version_minor": None, "version_build": True,
         "remote_version_major": 4.5, "remote_version_minor": "6",
         "remote_version_build": False},
        id="existing-version-string-conversion",
    ),
    pytest.param(
        {"version_major": [], "version_minor": {}, "version_build": -1,
         "remote_version_major": None, "remote_version_minor": [1],
         "remote_version_build": {"future": True}},
        id="version-components-not-narrowed",
    ),
    pytest.param(
        {"algorithm": 7.5, "valve1_position": 10.25, "refill_alarm": True},
        id="unscaled-float-and-boolean-types",
    ),
    pytest.param(
        {"algorithm": None, "burn_level": "unknown", "message_id": [],
         "refill_alarm": {}, "remote_refill_alarm": None, "time_since_remote_msg": "31",
         "updating": False, "valve1_position": {"position": 10},
         "valve2_position": [20], "valve3_position": None},
        id="unscaled-fields-passed-through",
    ),
    pytest.param(
        {"future_field": {"secret": "ignored", "values": [1.5, None, False]}},
        id="additional-fields-ignored",
    ),
]


def _baseline_function():
    assert hashlib.sha256(BASELINE_GET_DATA.encode()).hexdigest() == (
        "7349b2a5071f7ec181488bba88420fc17b04bba10181e969cf029958d579cc1c"
    )
    namespace = {}
    exec(
        compile(BASELINE_GET_DATA, "<pystove-0.3a1-get_data>", "exec"),
        vars(legacy),
        namespace,
    )
    return namespace["get_data"]


def _assert_same_data_contract(actual, expected):
    assert type(actual) is type(expected) is dict
    assert len(actual) == len(expected) == 25
    assert list(actual) == list(expected)
    for key in expected:
        assert key in actual
        assert type(actual[key]) is type(expected[key]), key
        assert actual[key] == expected[key], key


@pytest.mark.parametrize("changes", VALID_VARIANTS)
def test_valid_status_values_and_types_match_literal_0_3a1(
    stove, session, raw_data, changes
):
    raw_data.update(deepcopy(changes))
    baseline_stove = Stove()
    baseline_stove.stove_host = "stove.test"
    baseline_session = FakeSession()
    baseline_stove._session = baseline_session
    baseline_session.queue_json(deepcopy(raw_data), method="GET")
    session.queue_json(deepcopy(raw_data), method="GET")
    expected = asyncio.run(_baseline_function()(baseline_stove))
    actual = asyncio.run(stove.get_data())
    _assert_same_data_contract(actual, expected)
    assert session.calls == baseline_session.calls == [
        ("GET", "http://stove.test/get_stove_data", {})
    ]
    assert session.responses == baseline_session.responses == []


class _StatusDict(dict):
    """A normal mutable status dictionary subclass remains a valid input."""


@pytest.mark.parametrize("mapping_class", [dict, _StatusDict, UserDict])
def test_valid_mutable_mapping_and_existing_sensor_mutation_are_preserved(
    stove, monkeypatch, raw_data, mapping_class
):
    baseline_stove = Stove()
    baseline_input = mapping_class(deepcopy(raw_data))
    current_input = mapping_class(deepcopy(raw_data))
    baseline_stove.get_raw_data = AsyncMock(return_value=baseline_input)
    monkeypatch.setattr(stove, "get_raw_data", AsyncMock(return_value=current_input))
    expected = asyncio.run(_baseline_function()(baseline_stove))
    actual = asyncio.run(stove.get_data())
    _assert_same_data_contract(actual, expected)
    assert baseline_input == current_input
    assert current_input["stove_temperature"] == 273
    assert current_input["room_temperature"] == 21
    assert current_input["oxygen_level"] == 20


def test_valid_status_preserves_unknown_literal_and_emits_no_validation_log(
    stove, monkeypatch, raw_data, caplog
):
    raw_data.update(algorithm="Unknown", version_major="Unknown")
    result = _status_result(stove, monkeypatch, raw_data)
    assert result["algorithm"] == legacy.UNKNOWN
    assert result["firmware_version"] == "Unknown.2.8"
    assert not caplog.records
