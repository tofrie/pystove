# Python 3.14: owned initialization cleanup without shield diagnostics

Base: `fcb7e8ac46b1cc5d73de7c5879e49073aa21769b`, version `0.3a2.dev0`.
The version remains unchanged; this is neither a release nor a dependency update.
No hwam_stove file is changed and its migration gate is not resumed here.

## Root cause, proved before the runtime edit

The existing acceptance test
`test_repeated_failed_factories_do_not_accumulate_sessions_or_tasks[cancel]`
failed on Python 3.14.6 after all its session/task cleanup assertions succeeded.
Twenty factory cancellations produced twenty loop exception-handler messages:
`CancelledError exception in shielded future`.

The exact installed CPython 3.13.16 and 3.14.6 sources were inspected. Python
3.14.6's `asyncio.shield()` installs `_log_on_exception` on the inner future when
its outer wrapper finishes while the inner operation is still pending. That
callback calls `future.exception()` and explicitly invokes the loop exception
handler whenever the inner future is not cancelled and holds an exception.
It does not check whether another owner already retrieved that exception.
Python 3.13 removes the forwarding callback and does not install this logger.

In `_identify()`, the inner object is `asyncio.gather(*tasks)`. Cancelling an
identify child makes this gathering future finish with a **stored**
`CancelledError`; `group.cancelled()` remains False. Thus the 3.14 callback reports
it even though our cleanup also awaits the children and group with
`return_exceptions=True`. This is an explicit callback report, not a garbage-
collection `exception was never retrieved` report and not evidence by itself
that the session or tasks leaked. No claim that CPython is defective is needed.

There is a second affected boundary: `_finish_initialization_cleanup()` also
shields an owned task. If a caller cancellation detaches that wrapper and the
cleanup later raises a regular exception, 3.14 reports that exception even though
our helper subsequently reads it and logs it. Merely retaining or reading the
cancelled outer shield future cannot undo its already-installed inner callback.

`ci/reproduce_py314_shield.py` proves the difference without importing pystove or
performing I/O. It observes every loop context, cancels the caller, then explicitly
retrieves the child and gathering future outcomes. On 3.13.16 both strategies
produce no messages. On 3.14.6 the shield strategy reports ValueError and
CancelledError outcomes; success remains quiet. The wait strategy produces no
messages in all three cases. The reported object is the inner gathering future,
not the cancelled shield wrapper. Synchronization uses Events, not timed sleeps.

Primary references:

- [CPython 3.14.6 asyncio tasks source](https://github.com/python/cpython/blob/v3.14.6/Lib/asyncio/tasks.py)
- [CPython 3.13.16 asyncio tasks source](https://github.com/python/cpython/blob/v3.13.16/Lib/asyncio/tasks.py)
- [Python cancellation and shielding contract](https://docs.python.org/3.14/library/asyncio-task.html#shielding-from-cancellation)

## Ownership graph

Old normal identification:

```text
caller running Stove.create / _identify
  -> outer shield future (cancelled by caller cancellation)
     -> identify gather (retained by _identify)
        -> three explicitly created identify tasks
```

Old failure cleanup:

```text
caller retaining the original exception
  -> another shield wrapper per interrupted wait
     -> ONE retained cleanup task
        -> cancel and await own identify tasks AND original gather
  -> another retained close_session cleanup task
     -> await the owned session.close()
  -> re-raise original exception
```

The new graph removes shield wrappers at both wait boundaries. `asyncio.wait`
uses a completion waiter which carries only a completion notification, never the
operation exception. Caller cancellation cancels that waiter, not its input
futures. `wait` removes its completion callbacks in `finally`. The input task or
future remains strongly referenced by our existing ownership variables.

| Object | Creator / owner | Cancellation | Completion and exception reader | Lifetime end |
| --- | --- | --- | --- | --- |
| Caller task | Integration/caller | External caller | Its caller awaits original outcome | After original outcome observed |
| Old shield wrapper | `shield` | Propagated from caller | Caller sees CancelledError; 3.14 attaches inner logger | Wrapper completion, independently of owned inner work |
| New completion waiter | `asyncio.wait` | Propagated from caller | `wait` awaits it; it has no operation exception | Callbacks removed on exit |
| Identify gather | `_identify` | Not directly cancelled | Normal `group.result()` or cleanup gather with `return_exceptions=True` | After either result reader and cleanup complete |
| Identify tasks | `_identify` | Only owned cleanup cancels unfinished tasks | Identify gather and explicit cleanup gather; secondary regular failures logged | After all children/finalizers finish |
| Cleanup task | Helper, exactly once per operation | External caller cancellation does not reach it | Helper waits until done, then `cleanup.result()` | After result/error is consumed |
| Session close | Factory's close_session cleanup task | Protected as owned cleanup | Task awaits close; helper consumes task outcome | After close completes or its error is logged |

All references can be released after these ownership boundaries. A task error
never relies on garbage collection to become observed. The caller's primary
exception is retained by the existing exception handler and re-raised unchanged.

## Fix and scope

Only three runtime lines change in `pystove/pystove.py`:

- `await asyncio.shield(cleanup)` becomes `await asyncio.wait((cleanup,))`.
- `await asyncio.shield(group)` becomes `await asyncio.wait((group,))`, followed
  by `group.result()` to preserve immediate propagation of the gather outcome.

The cleanup helper still constructs its task exactly once. Repeated cancellation
re-enters a suspended wait on that same task, never starts a new cleanup coroutine,
and never cancels owned work. There is no busy wait or sleep-based timing rule.
The existing `while not cleanup.done()` exits immediately after completion, and
`cleanup.result()` consumes success or failure. A secondary exception retains the
existing controlled error logging; it cannot replace the primary exception.

Normal identification still starts the same three tasks in the same order.
`gather` still reports the first failure without waiting for unrelated pending
branches; explicit cleanup then drains those branches before session close.
No TaskGroup exception grouping or public exception conversion is introduced.
No private asyncio APIs, callback removal hacks, global exception-handler edits,
warning filters or `uncancel()` calls are added to runtime.

Endpoints, methods, payloads, serialization, headers, timeout/retry behavior,
status parsing, command semantics, API signatures and successful return values
are unchanged. Package/version/CLI files are unchanged. The package validator
reverses exactly the two new wait sites and result retrieval, then verifies the
entire historical H6 source and all prior scope hashes. Historical hashes are
retained. Additional negative tests reject expanded scope or missing result reads.

## Deterministic acceptance matrix

The existing 27 lifecycle tests remain byte-for-byte unchanged, including the
original failing test. Thirty additional lifecycle cases cover:

- one, two and five cancellations with primary cancellation;
- further cancellation during task finalization and during session.close();
- preservation of a regular primary error despite later cancellation;
- cleanup completion queued between cancellations at both boundaries;
- secondary RuntimeError and CancelledError during task/session cleanup;
- each secondary outcome with zero or three additional caller cancellations;
- exact primary identity/message, one close, finished owned tasks, no extra tasks;
- empty loop context recordings and absence of ResourceWarning, including GC.

Loop handlers are installed only in tests to **record and assert every message**;
no message is discarded or filtered. The full suite also treats ResourceWarning
as an error. No controller transport is used.

Before the fix, the combined lifecycle suite had 18 failures and 39 passes on
3.14.6. After the fix, all 57 lifecycle cases pass, without changing any existing
acceptance assertion. Ten additional packaging checks protect the narrow scope.
The six historical H6/M1/M2 xfails remain unchanged and strict; none is added for
Python 3.14. Installed-wheel checks include the new lifecycle matrix.

CI now includes Python 3.14.6 alongside 3.11, 3.12 and 3.13. The full matrix checks
pytest, Ruff, wheel/sdist, archive metadata and RECORD, isolated builds without
aiohttp, and tests imported from the installed wheel outside the checkout.
