"""Stand-alone shield/wait ownership probe; no pystove or network imports."""
import asyncio
import json
import sys


async def scenario(mode, outcome):
    loop = asyncio.get_running_loop()
    contexts = []
    loop.set_exception_handler(lambda loop, context: contexts.append(context))
    started, release, detached = asyncio.Event(), asyncio.Event(), asyncio.Event()
    holder = {}
    async def operation():
        started.set()
        await release.wait()
        if outcome == 'error':
            raise ValueError('owned operation error')
        if outcome == 'cancel':
            raise asyncio.CancelledError('owned operation cancellation')
        return 'ok'
    async def caller():
        child = asyncio.create_task(operation())
        group = asyncio.gather(child)
        holder.update(child=child, group=group)
        try:
            if mode == 'shield':
                holder['outer'] = asyncio.shield(group)
                await holder['outer']
            else:
                await asyncio.wait((group,))
                group.result()
        except asyncio.CancelledError:
            detached.set()
            # This explicitly retrieves every owned outcome in BOTH modes.
            await asyncio.gather(child, group, return_exceptions=True)
            raise
    parent = asyncio.create_task(caller())
    await started.wait()
    parent.cancel('primary cancellation')
    await detached.wait()
    release.set()
    try:
        await parent
    except asyncio.CancelledError as exc:
        assert exc.args == ('primary cancellation',)
    child, group = holder['child'], holder['group']
    assert child.done() and group.done()
    assert group.exception() is None or isinstance(group.exception(), BaseException)
    assert asyncio.all_tasks() == {asyncio.current_task()}
    return {
        'mode': mode, 'outcome': outcome,
        'group_cancelled': group.cancelled(),
        'group_exception': type(group.exception()).__name__,
        'outer_cancelled': holder['outer'].cancelled() if 'outer' in holder else None,
        'messages': [c['message'] for c in contexts],
        'reported_object_is_group': [c.get('future') is group for c in contexts],
    }

async def main():
    print(json.dumps({'python': sys.version.split()[0], 'cases': [
        await scenario(mode, outcome)
        for mode in ('shield', 'wait') for outcome in ('ok', 'error', 'cancel')
    ]}, indent=2))
asyncio.run(main())
