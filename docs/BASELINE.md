# Compatibility baseline and first-phase boundaries

The reference contract and first-phase boundaries below record Phase 1. The
subsequent corrections are described in [H3 follow-up](#h3-follow-up) and
[H4 follow-up](#h4-follow-up).

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

## H3 follow-up

The H3-only branch starts from Phase 1 commit
`5876e2d7c381baf1dc72815a110bc2c0b2c2d8c4` and retains the unpublished development
version `0.3a2.dev0`. H3 is now corrected; all other deferred defects remain.

`Stove.create()` owns the session it constructs; there is no supplied-session
API. On initialization failure or cancellation it closes that exact session,
even if a subclass has replaced `self._session`. Successful initialization keeps
the session open and `destroy()` retains its original behavior.

Identification still schedules identity, SSID and version-file operations in
their original order and uses the same request/parsing code. The three owned
tasks and their original gather are retained. Failure or cancellation cancels
unfinished owned tasks and awaits all of them before session cleanup. Unrelated
tasks and sessions are untouched. An unscheduled coroutine is closed if task
creation fails. Shielded cleanup waits through further caller cancellation and
then re-raises the original initialization exception or `CancelledError`, including
its message. No cleanup timeout or new retry policy is introduced.

Cleanup logs use the existing `pystove.pystove` logger at ERROR with traceback:

| Message | Logged cause |
| --- | --- |
| `Unable to close session after failed initialization.` | Exception from session cleanup, including cancellation originating in `close()` itself |
| `Additional identify task failure during initialization cleanup.` | Additional child exception different from the original cause; normal child cancellation is excluded |
| `Unable to finish identify task cleanup.` | Unexpected failure while scheduling or draining identify cleanup |

The original initialization cause is propagated rather than replaced by these
cleanup errors. Ordinary caller/child cancellation is not logged as a cleanup
failure. Cleanup errors are retrieved so completed tasks/gathers do not emit
unobserved-exception warnings.

The original 0.3a1 hashes remain in `ci/compatibility_baseline.json`. A separate
reviewed H3 hash permits exactly this runtime delta; a Phase 1 byte digest also
protects all code outside `create()`, `_identify()` and the new private cleanup
helper. The nested identify request/parsing functions were reviewed against
Phase 1 and remain unchanged. Contract tests retain the successful request order,
endpoints, methods, payloads, headers, data types and public API.

The two former H3 xfails are ordinary regression tests; all 22 other xfails
remain. Tests cover repeated failures, repeated cancellation during task/session
cleanup, secondary cleanup errors, ownership and real aiohttp sessions/connectors
without requests or sockets. H3 requires no hardware access.

Cleanup assumes the running loop can schedule its work and finalizers eventually
finish. A finalizer or `close()` that never returns delays error/cancellation
propagation; adding a timeout is outside H3. If `close()` itself fails before
closing its resource, successful closure cannot be guaranteed; its error is
logged and the original initialization cause still propagates.

## H4 follow-up

The H4-only branch starts from approved H3 commit
`35cc6bda8c014ca545f90f5b145b716bbcf68593`, retaining version `0.3a2.dev0` and the
published 0.3a1 successful-data contract. Only `get_data()`'s body changes.

Exactly **36 raw fields** are required by the released method; none has a default
or may be omitted. Additional fields are optional and ignored:

| Group | Required raw fields | Existing processing retained |
| --- | --- | --- |
| States | `phase`, `operation_mode`, `night_lowering` | Existing list indexing and state strings, including bool and in-range negative integer indices |
| Stove clock | `year`, `month`, `day`, `hours`, `minutes`, `seconds` | Builtin naive `datetime`, raw month 1–12 and calendar validation; no new coercion |
| Refuel duration | `new_fire_wood_hours`, `new_fire_wood_minutes` | Builtin `timedelta`; ints, floats, bools, negative values and minutes beyond 59 remain processable; estimate is stove datetime plus duration |
| Night interval | `night_begin_hour`, `night_begin_minute`, `night_end_hour`, `night_end_minute` | Builtin naive `time`; unchanged hour/minute ranges and integer semantics |
| Alarms | `maintenance_alarms`, `safety_alarms` | Integer bitmasks, including bools, negative masks and additional high bits; unchanged ordered string lists, duplicate labels and `[]` for no known bits |
| Measurements | `stove_temperature`, `room_temperature`, `oxygen_level` | Exact `int(raw / 100)`, truncating toward zero; no blanket size restriction if conversion succeeds |
| Versions | `version_major`, `version_minor`, `version_build`, `remote_version_major`, `remote_version_minor`, `remote_version_build` | Existing f-string formatting, without new integer/type restrictions |
| Pass-through | `algorithm`, `burn_level`, `message_id`, `refill_alarm`, `remote_refill_alarm`, `time_since_remote_msg`, `updating`, `valve1_position`, `valve2_position`, `valve3_position` | Raw JSON values and types, without new numeric normalization |

Native dictionaries, dictionary subclasses and mutable mapping objects such as
`UserDict` remain processable. Read-only mappings do not meet the legacy sensor
mutation contract. Empty, absent, non-mapping or incomplete status returns `None`.
Unprocessable state indices, datetime/time values, refuel durations/estimates,
alarm masks or scaled measurements also return `None` for the complete fetch.
No partial result or fabricated `UNKNOWN` values are introduced.

Validation checks presence before parsing and catches only `TypeError`,
`ValueError`, `IndexError` and `OverflowError` around builtin data conversions.
Fetching, alarm helpers, version formatting, raw-mapping updates and result
construction are outside those catches. Unexpected internal errors propagate;
`CancelledError`, `SystemExit`, `KeyboardInterrupt` and other `BaseException`
cases are never translated into `None`. No public exception hierarchy is added.

Each failed status validation emits at most one WARNING through the existing
logger. The message names a missing field, expected mapping shape or conversion
field/category plus exception class. It includes no raw value, response body or
traceback. Valid status emits no new validation message. Existing `_get_json()`
logging remains unchanged, including its legacy malformed-JSON body logging;
that broader transport logging issue is outside H4.

All eleven H4 xfail parameter cases now pass as regular regressions. The eleven
other xfails and all H3 tests remain unchanged. The new status suite compares
valid fixtures with a SHA-256-checked literal of the released method: all 25
keys, their order, values, exact types, sensor mutation and status GET remain
identical. Tests deliberately cover successful legacy edge cases so validation
does not silently narrow real firmware compatibility.

The separate H4 artifact approval preserves every original 0.3a1/H3 hash and
pins both the reviewed full source hash and all H3-base bytes outside
`get_data()`. Session lifecycle, transport, constants, commands, endpoints,
request payloads/serialization, headers, timeouts, retries and successful
request order are unchanged. No Home Assistant files or dependencies change.
The integration's existing `data is None` branch handles failed status retrieval.
No hardware access is needed for these synthetic-data checks.


## H6 POST response follow-up

This narrow H6 phase starts from H4 commit
`82c8438ed046261c2e29bf3af01fe6f65fc89bb5`, keeping version `0.3a2.dev0`.
Only the already received response text of `set_burn_level()`,
`set_remote_refill_alarm()`, `set_night_lowering_hours()` and `set_time()` is
interpreted by a shared private `_post_response_ok()` helper. A decoded JSON
object still succeeds exactly when `response == "OK"`. Other or missing response
values retain `False`; no case folding, value trimming or alternate success
values are introduced. Additional object fields remain ignored.

Malformed JSON and non-object JSON now return `False` instead of raising
`JSONDecodeError` or a structure error. Only `JSONDecodeError` is caught, around
`json.loads()` alone. Cancellation, memory errors and unexpected programming
errors propagate. The existing `None` response handling remains unchanged.
No new logging is added, and existing logging is untouched.

**False means no valid success confirmation was received. It does not prove
that the stove did not execute the command. No retry follows from this result.**

The four setters' requests, preceding status reads, signatures and all other
runtime code are unchanged. In particular, `_get()`, `_get_json()`, `_post()`,
HTTP status handling, transport exceptions, timeouts, retry behavior, GET
commands, H3 cleanup and H4 status processing retain their H4 bytes. Dependencies
and `hwam_stove` are unchanged. This does not complete the whole H6 finding.

Exactly two H6 xfail cases become regular regressions: malformed POST JSON and
wrong POST response shape. The remaining nine xfails still characterize H6
HTTP status errors (2), H6 response transport errors (3), M1 live data (3) and
M2 self-test polling (1). They remain strict; XPASS is a verification failure.

`test_post_response_validation.py` covers all four POST setters, exact success
semantics, malformed/non-object replies, exception propagation and no added
requests. Its SHA-256-pinned `h4_commands.json` fixture contains all six command
methods copied from the exact H4 commit; direct comparisons preserve results,
types and complete request sequences, including preliminary reads.

Artifact validation retains the historical H3/H4 approvals. Removing only the
new parser and restoring only four exact return expressions must reproduce the
full H4 source hash. Setter request construction is outside this exception.
The complete current source hash is checked separately. The H6 suite and its
fixture are included in sdists and installed-wheel verification.

Synthetic response tests need no hardware for this parsing-only scope. They do
not establish real firmware HTTP status conventions or actual command execution
after a lost response. H5 timeout tuning, H7 retry assessment, H9 file concurrency,
L2 transport logging and the broader M1/M2 findings remain separate work.


## H6 POST response-read follow-up

This second, independent H6 subscope starts from parser-phase commit
`9865615a2509aa13897f5e2b84e6a89310fa0ee3`; version remains `0.3a2.dev0`.
The four POST setters now use the private `_post_command()` request path. It
retains the exact request construction and legacy connector-error behavior of
`_post()`, but adds a catch only around `await response.text()` inside the
already-entered response context. Exactly `aiohttp.ClientPayloadError`,
`aiohttp.ServerDisconnectedError` and `TimeoutError` are treated as an absent
confirmation. The existing setter path then returns `False` and logs its usual
brief message, without response contents, exception text or a traceback.

The exception class does not determine the stage at which a failure occurred.
The documented three xfails inject their error during body reading. The same
classes raised during serialization, request construction, context entry or
context exit are outside the new catch and still propagate. Boundary tests
exercise these stages separately. No new timeout is created or configured.

Cancellation, memory errors, process-control exceptions and unexpected errors
propagate. Other previously unhandled aiohttp errors still propagate. Existing
`ClientConnectorError` handling is deliberately retained, not broadened.
The JSON parser `_post_response_ok()` is byte-identical to the approved parser
phase; it does not absorb transport exceptions raised from decoding itself.

False means there is no reliable success confirmation, not that the command
was not executed. There is no retry, additional request or assumed local state.
Responses still leave their context on failure. Cleanup/context-exit errors are
not converted into False by the new body-read handler.

The shared `_post()` remains byte-identical for identification and file reads.
GET commands, preliminary status GETs, `_get_json()`, H3 lifecycle, H4 status
validation, live history and self-test are unchanged. Status 500 with an OK
body is still accepted; both HTTP-status xfails intentionally remain xfail.

Exactly three response-read xfails become regressions. Six strict xfails remain:
H6 HTTP status POST/GET (2), M1 live-data failures (3) and M2 self-test polling (1).
The new tests cover all four POST setters, approved and unapproved exceptions,
request/context/read/exit boundaries, response cleanup, no retries, no inferred
state and bounded existing logging. An AST comparison also verifies that the
new request helper differs from `_post()` only in its name, docstring and the
approved inner body-read catch.

The SHA-256-pinned `h6_post_response_commands.json` fixture contains all six
original commands from the exact parser-phase commit. Direct comparisons verify
results, types and complete request sequences against both that commit and H4.
Existing success and malformed/non-object JSON matrices remain in force.

The new artifact approval preserves all historical H3/H4/H6 metadata. Removing
only `_post_command()` and restoring four call targets must reproduce the exact
parser-phase source hash. This freezes the parser, original transport methods,
request arguments, public signatures and all other runtime bytes. The complete
new source hash is checked separately. The suite and reference fixture are
included in sdist validation and installed-wheel verification.

No hardware access is needed for this handling of simulated existing read
errors. Tests do not prove whether a controller executed an unconfirmed command,
validate real response-loss behavior or establish HTTP status conventions.
