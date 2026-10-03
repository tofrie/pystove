# Compatibility baseline and first-phase boundaries

## Reference artifacts

The compatibility reference is the published `pystove==0.3a1` and its matching
Git tag `0.3a1`, commit
`6d2f7844d3fa49a339820c446aa47ba29e60e94a`. The current upstream `master` is
not the runtime baseline: it includes API, type and protocol differences.

Published artifact SHA-256 values:

| Artifact | SHA-256 |
| --- | --- |
| `pystove-0.3a1-py3-none-any.whl` | `0a7432f79e7e428ba04f897cb6a23108c294c6bf52dc6fdeb58108eff3408581` |
| `pystove-0.3a1.tar.gz` | `326691219cf0cb6f1160df0c32e9422bdd119918c88ba8919458ae60f61fc674` |

The integration compatibility reference is `mvn23/hwam_stove` commit
`2176600eece1c644f594a9608186bf395bb2488b`, whose manifest requires
`pystove==0.3a1`. This phase does not modify that repository.

The development version is `0.3a2.dev0`; `0.3a1` remains the compatibility
reference, not the version of newly changed packaging and development files.
The version has one source, `pystove/version.py`. Packaging reads that source
without importing the runtime package. Nothing in this phase is published.

## Imports and exported constants

These imports are part of the integration contract:

```python
from pystove import Stove
from pystove import pystove
```

`Stove` is the same class at both import paths. Root imports explicitly
re-export the constants indicated in the table below, the six state/alarm
tables, `Stove`, and `__version__`. The `pystove` module is also available from
the package. Constants marked module-only are available as
`pystove.pystove.<name>`; this phase does not add new root exports. In particular,
`UNKNOWN` is module-only, which matters to the integration's module import.

| Constant | Exact value | Root re-export |
| --- | --- | --- |
| `DATA_ALGORITHM` | `"algorithm"` | Yes |
| `DATA_BEGIN_HOUR` | `"begin_hour"` | Yes |
| `DATA_BEGIN_MINUTE` | `"begin_minute"` | Yes |
| `DATA_ENABLE` | `"enable"` | Module-only |
| `DATA_END_HOUR` | `"end_hour"` | Yes |
| `DATA_END_MINUTE` | `"end_minute"` | Yes |
| `DATA_BURN_LEVEL` | `"burn_level"` | Yes |
| `DATA_DATE_TIME` | `"date_time"` | Yes |
| `DATA_FILENAME` | `"file_name"` | Module-only |
| `DATA_FIRMWARE_VERSION` | `"firmware_version"` | Yes |
| `DATA_FIRMWARE_VERSION_BUILD` | `"version_build"` | Yes |
| `DATA_FIRMWARE_VERSION_MAJOR` | `"version_major"` | Yes |
| `DATA_FIRMWARE_VERSION_MINOR` | `"version_minor"` | Yes |
| `DATA_IP` | `"ip"` | Module-only |
| `DATA_LEVEL` | `"level"` | Module-only |
| `DATA_MAINTENANCE_ALARMS` | `"maintenance_alarms"` | Yes |
| `DATA_MESSAGE_ID` | `"message_id"` | Yes |
| `DATA_MDNS` | `"mdns"` | Module-only |
| `DATA_MODE` | `"mode"` | Module-only |
| `DATA_NAME` | `"name"` | Module-only |
| `DATA_NEW_FIREWOOD_ESTIMATE` | `"new_fire_wood_estimate"` | Yes |
| `DATA_NEW_FIREWOOD_HOURS` | `"new_fire_wood_hours"` | Yes |
| `DATA_NEW_FIREWOOD_MINUTES` | `"new_fire_wood_minutes"` | Yes |
| `DATA_NIGHT_BEGIN_HOUR` | `"night_begin_hour"` | Yes |
| `DATA_NIGHT_BEGIN_MINUTE` | `"night_begin_minute"` | Yes |
| `DATA_NIGHT_BEGIN_TIME` | `"night_begin_time"` | Yes |
| `DATA_NIGHT_END_HOUR` | `"night_end_hour"` | Yes |
| `DATA_NIGHT_END_MINUTE` | `"night_end_minute"` | Yes |
| `DATA_NIGHT_END_TIME` | `"night_end_time"` | Yes |
| `DATA_NIGHT_LOWERING` | `"night_lowering"` | Yes |
| `DATA_OPERATION_MODE` | `"operation_mode"` | Yes |
| `DATA_OXYGEN_LEVEL` | `"oxygen_level"` | Yes |
| `DATA_PHASE` | `"phase"` | Yes |
| `DATA_REFILL_ALARM` | `"refill_alarm"` | Yes |
| `DATA_REMOTE_REFILL_ALARM` | `"remote_refill_alarm"` | Yes |
| `DATA_REMOTE_VERSION` | `"remote_version"` | Yes |
| `DATA_REMOTE_VERSION_BUILD` | `"remote_version_build"` | Yes |
| `DATA_REMOTE_VERSION_MAJOR` | `"remote_version_major"` | Yes |
| `DATA_REMOTE_VERSION_MINOR` | `"remote_version_minor"` | Yes |
| `DATA_RESPONSE` | `"response"` | Module-only |
| `DATA_ROOM_TEMPERATURE` | `"room_temperature"` | Yes |
| `DATA_SAFETY_ALARMS` | `"safety_alarms"` | Yes |
| `DATA_SSID` | `"ssid"` | Module-only |
| `DATA_STOVE_TEMPERATURE` | `"stove_temperature"` | Yes |
| `DATA_SUCCESS` | `"success"` | Module-only |
| `DATA_TEST_CONFIGURATION` | `"configuration"` | Yes |
| `DATA_TEST_O2_SENSOR` | `"o2_sensor"` | Yes |
| `DATA_TEST_TEMP_SENSOR` | `"t10_sensor"` | Yes |
| `DATA_TEST_VALVE1` | `"valve_primary"` | Yes |
| `DATA_TEST_VALVE2` | `"valve_secondary"` | Yes |
| `DATA_TEST_VALVE3` | `"valve_tertiary"` | Yes |
| `DATA_TIME_SINCE_REMOTE_MSG` | `"time_since_remote_msg"` | Yes |
| `DATA_TIME_TO_NEW_FIREWOOD` | `"time_to_new_fire_wood"` | Yes |
| `DATA_UPDATING` | `"updating"` | Yes |
| `DATA_VALVE1_POSITION` | `"valve1_position"` | Yes |
| `DATA_VALVE2_POSITION` | `"valve2_position"` | Yes |
| `DATA_VALVE3_POSITION` | `"valve3_position"` | Yes |
| `DATA_YEAR` | `"year"` | Yes |
| `DATA_MONTH` | `"month"` | Yes |
| `DATA_DAY` | `"day"` | Yes |
| `DATA_HOURS` | `"hours"` | Yes |
| `DATA_MINUTES` | `"minutes"` | Yes |
| `DATA_SECONDS` | `"seconds"` | Yes |
| `HTTP_HEADERS` | `{"Accept": "application/json"}` | Module-only |
| `RESPONSE_OK` | `"OK"` | Module-only |
| `STOVE_ACCESSPOINT_URL` | `"/esp/get_current_accesspoint"` | Module-only |
| `STOVE_BURN_LEVEL_URL` | `"/set_burn_level"` | Module-only |
| `STOVE_DATA_URL` | `"/get_stove_data"` | Module-only |
| `STOVE_ID_URL` | `"/esp/get_identification"` | Module-only |
| `STOVE_LIVE_DATA_URL` | `"/get_live_data"` | Module-only |
| `STOVE_NIGHT_LOWERING_OFF_URL` | `"/set_night_lowering_off"` | Module-only |
| `STOVE_NIGHT_LOWERING_ON_URL` | `"/set_night_lowering_on"` | Module-only |
| `STOVE_NIGHT_TIME_URL` | `"/set_night_time"` | Module-only |
| `STOVE_OPEN_FILE_URL` | `"/open_file"` | Module-only |
| `STOVE_READ_OPEN_FILE_URL` | `"/read_open_file"` | Module-only |
| `STOVE_REMOTE_REFILL_ALARM_URL` | `"/set_remote_refill_alarm"` | Module-only |
| `STOVE_SET_TIME_URL` | `"/set_time"` | Module-only |
| `STOVE_SELFTEST_RESULT_URL` | `"/get_selftest_result"` | Module-only |
| `STOVE_SELFTEST_START_URL` | `"/start_selftest"` | Module-only |
| `STOVE_START_URL` | `"/start"` | Module-only |
| `UNKNOWN` | `"Unknown"` | Module-only |

All state tables are ordinary mutable lists, not enums or flags. Their order,
capitalization and duplicate labels are significant:

```python
PHASE = ["Ignition", "Burn", "Burn", "Burn", "Glow", "Standby"]
NIGHT_LOWERING_STATES = ["Disabled", "Init", "Day", "Night", "Manual Night"]
OPERATION_MODES = [
    "Init", "Self Test", "Normal", "Temperature Fault", "O2 Fault",
    "Calibration", "Safety", "Manual", "MotorTest", "Slow Combustion",
    "Low Voltage",
]
MAINTENANCE_ALARMS = [
    "Stove Backup Battery Low", "O2 Sensor Fault", "O2 Sensor Offset",
    "Stove Temperature Sensor Fault", "Room Temperature Sensor Fault",
    "Communication Fault", "Room Temperature Sensor Battery Low",
]
SAFETY_ALARMS = [
    "Valve Fault", "Valve Fault", "Valve Fault", "Bad Configuration",
    "Valve Disconnected", "Valve Disconnected", "Valve Disconnected",
    "Valve Calibration Error", "Valve Calibration Error",
    "Valve Calibration Error", "Chimney Overheat", "Door Open Too Long",
    "Manual Safety Alarm", "Stove Sensor Fault",
]
SELF_TEST_VALUES = [
    "Failed", "Passed", "Running", "Not Completed", "Not Started",
]
```

Alarm bit `i` selects list entry `i`. Multiple bits can therefore produce
duplicate strings. A zero bitmask produces `[]`; it is not `None`, an enum,
a flag object or a set. Unknown high bits are not reported by the legacy
conversion.

## Public class API

No public method has type annotations in the reference. The following types
describe existing successful results; they do not claim new validation or a
uniform exception contract.

| Public signature | Successful return / legacy behavior |
| --- | --- |
| `await Stove.create(stove_host, loop=None, skip_ident=False)` | `Stove`; classmethod, establishes an `aiohttp.ClientSession`, identifies by default |
| `await stove.destroy()` | `None`; awaits session close |
| `await stove.get_data()` | Processed dictionary described below; `None` if `get_raw_data()` returns `None` |
| `await stove.get_raw_data()` | Decoded JSON, normally a dictionary; `_get_json()` returns `{}` on a connection failure or invalid JSON |
| `await stove.get_live_data()` | Intended dictionary of two float lists; `None` for a response whose encoded length is not 120; known length/index defect remains |
| `stove.self_test(delay=3, processed=True)` | Async iterator (`_SelfTest`); yields dictionaries of state strings when processed, original values otherwise; ends with `StopAsyncIteration` |
| `await stove.set_burn_level(burn_level)` | `bool`, checks `response == "OK"`; missing text returns `False` |
| `await stove.set_night_lowering(state=None)` | `bool`, checks `response == "OK"`; `None` requests a toggle |
| `await stove.set_night_lowering_hours(start=None, end=None)` | `bool`; omitted boundary is taken from `get_data()`; supplied objects are read via `.hour` and `.minute` |
| `await stove.set_remote_refill_alarm(state=None)` | `bool`, checks `response == "OK"`; `None` requests a toggle |
| `await stove.set_time(new_time=None)` | `bool`; defaults to `datetime.now()` |
| `await stove.start()` | `bool`, checks `response == "OK"` |

The factory stores `stove_host` unchanged and sets `_loop` to the supplied
loop or `asyncio.get_event_loop()`. `algo_version`, `name`, `series`,
`stove_ip`, `stove_mdns`, and `stove_ssid` begin as the string `"Unknown"`.
Successful identification replaces them from the response. Skipping
identification preserves these defaults. There is no new context manager,
reconnect task or external-session API in this phase.

## `get_data()` data shape

The successful result contains exactly **25 keys**, listed below. This count
comes from the released implementation's `processed_data` literal. Raw date,
version-component and night-boundary fields are not additional result keys.

| Key / exported constant | Existing result shape |
| --- | --- |
| `algorithm` / `DATA_ALGORITHM` | Raw JSON value, unchanged |
| `burn_level` / `DATA_BURN_LEVEL` | Raw JSON value, normally integer |
| `maintenance_alarms` / `DATA_MAINTENANCE_ALARMS` | `list[str]`, including `[]` for zero |
| `message_id` / `DATA_MESSAGE_ID` | Raw JSON value, normally integer |
| `new_fire_wood_estimate` / `DATA_NEW_FIREWOOD_ESTIMATE` | Naive `datetime`: stove datetime plus refuel duration |
| `night_begin_time` / `DATA_NIGHT_BEGIN_TIME` | Naive `datetime.time` |
| `night_end_time` / `DATA_NIGHT_END_TIME` | Naive `datetime.time` |
| `night_lowering` / `DATA_NIGHT_LOWERING` | String selected from `NIGHT_LOWERING_STATES` |
| `operation_mode` / `DATA_OPERATION_MODE` | String selected from `OPERATION_MODES` |
| `oxygen_level` / `DATA_OXYGEN_LEVEL` | `int(raw / 100)` |
| `phase` / `DATA_PHASE` | String selected from `PHASE` |
| `refill_alarm` / `DATA_REFILL_ALARM` | Raw JSON value, normally integer `0`/`1`; not coerced to `bool` |
| `remote_refill_alarm` / `DATA_REMOTE_REFILL_ALARM` | Raw JSON value, normally integer `0`/`1`; not coerced to `bool` |
| `remote_version` / `DATA_REMOTE_VERSION` | String `"major.minor.build"` from raw remote version components |
| `room_temperature` / `DATA_ROOM_TEMPERATURE` | `int(raw / 100)` |
| `safety_alarms` / `DATA_SAFETY_ALARMS` | `list[str]`, potentially duplicate labels |
| `stove_temperature` / `DATA_STOVE_TEMPERATURE` | `int(raw / 100)` |
| `time_since_remote_msg` / `DATA_TIME_SINCE_REMOTE_MSG` | Raw JSON value, unchanged |
| `date_time` / `DATA_DATE_TIME` | Naive `datetime` assembled directly from raw fields |
| `time_to_new_fire_wood` / `DATA_TIME_TO_NEW_FIREWOOD` | `timedelta(hours=raw_hours, minutes=raw_minutes)` |
| `updating` / `DATA_UPDATING` | Raw JSON value, unchanged |
| `valve1_position` / `DATA_VALVE1_POSITION` | Raw JSON value, unchanged |
| `valve2_position` / `DATA_VALVE2_POSITION` | Raw JSON value, unchanged |
| `valve3_position` / `DATA_VALVE3_POSITION` | Raw JSON value, unchanged |
| `firmware_version` / `DATA_FIRMWARE_VERSION` | String `"major.minor.build"` from raw firmware version components |

The three scaled fields are **integers**, even for fractional centiunit
inputs. `int(raw / 100)` truncates towards zero, including negative values.
Other numeric fields are passed through: the parser does not force every
JSON number to an integer. The tests protect these returned values and types
rather than substituting float division or extra normalization. The current
implementation also mutates the supplied raw dictionary's three scaled
fields. That mutation is an incidental implementation detail, not a required
public API guarantee for a later, explicitly approved parser correction; it
is nevertheless unchanged in this phase.

For status parsing, raw `month` is passed directly to `datetime` and therefore
must be 1–12. The datetime and night time objects have no attached timezone.
No modulo operation permits `24:00` in this baseline. `set_time()` has the
separate, existing **zero-based outgoing month** convention described below.
An aware input datetime's fields are used as supplied, without timezone
conversion. These asymmetric conventions are retained rather than inferred
from an imagined new protocol.

## HTTP request contract

The URL prefix is exactly `"http://" + stove.stove_host`. Every endpoint below
is appended directly. The session is created with
`headers={"Accept": "application/json"}`. There is no new explicit timeout,
retry, status-code policy or redirect policy in this phase.

All POSTs use this exact application-level representation:

```python
self._session.post(url, data=json.dumps(data, separators=(",", ":")))
```

This is a compact JSON **string passed through `data=`**, not `json=`.
Existing `json.dumps()` defaults, including `ensure_ascii=True`, are retained.
The implementation does not explicitly set a JSON `Content-Type`; an
`aiohttp`-generated header is not an additional library protocol guarantee.
Tests inspect the exact method, URL, arguments and serialized string. They do
not claim to record bytes from a physical controller.

| Operation | HTTP method and endpoint | Application payload / parameters |
| --- | --- | --- |
| Raw status (also used by `get_data()`) | GET `/get_stove_data` | No body or additional request arguments |
| Live history | GET `/get_live_data` | No body or additional request arguments |
| Burn level | POST `/set_burn_level` | `{"level":<burn_level>}` |
| Night lowering on | GET `/set_night_lowering_on` | No body; explicit truthy state, or toggle from raw state `<= 0` |
| Night lowering off | GET `/set_night_lowering_off` | No body; explicit falsey state, or toggle from raw state `> 0` |
| Night interval | POST `/set_night_time` | Ordered fields `{"begin_hour":<start.hour>,"begin_minute":<start.minute>,"end_hour":<end.hour>,"end_minute":<end.minute>}` |
| Remote refill alarm | POST `/set_remote_refill_alarm` | `{"enable":1}` to enable, `{"enable":0}` to disable |
| Clock | POST `/set_time` | Ordered fields `{"year":<year>,"month":<month-1>,"day":<day>,"hours":<hour>,"minutes":<minute>,"seconds":<second>}` |
| Start ignition | GET `/start` | No body or additional request arguments |
| Stove identification | GET `/esp/get_identification` | No body; reads `name`, `ip`, `mdns` |
| Access point | GET `/esp/get_current_accesspoint` | No body; reads `ssid` |
| Open version file | POST `/open_file` | Exact string `{"file_name":"info.xml","mode":1}` |
| Read opened version file | POST `/read_open_file` | The **same** exact string `{"file_name":"info.xml","mode":1}` |
| Start self-test | GET `/start_selftest` | No body; checks `response == "OK"` |
| Self-test result | GET `/get_selftest_result` | No body; legacy result loop uses the literal key `"reponse"` |

`set_remote_refill_alarm(None)` first GETs raw status and considers exactly
`remote_refill_alarm == 1` enabled. `set_night_lowering(None)` first GETs raw
status and considers `night_lowering > 0` enabled. An explicit state avoids
that preliminary read. If either night-time boundary is omitted, the setter
reads processed status and fills the missing value before its POST.

Identification starts the identity, SSID and version-file flows using
`asyncio.gather()`; ordering between those flows is not guaranteed. Within the
version-file flow, opening precedes reading. The baseline does **not** send a
close-file request. There are no public write/delete-file methods in this
release. New upstream file operations are not imported into this phase.

The getters and commands retain all legacy failure behavior, including
exceptions from malformed successful responses. Command success is the exact
string comparison with `"OK"`; it is not a new HTTP-status-based definition.

## Home Assistant usage protected by this baseline

At the reference commit, the integration uses `Stove.create()`, `destroy()`,
`get_data()`, the six public setters/start command documented above, the
`DATA_*` names, `PHASE`, `NIGHT_LOWERING_STATES`, `OPERATION_MODES`, both alarm
tables and module-level `UNKNOWN`. It expects phase, operation mode and night
lowering as strings, and alarms as lists of strings. The empty list means no
alarm. It uses the naive `datetime`/`time` results with its own timezone
handling. The status coordinator treats `None` as an unsuccessful update.

Inspection of the reference source identifies these exact module constant
names in use:

```text
DATA_ALGORITHM                 DATA_BURN_LEVEL
DATA_DATE_TIME                 DATA_FIRMWARE_VERSION
DATA_MAINTENANCE_ALARMS         DATA_MESSAGE_ID
DATA_NEW_FIREWOOD_ESTIMATE      DATA_NIGHT_BEGIN_TIME
DATA_NIGHT_END_TIME             DATA_NIGHT_LOWERING
DATA_OPERATION_MODE            DATA_OXYGEN_LEVEL
DATA_PHASE                     DATA_REFILL_ALARM
DATA_REMOTE_REFILL_ALARM        DATA_REMOTE_VERSION
DATA_ROOM_TEMPERATURE           DATA_SAFETY_ALARMS
DATA_STOVE_TEMPERATURE          DATA_TIME_SINCE_REMOTE_MSG
DATA_TIME_TO_NEW_FIREWOOD       DATA_VALVE1_POSITION
DATA_VALVE2_POSITION            DATA_VALVE3_POSITION
MAINTENANCE_ALARMS              NIGHT_LOWERING_STATES
OPERATION_MODES                 PHASE
SAFETY_ALARMS                   UNKNOWN
```

The library contract covers the additional exported constants too. HA does
not currently reference `DATA_UPDATING`, but that key remains in the exact
25-key result shape.

The integration does not use live history, self-test, or the file
write/delete methods from upstream `master`. Preserving their released code
here does not claim those legacy paths are correct.

## Tests, known failures and verification limits

The tests use synthetic status/identification data and simulated session I/O;
they never connect to a stove. Fixtures are characterization inputs, not
golden captures of every firmware's wire protocol. Required compatibility
behavior is tested as ordinary passing assertions. Desired corrections to
known defects are separate strict `xfail` tests with audit references; an
unexpected pass must fail the suite so a runtime change cannot slip through.

Relevant deferred audit findings include:

| Audit reference | Legacy defect or deferred question |
| --- | --- |
| H3 | Factory exception/cancellation can leave the created session open |
| H4 | Missing/invalid status responses reach unchecked parsing |
| H5 | No explicit through-going application timeout policy |
| H6 | Inconsistent handling of command/transport/JSON failures |
| H7 | Dependency-level retries and ambiguous command delivery need later assessment |
| M1 | Live-history length check is incompatible with later array indexing |
| M2 | Empty self-test results skip the retry counter and delay |
| M8 | Toggle and read-modify-write operations are not serialized |
| M9 | Setter validation is absent |
| M10 | Time conventions require hardware evidence before normalization |
| M11 | Identification is not robust to every incomplete response |

Some audit findings described functions introduced only on `master`; those
functions are absent from the released baseline and are not added merely to
create tests. None of these defects is repaired in this phase. In particular,
no runtime cleanup, parsing, timeout, retry, HTTP method, endpoint, payload,
header or command-semantic change is authorized here.

The only runtime dependency remains the unbounded `aiohttp` requirement.
There is no new `defusedxml` dependency or runtime version pin. Development
checks use the separately pinned `requirements-dev.txt`. The dependency
versions selected for tests describe that test environment, not a new
production dependency policy.

Initial CI covers Python 3.11, 3.12 and 3.13. This is conservative coverage,
not a new `Requires-Python` minimum or a statement that older interpreters
cannot run the release. Python 3.11 aligns with the existing tooling target;
3.12 with the existing development-container target; 3.13 covers the available
HA-relevant interpreter. Broader support claims require a later tested matrix.

The development workflow checks pytest, Ruff in check mode only, package
builds, wheel/sdist metadata and contents, isolated metadata/build operation,
and imports/contracts against the built wheel. The CI and package validator
do not publish artifacts, require secrets, or deploy to PyPI. Tooling and
verification details are in `requirements-dev.txt`, `.github/workflows/baseline.yml`
and `ci/validate_package.py`.

No hardware test is needed to validate this packaging/test-only scope.
Hardware validation remains mandatory before later changes to communication,
timing, parsing conventions or a real integration upgrade are released.
