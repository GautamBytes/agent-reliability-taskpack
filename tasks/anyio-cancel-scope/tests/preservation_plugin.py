from __future__ import annotations


def pytest_collection_modifyitems(config, items):
    excluded = [item for item in items if "asyncio+uvloop" in item.nodeid]
    if excluded:
        config.hook.pytest_deselected(items=excluded)
        items[:] = [item for item in items if item not in excluded]
