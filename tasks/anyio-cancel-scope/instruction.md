Fix cancellation propagation on AnyIO's asyncio backend.

A task-group host can enter `CancelScope(shield=True)` while a sibling task waits for cancellation. Cancelling an enclosing scope then leaves the sibling waiting forever. The same program completes on the Trio backend.

This reproduces the problem without relying on a timed sleep.

```python
import anyio

async def main():
    ready = anyio.Event()
    cancelled = anyio.Event()

    async def child():
        ready.set()
        try:
            await anyio.sleep_forever()
        except anyio.get_cancelled_exc_class():
            cancelled.set()
            raise

    with anyio.CancelScope() as parent:
        async with anyio.create_task_group() as group:
            group.start_soon(child)
            await ready.wait()
            with anyio.CancelScope(shield=True):
                parent.cancel()
                await cancelled.wait()

anyio.run(main, backend="asyncio")
```

Make cancellation reach unshielded sibling tasks even when their host is shielded. Keep each task's own shield effective. Preserve cancellation through nested scopes and task groups, including repeated cancellation checkpoints. Pending cancellation must take effect when a shield exits or is disabled, even when the cancelled ancestor is several scopes away.

Keep task-group startup, child completion, exception propagation, timeout handling, and native cancellation behavior intact. Preserve the public API and Trio behavior.

The repository is at `/app/repo`. Python 3.12 and the dependencies needed by the original task-group suite are installed. Run the original suite with `PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p anyio.pytest_plugin tests/test_taskgroups.py -k 'not uvloop'`. The uvloop extra is outside this environment.

The preserved upstream suite has four expected nonpassing cases on Python 3.12. Two generator-coroutine tests skip because Python 3.11 removed that support. Both backends xfail `test_fail_after_scope_camcelled_before_timeout` because upstream cannot distinguish an explicit cancellation after its deadline. These outcomes are accepted. Do not repair those unrelated cases.
