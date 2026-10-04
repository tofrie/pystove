"""Freeze the published API and successful data behavior, not a redesigned API."""

import asyncio
from datetime import datetime, time, timedelta
import inspect
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import pystove as package
from pystove import Stove, pystove as legacy

DATA_CONSTANTS = {
    "DATA_ALGORITHM": "algorithm",
    "DATA_BEGIN_HOUR": "begin_hour",
    "DATA_BEGIN_MINUTE": "begin_minute",
    "DATA_ENABLE": "enable",
    "DATA_END_HOUR": "end_hour",
    "DATA_END_MINUTE": "end_minute",
    "DATA_BURN_LEVEL": "burn_level",
    "DATA_DATE_TIME": "date_time",
    "DATA_FILENAME": "file_name",
    "DATA_FIRMWARE_VERSION": "firmware_version",
    "DATA_FIRMWARE_VERSION_BUILD": "version_build",
    "DATA_FIRMWARE_VERSION_MAJOR": "version_major",
    "DATA_FIRMWARE_VERSION_MINOR": "version_minor",
    "DATA_IP": "ip",
    "DATA_LEVEL": "level",
    "DATA_MAINTENANCE_ALARMS": "maintenance_alarms",
    "DATA_MESSAGE_ID": "message_id",
    "DATA_MDNS": "mdns",
    "DATA_MODE": "mode",
    "DATA_NAME": "name",
    "DATA_NEW_FIREWOOD_ESTIMATE": "new_fire_wood_estimate",
    "DATA_NEW_FIREWOOD_HOURS": "new_fire_wood_hours",
    "DATA_NEW_FIREWOOD_MINUTES": "new_fire_wood_minutes",
    "DATA_NIGHT_BEGIN_HOUR": "night_begin_hour",
    "DATA_NIGHT_BEGIN_MINUTE": "night_begin_minute",
    "DATA_NIGHT_BEGIN_TIME": "night_begin_time",
    "DATA_NIGHT_END_HOUR": "night_end_hour",
    "DATA_NIGHT_END_MINUTE": "night_end_minute",
    "DATA_NIGHT_END_TIME": "night_end_time",
    "DATA_NIGHT_LOWERING": "night_lowering",
    "DATA_OPERATION_MODE": "operation_mode",
    "DATA_OXYGEN_LEVEL": "oxygen_level",
    "DATA_PHASE": "phase",
    "DATA_REFILL_ALARM": "refill_alarm",
    "DATA_REMOTE_REFILL_ALARM": "remote_refill_alarm",
    "DATA_REMOTE_VERSION": "remote_version",
    "DATA_REMOTE_VERSION_BUILD": "remote_version_build",
    "DATA_REMOTE_VERSION_MAJOR": "remote_version_major",
    "DATA_REMOTE_VERSION_MINOR": "remote_version_minor",
    "DATA_RESPONSE": "response",
    "DATA_ROOM_TEMPERATURE": "room_temperature",
    "DATA_SAFETY_ALARMS": "safety_alarms",
    "DATA_SSID": "ssid",
    "DATA_STOVE_TEMPERATURE": "stove_temperature",
    "DATA_SUCCESS": "success",
    "DATA_TEST_CONFIGURATION": "configuration",
    "DATA_TEST_O2_SENSOR": "o2_sensor",
    "DATA_TEST_TEMP_SENSOR": "t10_sensor",
    "DATA_TEST_VALVE1": "valve_primary",
    "DATA_TEST_VALVE2": "valve_secondary",
    "DATA_TEST_VALVE3": "valve_tertiary",
    "DATA_TIME_SINCE_REMOTE_MSG": "time_since_remote_msg",
    "DATA_TIME_TO_NEW_FIREWOOD": "time_to_new_fire_wood",
    "DATA_UPDATING": "updating",
    "DATA_VALVE1_POSITION": "valve1_position",
    "DATA_VALVE2_POSITION": "valve2_position",
    "DATA_VALVE3_POSITION": "valve3_position",
    "DATA_YEAR": "year",
    "DATA_MONTH": "month",
    "DATA_DAY": "day",
    "DATA_HOURS": "hours",
    "DATA_MINUTES": "minutes",
    "DATA_SECONDS": "seconds",
}

MODULE_ONLY_DATA_CONSTANTS = {
    "DATA_ENABLE",
    "DATA_FILENAME",
    "DATA_IP",
    "DATA_LEVEL",
    "DATA_MDNS",
    "DATA_MODE",
    "DATA_NAME",
    "DATA_RESPONSE",
    "DATA_SSID",
    "DATA_SUCCESS",
}

TABLES = {
    "MAINTENANCE_ALARMS": [
        "Stove Backup Battery Low",
        "O2 Sensor Fault",
        "O2 Sensor Offset",
        "Stove Temperature Sensor Fault",
        "Room Temperature Sensor Fault",
        "Communication Fault",
        "Room Temperature Sensor Battery Low",
    ],
    "NIGHT_LOWERING_STATES": ["Disabled", "Init", "Day", "Night", "Manual Night"],
    "OPERATION_MODES": [
        "Init",
        "Self Test",
        "Normal",
        "Temperature Fault",
        "O2 Fault",
        "Calibration",
        "Safety",
        "Manual",
        "MotorTest",
        "Slow Combustion",
        "Low Voltage",
    ],
    "PHASE": ["Ignition", "Burn", "Burn", "Burn", "Glow", "Standby"],
    "SAFETY_ALARMS": [
        "Valve Fault",
        "Valve Fault",
        "Valve Fault",
        "Bad Configuration",
        "Valve Disconnected",
        "Valve Disconnected",
        "Valve Disconnected",
        "Valve Calibration Error",
        "Valve Calibration Error",
        "Valve Calibration Error",
        "Chimney Overheat",
        "Door Open Too Long",
        "Manual Safety Alarm",
        "Stove Sensor Fault",
    ],
    "SELF_TEST_VALUES": [
        "Failed",
        "Passed",
        "Running",
        "Not Completed",
        "Not Started",
    ],
}

ENDPOINTS = {
    "STOVE_ACCESSPOINT_URL": "/esp/get_current_accesspoint",
    "STOVE_BURN_LEVEL_URL": "/set_burn_level",
    "STOVE_DATA_URL": "/get_stove_data",
    "STOVE_ID_URL": "/esp/get_identification",
    "STOVE_LIVE_DATA_URL": "/get_live_data",
    "STOVE_NIGHT_LOWERING_OFF_URL": "/set_night_lowering_off",
    "STOVE_NIGHT_LOWERING_ON_URL": "/set_night_lowering_on",
    "STOVE_NIGHT_TIME_URL": "/set_night_time",
    "STOVE_OPEN_FILE_URL": "/open_file",
    "STOVE_READ_OPEN_FILE_URL": "/read_open_file",
    "STOVE_REMOTE_REFILL_ALARM_URL": "/set_remote_refill_alarm",
    "STOVE_SET_TIME_URL": "/set_time",
    "STOVE_SELFTEST_RESULT_URL": "/get_selftest_result",
    "STOVE_SELFTEST_START_URL": "/start_selftest",
    "STOVE_START_URL": "/start",
}


def test_published_import_paths():
    assert package.Stove is Stove is legacy.Stove
    assert package.pystove is legacy
    assert type(package.__version__) is str


def test_hwam_stove_pinned_consumer_symbols():
    snapshot = json.loads(
        (Path(__file__).parent / "fixtures" / "hwam_contract.json").read_text(
            encoding="utf-8"
        )
    )
    assert snapshot["repository"] == "mvn23/hwam_stove"
    assert snapshot["commit"] == "2176600eece1c644f594a9608186bf395bb2488b"
    assert snapshot["manifest_requirement"] == "pystove==0.3a1"
    assert len(snapshot["module_symbols"]) == 31
    assert set(snapshot["module_symbols"]) == {
        "DATA_ALGORITHM",
        "DATA_BURN_LEVEL",
        "DATA_DATE_TIME",
        "DATA_FIRMWARE_VERSION",
        "DATA_MAINTENANCE_ALARMS",
        "DATA_MESSAGE_ID",
        "DATA_NEW_FIREWOOD_ESTIMATE",
        "DATA_NIGHT_BEGIN_TIME",
        "DATA_NIGHT_END_TIME",
        "DATA_NIGHT_LOWERING",
        "DATA_OPERATION_MODE",
        "DATA_OXYGEN_LEVEL",
        "DATA_PHASE",
        "DATA_REFILL_ALARM",
        "DATA_REMOTE_REFILL_ALARM",
        "DATA_REMOTE_VERSION",
        "DATA_ROOM_TEMPERATURE",
        "DATA_SAFETY_ALARMS",
        "DATA_STOVE_TEMPERATURE",
        "DATA_TIME_SINCE_REMOTE_MSG",
        "DATA_TIME_TO_NEW_FIREWOOD",
        "DATA_VALVE1_POSITION",
        "DATA_VALVE2_POSITION",
        "DATA_VALVE3_POSITION",
        "MAINTENANCE_ALARMS",
        "NIGHT_LOWERING_STATES",
        "OPERATION_MODES",
        "PHASE",
        "SAFETY_ALARMS",
        "Stove",
        "UNKNOWN",
    }
    expected = {**DATA_CONSTANTS, **TABLES, "Stove": Stove, "UNKNOWN": "Unknown"}
    for symbol in snapshot["module_symbols"]:
        assert getattr(legacy, symbol) == expected[symbol]


def test_exact_data_constants_and_root_exports():
    assert {
        name: value for name, value in vars(legacy).items() if name.startswith("DATA_")
    } == DATA_CONSTANTS
    assert {
        name: value for name, value in vars(package).items() if name.startswith("DATA_")
    } == {
        name: value
        for name, value in DATA_CONSTANTS.items()
        if name not in MODULE_ONLY_DATA_CONSTANTS
    }


@pytest.mark.parametrize("name", list(TABLES))
def test_published_tables_at_both_import_paths(name):
    assert getattr(legacy, name) == TABLES[name]
    assert getattr(package, name) is getattr(legacy, name)
    assert type(getattr(legacy, name)) is list


def test_module_constants_including_unknown_and_endpoints():
    assert legacy.UNKNOWN == "Unknown"
    assert not hasattr(package, "UNKNOWN")
    assert legacy.RESPONSE_OK == "OK"
    assert legacy.HTTP_HEADERS == {"Accept": "application/json"}
    assert {
        name: value for name, value in vars(legacy).items() if name.startswith("STOVE_")
    } == ENDPOINTS


def test_exact_public_stove_methods_and_signatures():
    expected = {
        "create": "(stove_host, loop=None, skip_ident=False)",
        "destroy": "(self)",
        "get_data": "(self)",
        "get_live_data": "(self)",
        "get_raw_data": "(self)",
        "self_test": "(self, delay=3, processed=True)",
        "set_burn_level": "(self, burn_level)",
        "set_night_lowering": "(self, state=None)",
        "set_night_lowering_hours": "(self, start=None, end=None)",
        "set_remote_refill_alarm": "(self, state=None)",
        "set_time": "(self, new_time=None)",
        "start": "(self)",
    }
    assert {
        name: str(inspect.signature(getattr(Stove, name)))
        for name in Stove.__dict__
        if not name.startswith("_")
    } == expected
    for name in expected:
        is_coroutine = inspect.iscoroutinefunction(getattr(Stove, name))
        assert is_coroutine is (name != "self_test")


@pytest.mark.parametrize("explicit_loop", [False, True])
def test_create_skipping_identification_and_destroy(
    monkeypatch, session, explicit_loop
):
    factory_calls = []

    def session_factory(**kwargs):
        factory_calls.append(kwargs)
        return session

    monkeypatch.setattr(legacy.aiohttp, "ClientSession", session_factory)

    async def exercise():
        loop = asyncio.get_running_loop()
        instance = await Stove.create(
            "stove.test", loop=loop if explicit_loop else None, skip_ident=True
        )
        assert instance._loop is loop
        assert instance.stove_host == "stove.test"
        assert instance._session is session
        assert {
            name: getattr(instance, name)
            for name in (
                "algo_version",
                "name",
                "series",
                "stove_ip",
                "stove_mdns",
                "stove_ssid",
            )
        } == {
            "algo_version": "Unknown",
            "name": "Unknown",
            "series": "Unknown",
            "stove_ip": "Unknown",
            "stove_mdns": "Unknown",
            "stove_ssid": "Unknown",
        }
        assert session.calls == []
        assert await instance.destroy() is None

    asyncio.run(exercise())
    assert factory_calls == [{"headers": {"Accept": "application/json"}}]
    assert session.closed is True
    assert session.close_calls == 1


def test_create_identification_preserves_legacy_file_wire_requests(
    monkeypatch, session
):
    session.queue_json(
        {"name": "HWAM", "ip": "192.0.2.5", "mdns": "hwam-abcdef"},
        url="http://stove.test/esp/get_identification",
    )
    session.queue_json(
        {"ssid": "HWAM LAN"}, url="http://stove.test/esp/get_current_accesspoint"
    )
    session.queue_json({"success": 1}, url="http://stove.test/open_file")
    session.queue_text(
        "<Info><Name>Algorithm 1.2</Name><StoveType>HWAM 3000</StoveType></Info>",
        url="http://stove.test/read_open_file",
    )
    session.queue_text("", url="http://stove.test/close_file")
    factory_calls = []

    def session_factory(**kwargs):
        factory_calls.append(kwargs)
        return session.factory(**kwargs)

    monkeypatch.setattr(legacy.aiohttp, "ClientSession", session_factory)

    async def exercise():
        instance = await Stove.create("stove.test")
        assert instance.name == "HWAM"
        assert instance.stove_ip == "192.0.2.5"
        assert instance.stove_mdns == "hwam-abcdef"
        assert instance.stove_ssid == "HWAM LAN"
        assert instance.algo_version == "Algorithm 1.2"
        assert instance.series == "HWAM 3000"
        await instance.destroy()

    asyncio.run(exercise())
    assert factory_calls == [
        {"headers": {"Accept": "application/json"}},
        {
            "connector": session.connector,
            "connector_owner": False,
            "cookie_jar": session.cookie_jar,
            "headers": session.headers,
        },
    ]
    assert session.calls == [
        ("GET", "http://stove.test/esp/get_identification", {}),
        ("GET", "http://stove.test/esp/get_current_accesspoint", {}),
        (
            "POST",
            "http://stove.test/open_file",
            {"data": '{"file_name":"info.xml","mode":1}'},
        ),
        (
            "POST",
            "http://stove.test/read_open_file",
            {"data": '{"file_name":"info.xml","mode":1}'},
        ),
        ("GET", "http://stove.test/close_file", {"allow_redirects": False}),
    ]
    assert session.closed is True
    assert session.responses == []


def test_get_data_exact_legacy_shape_and_types(stove, session, raw_data):
    session.queue_json(raw_data)
    result = asyncio.run(stove.get_data())
    assert result == {
        "algorithm": 7,
        "burn_level": 3,
        "maintenance_alarms": [],
        "message_id": 42,
        "new_fire_wood_estimate": datetime(2024, 3, 1, 1, 5, 57),
        "night_begin_time": time(22, 15),
        "night_end_time": time(6, 30),
        "night_lowering": "Day",
        "operation_mode": "Normal",
        "oxygen_level": 20,
        "phase": "Burn",
        "refill_alarm": 1,
        "remote_refill_alarm": 0,
        "remote_version": "4.5.9",
        "room_temperature": 21,
        "safety_alarms": [],
        "stove_temperature": 273,
        "time_since_remote_msg": 31,
        "date_time": datetime(2024, 2, 29, 23, 58, 57),
        "time_to_new_fire_wood": timedelta(hours=1, minutes=7),
        "updating": 0,
        "valve1_position": 10,
        "valve2_position": 20,
        "valve3_position": 30,
        "firmware_version": "1.2.8",
    }
    for key in (
        "algorithm",
        "burn_level",
        "message_id",
        "oxygen_level",
        "refill_alarm",
        "remote_refill_alarm",
        "room_temperature",
        "stove_temperature",
        "time_since_remote_msg",
        "updating",
        "valve1_position",
        "valve2_position",
        "valve3_position",
    ):
        assert type(result[key]) is int
    for key in (
        "phase",
        "operation_mode",
        "night_lowering",
        "remote_version",
        "firmware_version",
    ):
        assert type(result[key]) is str
    assert type(result["date_time"]) is datetime
    assert type(result["new_fire_wood_estimate"]) is datetime
    assert result["date_time"].tzinfo is None
    assert result["new_fire_wood_estimate"].tzinfo is None
    assert type(result["night_begin_time"]) is time
    assert type(result["night_end_time"]) is time
    assert type(result["time_to_new_fire_wood"]) is timedelta
    assert type(result["maintenance_alarms"]) is list
    assert type(result["safety_alarms"]) is list
    assert session.calls == [("GET", "http://stove.test/get_stove_data", {})]


@pytest.mark.parametrize(
    ("field", "raw_value", "expected"),
    [
        ("stove_temperature", 12345, 123),
        ("room_temperature", -2199, -21),
        ("oxygen_level", 1999.5, 19),
        ("stove_temperature", -199.9, -1),
        ("room_temperature", 99.9, 0),
        ("oxygen_level", -99.9, 0),
    ],
)
def test_get_data_truncates_scaled_measurements_to_integer(
    stove, session, raw_data, field, raw_value, expected
):
    raw_data[field] = raw_value
    session.queue_json(raw_data)
    result = asyncio.run(stove.get_data())
    assert result[field] == expected
    assert type(result[field]) is int


@pytest.mark.parametrize(
    ("field", "index", "expected"),
    [
        *(("phase", index, value) for index, value in enumerate(TABLES["PHASE"])),
        *(
            ("operation_mode", index, value)
            for index, value in enumerate(TABLES["OPERATION_MODES"])
        ),
        *(
            ("night_lowering", index, value)
            for index, value in enumerate(TABLES["NIGHT_LOWERING_STATES"])
        ),
    ],
)
def test_get_data_state_strings(stove, session, raw_data, field, index, expected):
    raw_data[field] = index
    session.queue_json(raw_data)
    result = asyncio.run(stove.get_data())
    assert result[field] == expected
    assert type(result[field]) is str


@pytest.mark.parametrize(
    ("table_name", "method"),
    [
        ("MAINTENANCE_ALARMS", "_get_maintenance_alarms_text"),
        ("SAFETY_ALARMS", "_get_safety_alarms_text"),
    ],
)
def test_every_alarm_bitmask_keeps_order_labels_and_duplicates(
    stove, table_name, method
):
    labels = TABLES[table_name]
    decode = getattr(stove, method)
    for mask in range(1 << len(labels)):
        expected = [label for bit, label in enumerate(labels) if mask & (1 << bit)]
        result = decode(mask)
        assert result == expected
        assert type(result) is list
        assert all(type(label) is str for label in result)
    # Undocumented higher bits were ignored by the released implementation.
    assert decode(1 << len(labels)) == []


def test_get_data_alarms_are_lists_and_duplicate_labels_survive(
    stove, session, raw_data
):
    raw_data["maintenance_alarms"] = 127
    raw_data["safety_alarms"] = 16383
    session.queue_json(raw_data)
    result = asyncio.run(stove.get_data())
    assert result["maintenance_alarms"] == TABLES["MAINTENANCE_ALARMS"]
    assert result["safety_alarms"] == TABLES["SAFETY_ALARMS"]
    assert result["safety_alarms"].count("Valve Fault") == 3
    assert result["safety_alarms"].count("Valve Disconnected") == 3
    assert result["safety_alarms"].count("Valve Calibration Error") == 3


@pytest.mark.parametrize("has_alarms", [False, True])
def test_hwam_consumer_state_and_alarm_lookups(stove, session, raw_data, has_alarms):
    if has_alarms:
        raw_data["maintenance_alarms"] = 64
        raw_data["safety_alarms"] = 8199
    session.queue_json(raw_data)
    data = asyncio.run(stove.get_data())
    # HA enumerated sensors consume strings from these exact option tables.
    assert data[legacy.DATA_PHASE] in legacy.PHASE
    assert data[legacy.DATA_OPERATION_MODE] in legacy.OPERATION_MODES
    assert data[legacy.DATA_NIGHT_LOWERING] in legacy.NIGHT_LOWERING_STATES
    # HA's aggregate alarm explicitly compares with []; individual alarms use
    # list membership, preserving duplicate valve labels for its three bits.
    assert (data[legacy.DATA_MAINTENANCE_ALARMS] != []) is has_alarms
    assert (data[legacy.DATA_SAFETY_ALARMS] != []) is has_alarms
    assert (
        "Room Temperature Sensor Battery Low" in data[legacy.DATA_MAINTENANCE_ALARMS]
    ) is has_alarms
    assert ("Valve Fault" in data[legacy.DATA_SAFETY_ALARMS]) is has_alarms
    assert ("Stove Sensor Fault" in data[legacy.DATA_SAFETY_ALARMS]) is has_alarms
    assert "Door Open Too Long" not in data[legacy.DATA_SAFETY_ALARMS]


def test_get_data_preserves_unscaled_numeric_and_boolean_types(
    stove, session, raw_data
):
    raw_data.update({"algorithm": 7.5, "valve1_position": 10.25, "refill_alarm": True})
    session.queue_json(raw_data)
    result = asyncio.run(stove.get_data())
    assert result["algorithm"] == 7.5
    assert type(result["algorithm"]) is float
    assert result["valve1_position"] == 10.25
    assert type(result["valve1_position"]) is float
    assert result["refill_alarm"] is True


def test_get_raw_data_returns_parsed_payload_without_scaling(stove, session, raw_data):
    raw_data["future_field"] = {"values": [1.5, None, False]}
    session.queue_json(raw_data)
    result = asyncio.run(stove.get_raw_data())
    assert result == raw_data
    assert result["stove_temperature"] == 27349
    assert result["phase"] == 3
    assert result["maintenance_alarms"] == 0
    assert session.calls == [("GET", "http://stove.test/get_stove_data", {})]


def test_get_raw_data_passes_through_the_json_result_object(stove, monkeypatch):
    payload = {"future_field": [1.25, None, True]}
    get_json = AsyncMock(return_value=payload)
    monkeypatch.setattr(stove, "_get_json", get_json)
    assert asyncio.run(stove.get_raw_data()) is payload
    get_json.assert_awaited_once_with("http://stove.test/get_stove_data")


def test_get_data_returns_none_when_raw_data_is_none(stove, monkeypatch):
    monkeypatch.setattr(stove, "get_raw_data", AsyncMock(return_value=None))
    assert asyncio.run(stove.get_data()) is None


def test_successful_get_releases_response_context(stove, session):
    response = session.queue_text("HWAM")
    assert asyncio.run(stove._get("http://stove.test/status")) == "HWAM"
    assert response.entered is True
    assert response.exited is True


def test_self_test_returns_legacy_async_iterator_without_starting_requests(
    stove, session
):
    iterator = stove.self_test(delay=7, processed=False)
    assert iterator.stove is stove
    assert iterator.delay == 7
    assert iterator.processed is False
    assert iterator.test_started is False
    assert iterator.test_finished is False
    assert iterator.__aiter__() is iterator
    assert inspect.iscoroutinefunction(iterator.__anext__)
    assert session.calls == []
