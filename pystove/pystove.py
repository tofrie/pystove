# This file is part of pystove.
#
# pystove is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pystove is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pystove.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2019 Milan van Nugteren
#

import asyncio
from datetime import datetime, time, timedelta
import json
import logging
import xml.etree.ElementTree as ET

import aiohttp

_LOGGER = logging.getLogger(__name__)

DATA_ALGORITHM = "algorithm"
DATA_BEGIN_HOUR = "begin_hour"
DATA_BEGIN_MINUTE = "begin_minute"
DATA_ENABLE = "enable"
DATA_END_HOUR = "end_hour"
DATA_END_MINUTE = "end_minute"
DATA_BURN_LEVEL = "burn_level"
DATA_DATE_TIME = "date_time"
DATA_FILENAME = "file_name"
DATA_FIRMWARE_VERSION = "firmware_version"
DATA_FIRMWARE_VERSION_BUILD = "version_build"
DATA_FIRMWARE_VERSION_MAJOR = "version_major"
DATA_FIRMWARE_VERSION_MINOR = "version_minor"
DATA_IP = "ip"
DATA_LEVEL = "level"
DATA_MAINTENANCE_ALARMS = "maintenance_alarms"
DATA_MESSAGE_ID = "message_id"
DATA_MDNS = "mdns"
DATA_MODE = "mode"
DATA_NAME = "name"
DATA_NEW_FIREWOOD_ESTIMATE = "new_fire_wood_estimate"
DATA_NEW_FIREWOOD_HOURS = "new_fire_wood_hours"
DATA_NEW_FIREWOOD_MINUTES = "new_fire_wood_minutes"
DATA_NIGHT_BEGIN_HOUR = "night_begin_hour"
DATA_NIGHT_BEGIN_MINUTE = "night_begin_minute"
DATA_NIGHT_BEGIN_TIME = "night_begin_time"
DATA_NIGHT_END_HOUR = "night_end_hour"
DATA_NIGHT_END_MINUTE = "night_end_minute"
DATA_NIGHT_END_TIME = "night_end_time"
DATA_NIGHT_LOWERING = "night_lowering"
DATA_OPERATION_MODE = "operation_mode"
DATA_OXYGEN_LEVEL = "oxygen_level"
DATA_PHASE = "phase"
DATA_REFILL_ALARM = "refill_alarm"
DATA_REMOTE_REFILL_ALARM = "remote_refill_alarm"
DATA_REMOTE_VERSION = "remote_version"
DATA_REMOTE_VERSION_BUILD = "remote_version_build"
DATA_REMOTE_VERSION_MAJOR = "remote_version_major"
DATA_REMOTE_VERSION_MINOR = "remote_version_minor"
DATA_RESPONSE = "response"
DATA_ROOM_TEMPERATURE = "room_temperature"
DATA_SAFETY_ALARMS = "safety_alarms"
DATA_SSID = "ssid"
DATA_STOVE_TEMPERATURE = "stove_temperature"
DATA_SUCCESS = "success"
DATA_TEST_CONFIGURATION = "configuration"
DATA_TEST_O2_SENSOR = "o2_sensor"
DATA_TEST_TEMP_SENSOR = "t10_sensor"
DATA_TEST_VALVE1 = "valve_primary"
DATA_TEST_VALVE2 = "valve_secondary"
DATA_TEST_VALVE3 = "valve_tertiary"
DATA_TIME_SINCE_REMOTE_MSG = "time_since_remote_msg"
DATA_TIME_TO_NEW_FIREWOOD = "time_to_new_fire_wood"
DATA_UPDATING = "updating"
DATA_VALVE1_POSITION = "valve1_position"
DATA_VALVE2_POSITION = "valve2_position"
DATA_VALVE3_POSITION = "valve3_position"

DATA_YEAR = "year"
DATA_MONTH = "month"
DATA_DAY = "day"
DATA_HOURS = "hours"
DATA_MINUTES = "minutes"
DATA_SECONDS = "seconds"

HTTP_HEADERS = {"Accept": "application/json"}

MAINTENANCE_ALARMS = [
    "Stove Backup Battery Low",
    "O2 Sensor Fault",
    "O2 Sensor Offset",
    "Stove Temperature Sensor Fault",
    "Room Temperature Sensor Fault",
    "Communication Fault",
    "Room Temperature Sensor Battery Low",
]

NIGHT_LOWERING_STATES = [
    "Disabled",
    "Init",
    "Day",
    "Night",
    "Manual Night",
]

OPERATION_MODES = [
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
]

PHASE = [
    "Ignition",
    "Burn",
    "Burn",
    "Burn",
    "Glow",
    "Standby",
]

RESPONSE_OK = "OK"

SAFETY_ALARMS = [
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
]

SELF_TEST_VALUES = [
    "Failed",
    "Passed",
    "Running",
    "Not Completed",
    "Not Started",
]

STOVE_ACCESSPOINT_URL = "/esp/get_current_accesspoint"
STOVE_BURN_LEVEL_URL = "/set_burn_level"
STOVE_DATA_URL = "/get_stove_data"
STOVE_ID_URL = "/esp/get_identification"
STOVE_LIVE_DATA_URL = "/get_live_data"
STOVE_NIGHT_LOWERING_OFF_URL = "/set_night_lowering_off"
STOVE_NIGHT_LOWERING_ON_URL = "/set_night_lowering_on"
STOVE_NIGHT_TIME_URL = "/set_night_time"
STOVE_OPEN_FILE_URL = "/open_file"
STOVE_READ_OPEN_FILE_URL = "/read_open_file"
STOVE_REMOTE_REFILL_ALARM_URL = "/set_remote_refill_alarm"
STOVE_SET_TIME_URL = "/set_time"
STOVE_SELFTEST_RESULT_URL = "/get_selftest_result"
STOVE_SELFTEST_START_URL = "/start_selftest"
STOVE_START_URL = "/start"

UNKNOWN = "Unknown"

_INFO_FILE_CLOSE_TIMEOUT = 5.0


def _post_response_ok(response_text):
    """Return whether a received POST body confirms success, without retrying.

    False means no valid confirmation, not that the command was not executed.
    """
    try:
        response = json.loads(response_text)
    except json.JSONDecodeError:
        return False
    if not isinstance(response, dict):
        return False
    return response.get(DATA_RESPONSE) == RESPONSE_OK


async def _finish_initialization_cleanup(operation, message):
    """Finish owned cleanup without replacing the initialization exception."""
    try:
        coroutine = operation()
        try:
            cleanup = asyncio.ensure_future(coroutine)
        except BaseException:
            coroutine.close()
            raise
        while not cleanup.done():
            try:
                await asyncio.wait((cleanup,))
            except asyncio.CancelledError:
                # Further caller cancellation must not interrupt owned cleanup.
                continue
        cleanup.result()
    except BaseException:
        _LOGGER.error(message, exc_info=True)


class Stove:
    """Abstraction of a Stove object."""

    @classmethod
    async def create(cls, stove_host, loop=None, skip_ident=False):
        """Async create the Stove object."""
        self = cls()
        self._loop = loop or asyncio.get_event_loop()
        self.stove_host = stove_host
        self.algo_version = UNKNOWN
        self.name = UNKNOWN
        self.series = UNKNOWN
        self.stove_ip = UNKNOWN
        self.stove_mdns = UNKNOWN
        self.stove_ssid = UNKNOWN
        session = aiohttp.ClientSession(headers=HTTP_HEADERS)
        try:
            self._session = session
            if not skip_ident:
                await self._identify()
        except BaseException:
            async def close_session():
                await session.close()

            await _finish_initialization_cleanup(
                close_session, "Unable to close session after failed initialization."
            )
            raise
        return self

    async def destroy(self):
        await self._session.close()

    @property
    def cached_diagnostics(self):
        """Copy optional diagnostics from the last successful get_data, without I/O.

        Empty before the first valid status. Failed/cancelled reads retain the
        last successful snapshot; a newer valid status replaces it completely.
        This cache does not establish freshness or change the 25-key result.
        """
        return getattr(self, "_cached_diagnostics", {}).copy()

    def _cache_diagnostics(self, data):
        """Accept only the two optional diagnostic values, never raw objects."""
        from contextlib import suppress

        diagnostics = {}
        beeps = data.get("remote_refill_beeps")
        if type(beeps) is int and beeps >= 0:
            diagnostics["remote_refill_beeps"] = beeps
        parts = tuple(data.get(f"wifi_version_{part}")
                      for part in ("major", "minor", "build"))
        if all(type(part) is int and part >= 0 for part in parts):
            # Python's integer-to-string limit must not reject valid status.
            with suppress(ValueError):
                diagnostics["wifi_version"] = ".".join(map(str, parts))
        self._cached_diagnostics = diagnostics

    async def get_data(self):
        """Call get_raw_data, process result before returning."""
        from collections.abc import MutableMapping

        data = await self.get_raw_data()
        if not isinstance(data, MutableMapping):
            _LOGGER.warning("Invalid stove status: expected a mutable mapping.")
            return
        required = (
            DATA_PHASE,
            DATA_YEAR, DATA_MONTH, DATA_DAY, DATA_HOURS, DATA_MINUTES, DATA_SECONDS,
            DATA_NEW_FIREWOOD_HOURS, DATA_NEW_FIREWOOD_MINUTES,
            DATA_MAINTENANCE_ALARMS, DATA_SAFETY_ALARMS,
            DATA_OPERATION_MODE, DATA_NIGHT_LOWERING,
            DATA_NIGHT_BEGIN_HOUR, DATA_NIGHT_BEGIN_MINUTE,
            DATA_NIGHT_END_HOUR, DATA_NIGHT_END_MINUTE,
            DATA_FIRMWARE_VERSION_MAJOR, DATA_FIRMWARE_VERSION_MINOR,
            DATA_FIRMWARE_VERSION_BUILD,
            DATA_REMOTE_VERSION_MAJOR, DATA_REMOTE_VERSION_MINOR,
            DATA_REMOTE_VERSION_BUILD,
            DATA_STOVE_TEMPERATURE, DATA_ROOM_TEMPERATURE, DATA_OXYGEN_LEVEL,
            DATA_ALGORITHM, DATA_BURN_LEVEL, DATA_MESSAGE_ID,
            DATA_REFILL_ALARM, DATA_REMOTE_REFILL_ALARM,
            DATA_TIME_SINCE_REMOTE_MSG, DATA_UPDATING,
            DATA_VALVE1_POSITION, DATA_VALVE2_POSITION, DATA_VALVE3_POSITION,
        )
        for field in required:
            if field not in data:
                _LOGGER.warning(
                    "Invalid stove status: missing required field %s.", field
                )
                return
        try:
            field = DATA_PHASE
            phase = PHASE[data[DATA_PHASE]]
            field = DATA_DATE_TIME
            stove_datetime = datetime(
                data[DATA_YEAR],
                data[DATA_MONTH],
                data[DATA_DAY],
                data[DATA_HOURS],
                data[DATA_MINUTES],
                data[DATA_SECONDS],
            )
            field = DATA_TIME_TO_NEW_FIREWOOD
            time_to_refuel = timedelta(
                hours=data[DATA_NEW_FIREWOOD_HOURS],
                minutes=data[DATA_NEW_FIREWOOD_MINUTES],
            )
            field = DATA_NEW_FIREWOOD_ESTIMATE
            refuel_estimate = stove_datetime + time_to_refuel
            field = DATA_OPERATION_MODE
            operation_mode = OPERATION_MODES[data[DATA_OPERATION_MODE]]
            field = DATA_NIGHT_LOWERING
            night_lowering = NIGHT_LOWERING_STATES[data[DATA_NIGHT_LOWERING]]
            field = DATA_NIGHT_BEGIN_TIME
            nighttime_start = time(
                hour=data[DATA_NIGHT_BEGIN_HOUR], minute=data[DATA_NIGHT_BEGIN_MINUTE]
            )
            field = DATA_NIGHT_END_TIME
            nighttime_end = time(
                hour=data[DATA_NIGHT_END_HOUR], minute=data[DATA_NIGHT_END_MINUTE]
            )
            for field in (DATA_MAINTENANCE_ALARMS, DATA_SAFETY_ALARMS):
                # Preserve the existing integer bitmask operation, including bools
                # and negative/high masks, without catching errors from helpers.
                1 & data[field]
            scaled = {}
            for field in (
                DATA_STOVE_TEMPERATURE, DATA_ROOM_TEMPERATURE, DATA_OXYGEN_LEVEL
            ):
                scaled[field] = int(data[field] / 100)
        except (TypeError, ValueError, IndexError, OverflowError) as exc:
            _LOGGER.warning(
                "Invalid stove status field %s (%s).", field, type(exc).__name__
            )
            return
        maintenance_alarms = self._get_maintenance_alarms_text(
            data[DATA_MAINTENANCE_ALARMS]
        )
        safety_alarms = self._get_safety_alarms_text(data[DATA_SAFETY_ALARMS])
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
        for item, value in scaled.items():
            data[item] = value
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
        self._cache_diagnostics(data)
        return processed_data

    async def get_live_data(self):
        """Get 'live' temp and o2 data from the last 2 hours."""
        bin_arr = bytearray(
            await self._get("http://" + self.stove_host + STOVE_LIVE_DATA_URL), "utf-8"
        )
        if len(bin_arr) != 120:
            _LOGGER.error("get_live_data got unexpected response from stove.")
            return
        data_out = {
            DATA_STOVE_TEMPERATURE: [],
            DATA_OXYGEN_LEVEL: [],
        }
        for i in range(120):
            data_out[DATA_STOVE_TEMPERATURE].append(
                (
                    bin_arr[i * 4] << 4
                    | bin_arr[i * 4 + 1] << 0
                    | bin_arr[i * 4 + 2] << 12
                    | bin_arr[i * 4 + 3] << 8
                )
                / 100
            )
            data_out[DATA_OXYGEN_LEVEL].append(
                (
                    bin_arr[i * 4 + 480] << 4
                    | bin_arr[i * 4 + 481] << 0
                    | bin_arr[i * 4 + 482] << 12
                    | bin_arr[i * 4 + 483] << 8
                )
                / 100
            )
        return data_out

    async def get_raw_data(self):
        """Request an update from the stove, return raw result."""
        return await self._get_json("http://" + self.stove_host + STOVE_DATA_URL)

    def self_test(self, delay=3, processed=True):
        """Return self test async generator."""
        return _SelfTest(self, delay, processed)

    async def set_burn_level(self, burn_level):
        """Set the desired burnlevel."""
        data = {DATA_LEVEL: burn_level}
        json_str = await self._post_command(
            "http://" + self.stove_host + STOVE_BURN_LEVEL_URL, data
        )
        if json_str is None:
            _LOGGER.error("Got empty or no response from stove.")
            return False
        return _post_response_ok(json_str)

    async def set_night_lowering(self, state=None):
        """Switch/toggle night lowering (True=on, False=off, None=toggle)."""
        if state is None:
            data = await self.get_raw_data()
            # 0 == Off
            # 2 == On outside night hours
            # 3 == On inside night hours
            # When does night_lowering == 1 happen?
            cur_state = data[DATA_NIGHT_LOWERING] > 0
        else:
            cur_state = not state
        url = STOVE_NIGHT_LOWERING_OFF_URL if cur_state else STOVE_NIGHT_LOWERING_ON_URL
        result = await self._get_json("http://" + self.stove_host + url)
        return result.get(DATA_RESPONSE) == RESPONSE_OK

    async def set_night_lowering_hours(self, start=None, end=None):
        """Set night lowering start and end time."""
        if start is None or end is None:
            data = await self.get_data()
        start = start or data[DATA_NIGHT_BEGIN_TIME]
        end = end or data[DATA_NIGHT_END_TIME]
        data = {
            DATA_BEGIN_HOUR: start.hour,
            DATA_BEGIN_MINUTE: start.minute,
            DATA_END_HOUR: end.hour,
            DATA_END_MINUTE: end.minute,
        }
        json_str = await self._post_command(
            "http://" + self.stove_host + STOVE_NIGHT_TIME_URL, data
        )
        if json_str is None:
            _LOGGER.error("Got empty or no response from stove.")
            return False
        return _post_response_ok(json_str)

    async def set_remote_refill_alarm(self, state=None):
        """Set or toggle remote_refill_alarm setting."""
        if state is None:
            data = await self.get_raw_data()
            cur_state = data[DATA_REMOTE_REFILL_ALARM] == 1
        else:
            cur_state = not state
        data = {DATA_ENABLE: 0 if cur_state else 1}
        json_str = await self._post_command(
            "http://" + self.stove_host + STOVE_REMOTE_REFILL_ALARM_URL, data
        )
        if json_str is None:
            _LOGGER.error("Got empty or no response from stove.")
            return False
        return _post_response_ok(json_str)

    async def set_time(self, new_time=None):
        """Set the time and date of the stove."""
        if new_time is None:
            new_time = datetime.now()
        data = {
            "year": new_time.year,
            "month": new_time.month - 1,  # Stove month input is 0 based.
            "day": new_time.day,
            "hours": new_time.hour,
            "minutes": new_time.minute,
            "seconds": new_time.second,
        }
        json_str = await self._post_command(
            "http://" + self.stove_host + STOVE_SET_TIME_URL, data
        )
        if json_str is None:
            _LOGGER.error("Got empty or no response from stove.")
            return False
        return _post_response_ok(json_str)

    async def start(self):
        """Start the ignition phase."""
        result = await self._get_json("http://" + self.stove_host + STOVE_START_URL)
        return result.get(DATA_RESPONSE) == RESPONSE_OK

    async def _identify(self):
        """Get identification and set the properties on the object."""

        async def get_identification():
            """Get stove name, IP and MDNS"""
            stove_id = await self._get_json("http://" + self.stove_host + STOVE_ID_URL)
            if not stove_id:
                _LOGGER.error("Unable to read stove identity informations.")
                return

            if DATA_NAME in stove_id:
                self.name = stove_id[DATA_NAME]
            else:
                _LOGGER.warning("Unable to read stove name.")

            if DATA_IP in stove_id:
                self.stove_ip = stove_id[DATA_IP]
            else:
                _LOGGER.warning("Unable to read stove IP.")

            if DATA_MDNS in stove_id:
                self.stove_mdns = stove_id[DATA_MDNS]
            else:
                _LOGGER.warning("Unable to read stove MDNS.")

        async def get_ssid():
            """Get stove SSID."""
            result = await self._get_json(
                "http://" + self.stove_host + STOVE_ACCESSPOINT_URL
            )
            stove_ssid = result.get(DATA_SSID)
            if stove_ssid is None:
                _LOGGER.warning("Unable to read stove SSID.")
                return
            self.stove_ssid = stove_ssid

        info_read_error = None

        async def get_version_info():
            """Get stove version info."""
            nonlocal info_read_error
            data = {DATA_FILENAME: "info.xml", DATA_MODE: 1}
            json_str = await self._post(
                "http://" + self.stove_host + STOVE_OPEN_FILE_URL, data
            )
            if json_str is None:
                _LOGGER.error("Got empty or no response from stove.")
                return
            success = json.loads(json_str)
            if success[DATA_SUCCESS] == 1:
                read_error = None
                try:
                    xml_str = await self._post(
                        "http://" + self.stove_host + STOVE_READ_OPEN_FILE_URL, data
                    )
                except BaseException as exc:
                    read_error = exc
                    info_read_error = exc
                    raise
                finally:
                    await self._close_info_file(read_error)
                try:
                    xml_root = ET.fromstring(xml_str)
                    self.algo_version = xml_root.find("Name").text
                    self.series = xml_root.find("StoveType").text
                except ET.ParseError:
                    _LOGGER.warning("Invalid XML. Could not get version info.")
                except AttributeError:
                    _LOGGER.warning("Missing key in version info XML.")
            else:
                _LOGGER.warning("Unable to open stove version info file.")

        tasks = []
        group = None
        try:
            for identify in (get_identification, get_ssid, get_version_info):
                coroutine = identify()
                try:
                    task = asyncio.ensure_future(coroutine)
                except BaseException:
                    coroutine.close()
                    raise
                tasks.append(task)
            group = asyncio.gather(*tasks)
            await asyncio.wait((group,))
            group.result()
        except BaseException as cause:
            # A read failure can be waiting for its close when a later
            # factory cancellation arrives. Keep the original failure.
            primary = (
                info_read_error
                if isinstance(cause, asyncio.CancelledError)
                and info_read_error is not None
                else cause
            )

            async def cleanup_tasks(initial_error=primary):
                for task in tasks:
                    if not task.done():
                        task.cancel()
                pending = [*tasks]
                if group is not None:
                    pending.append(group)
                results = await asyncio.gather(*pending, return_exceptions=True)
                for result in results[:len(tasks)]:
                    if (
                        isinstance(result, BaseException)
                        and not isinstance(result, asyncio.CancelledError)
                        and result is not initial_error
                    ):
                        _LOGGER.error(
                            "Additional identify task failure during "
                            "initialization cleanup.",
                            exc_info=(type(result), result, result.__traceback__),
                        )

            await _finish_initialization_cleanup(
                cleanup_tasks, "Unable to finish identify task cleanup."
            )
            if primary is not cause:
                raise primary from primary.__cause__
            raise

    async def _close_info_file(self, read_error):
        """Attempt one bounded close after confirmed open, without claiming success."""
        async def close_file():
            async with asyncio.timeout(_INFO_FILE_CLOSE_TIMEOUT):
                # Borrow the existing pool/cookies; never change another request's
                # retry policy or close the factory-owned connector here.
                async with aiohttp.ClientSession(
                    connector=self._session.connector,
                    connector_owner=False,
                    cookie_jar=self._session.cookie_jar,
                    headers=self._session.headers,
                ) as session:
                    # aiohttp can retry GET internally, including on a fresh
                    # connection. Restrict this switch to this close-only session.
                    session._retry_connection = False
                    async with session.get(
                        "http://" + self.stove_host + "/close_file",
                        allow_redirects=False,
                    ) as response:
                        await response.read()

        cancellation = None
        coroutine = close_file()
        try:
            try:
                close_task = asyncio.ensure_future(coroutine)
            except BaseException:
                coroutine.close()
                raise
            while not close_task.done():
                try:
                    await asyncio.wait((close_task,))
                except asyncio.CancelledError as exc:
                    if cancellation is None:
                        cancellation = exc
            close_task.result()
        except BaseException:
            _LOGGER.error(
                "info.xml close attempt failed; controller close unconfirmed.",
                exc_info=True,
            )
        # Unlike failed-initialization cleanup, this also runs on a successful
        # read: a first caller cancellation here must remain visible afterwards.
        if read_error is None and cancellation is not None:
            raise cancellation

    async def _self_test_result(self):
        """Get self test result."""
        count = 0
        result = None
        while True:
            # Error prone, retry up to 3 times
            result = await self._get_json(
                "http://" + self.stove_host + STOVE_SELFTEST_RESULT_URL
            )
            if result == {}:
                continue
            if not result.get("reponse"):  # NOT A TYPO!!!
                break
            if count >= 3:
                return
            count = count + 1
            await asyncio.sleep(3)
        return result

    async def _self_test_start(self):
        """Request self test start."""
        result = await self._get_json(
            "http://" + self.stove_host + STOVE_SELFTEST_START_URL
        )
        return result.get(DATA_RESPONSE) == RESPONSE_OK

    def _get_maintenance_alarms_text(self, bitmask):
        """Process maintenance alarms bitmask, return a list of strings."""
        num_alarms = len(MAINTENANCE_ALARMS)
        ret = []
        for i in range(num_alarms):
            if 1 << i & bitmask:
                ret.append(MAINTENANCE_ALARMS[i])
        return ret

    def _get_safety_alarms_text(self, bitmask):
        """Process safety alarms bitmask, return a list of strings."""
        num_alarms = len(SAFETY_ALARMS)
        ret = []
        for i in range(num_alarms):
            if 1 << i & bitmask:
                ret.append(SAFETY_ALARMS[i])
        return ret

    async def _get_json(self, url):
        """Get data from url, interpret as json, return result."""
        json_str = await self._get(url)
        if json_str is None:
            _LOGGER.error("Got empty or no response from stove.")
            return {}
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as exc:
            _LOGGER.error("Could not decode received data as json: %s", exc.doc)
            _LOGGER.error("Error was: %s", exc.msg)
            return {}
        return result

    async def _get(self, url):
        """Get data from url, return response."""
        try:
            async with self._session.get(url) as response:
                return await response.text()
        except aiohttp.client_exceptions.ClientConnectorError:
            _LOGGER.error("Could not connect to stove.")

    async def _post_command(self, url, data):
        """Post a command; approved body-read failures leave success unconfirmed."""
        try:
            async with self._session.post(
                url, data=json.dumps(data, separators=(",", ":"))
            ) as response:
                try:
                    return await response.text()
                except (
                    aiohttp.ClientPayloadError,
                    aiohttp.ServerDisconnectedError,
                    TimeoutError,
                ):
                    return None
        except aiohttp.client_exceptions.ClientConnectorError:
            _LOGGER.error("Could not connect to stove.")

    async def _post(self, url, data):
        """Post data to url, return response."""
        try:
            async with self._session.post(
                url, data=json.dumps(data, separators=(",", ":"))
            ) as response:
                return await response.text()
        except aiohttp.client_exceptions.ClientConnectorError:
            _LOGGER.error("Could not connect to stove.")


class _SelfTest:
    """Self test async generator."""

    def __init__(self, stove, delay, processed=True):
        self.stove = stove
        self.delay = delay
        self.processed = processed
        self.test_started = False
        self.test_finished = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        async def get_result():
            """Get intermediate test results."""

            def process_dict(in_dict):
                """Process dict values."""
                if not self.processed:
                    return in_dict
                out_dict = {}
                for k, v in in_dict.items():
                    out_dict[k] = SELF_TEST_VALUES[v]
                return out_dict

            intermediate_raw = await self.stove._self_test_result()
            if intermediate_raw is None:
                return None
            else:
                intermediate = process_dict(intermediate_raw)
                if 2 not in intermediate_raw.values():
                    self.test_finished = True
                return intermediate

        if not self.test_started:
            if await self.stove._self_test_start():
                self.test_started = True
                return await get_result()
            else:
                raise StopAsyncIteration
        if self.test_finished:
            raise StopAsyncIteration

        await asyncio.sleep(self.delay)
        return await get_result()
