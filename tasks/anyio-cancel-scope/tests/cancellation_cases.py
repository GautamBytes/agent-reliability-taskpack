from __future__ import annotations

import sys
from contextlib import ExitStack

import anyio
from anyio.lowlevel import checkpoint


async def host_shield(depth: int = 0) -> None:
    ready = anyio.Event()
    cancelled = anyio.Event()
    host_finished = False

    async def child() -> None:
        ready.set()
        try:
            await anyio.sleep_forever()
        except anyio.get_cancelled_exc_class():
            cancelled.set()
            raise

    with anyio.CancelScope() as parent:
        with ExitStack() as scopes:
            for _ in range(depth):
                scopes.enter_context(anyio.CancelScope())
            async with anyio.create_task_group() as group:
                group.start_soon(child)
                await ready.wait()
                with anyio.CancelScope(shield=True):
                    parent.cancel()
                    await cancelled.wait()
                    await checkpoint()
                    host_finished = True
    assert cancelled.is_set(), "the sibling did not receive cancellation"
    assert host_finished, "the host lost its shield"


async def host_shield_nested() -> None:
    await host_shield(3)


async def independent_sibling_shield() -> None:
    ready = anyio.Event()
    watcher_ready = anyio.Event()
    release = anyio.Event()
    watcher_cancelled = anyio.Event()
    protected_finished = anyio.Event()
    protected_cancelled = anyio.Event()

    async def protected() -> None:
        try:
            with anyio.CancelScope(shield=True):
                ready.set()
                await release.wait()
                await checkpoint()
                protected_finished.set()
            await checkpoint()
        except anyio.get_cancelled_exc_class():
            protected_cancelled.set()
            raise

    async def watcher() -> None:
        watcher_ready.set()
        try:
            await anyio.sleep_forever()
        except anyio.get_cancelled_exc_class():
            watcher_cancelled.set()
            raise

    with anyio.CancelScope() as parent:
        async with anyio.create_task_group() as group:
            group.start_soon(protected)
            group.start_soon(watcher)
            await ready.wait()
            await watcher_ready.wait()
            with anyio.CancelScope(shield=True):
                parent.cancel()
                await watcher_cancelled.wait()
                assert not protected_cancelled.is_set()
                release.set()
                await protected_finished.wait()
                await protected_cancelled.wait()
    assert protected_finished.is_set()
    assert protected_cancelled.is_set()


async def repeated_sibling_cancellation() -> None:
    ready = anyio.Event()
    cancelled_twice = anyio.Event()
    count = 0

    async def child() -> None:
        nonlocal count
        ready.set()
        for _ in range(2):
            try:
                await anyio.sleep_forever()
            except anyio.get_cancelled_exc_class():
                count += 1
        cancelled_twice.set()

    with anyio.CancelScope() as parent:
        async with anyio.create_task_group() as group:
            group.start_soon(child)
            await ready.wait()
            with anyio.CancelScope(shield=True):
                parent.cancel()
                await cancelled_twice.wait()
    assert count == 2, "level cancellation must retry after a child catches it"


async def nested_groups() -> None:
    ready = anyio.Event()
    cancelled = anyio.Event()
    host_ready = anyio.Event()

    async def leaf() -> None:
        ready.set()
        try:
            await anyio.sleep_forever()
        except anyio.get_cancelled_exc_class():
            cancelled.set()
            raise

    async def middle() -> None:
        async with anyio.create_task_group() as inner:
            inner.start_soon(leaf)
            await ready.wait()
            with anyio.CancelScope(shield=True):
                host_ready.set()
                await cancelled.wait()
                await checkpoint()

    async with anyio.create_task_group() as outer:
        outer.start_soon(middle)
        await host_ready.wait()
        outer.cancel_scope.cancel()
    assert cancelled.is_set()


async def restart_after_inner_shield() -> None:
    reached_checkpoint = False
    with anyio.CancelScope() as outer:
        with anyio.CancelScope():
            with anyio.CancelScope(shield=True):
                outer.cancel()
                await checkpoint()
            await checkpoint()
            reached_checkpoint = True
    assert outer.cancelled_caught
    assert not reached_checkpoint, "pending cancellation was lost across an inner shield"


async def restart_after_shield_toggle() -> None:
    reached_checkpoint = False
    with anyio.CancelScope() as outer:
        with anyio.CancelScope():
            with anyio.CancelScope(shield=True) as shield:
                outer.cancel()
                await checkpoint()
                shield.shield = False
                await checkpoint()
                reached_checkpoint = True
    assert outer.cancelled_caught
    assert not reached_checkpoint, "removing a shield must expose pending cancellation"


async def explicitly_cancelled_shield() -> None:
    reached_checkpoint = False
    with anyio.CancelScope(shield=True) as scope:
        scope.cancel()
        await checkpoint()
        reached_checkpoint = True
    assert scope.cancel_called and scope.cancelled_caught
    assert not reached_checkpoint, "a shield must not block its own cancellation"


async def shielded_child_joins_before_exit() -> None:
    ready = anyio.Event()
    release = anyio.Event()
    finished = anyio.Event()

    async def child() -> None:
        with anyio.CancelScope(shield=True):
            ready.set()
            await release.wait()
            await checkpoint()
            finished.set()

    async with anyio.create_task_group() as group:
        group.start_soon(child)
        await ready.wait()
        release.set()
    assert finished.is_set(), "task group exited before its shielded child finished"


async def child_error_propagates() -> None:
    ready = anyio.Event()
    release = anyio.Event()

    async def child() -> None:
        ready.set()
        await release.wait()
        raise ValueError("child failure")

    try:
        async with anyio.create_task_group() as group:
            group.start_soon(child)
            await ready.wait()
            release.set()
    except ExceptionGroup as exc:
        assert len(exc.exceptions) == 1
        assert isinstance(exc.exceptions[0], ValueError)
        assert str(exc.exceptions[0]) == "child failure"
    else:
        raise AssertionError("task group swallowed its child error")


CASES = {
    "host_shield": host_shield,
    "host_shield_nested": host_shield_nested,
    "independent_sibling_shield": independent_sibling_shield,
    "repeated_sibling_cancellation": repeated_sibling_cancellation,
    "nested_groups": nested_groups,
    "restart_after_inner_shield": restart_after_inner_shield,
    "restart_after_shield_toggle": restart_after_shield_toggle,
    "explicitly_cancelled_shield": explicitly_cancelled_shield,
    "shielded_child_joins_before_exit": shielded_child_joins_before_exit,
    "child_error_propagates": child_error_propagates,
}


if __name__ == "__main__":
    anyio.run(CASES[sys.argv[1]], backend=sys.argv[2])
    print(f"completed {sys.argv[1]} on {sys.argv[2]}")
