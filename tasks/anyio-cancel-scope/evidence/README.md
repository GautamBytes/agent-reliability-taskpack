# Reproduce the cancellation checks

The task contains the complete source from AnyIO commit `3ea17f9f43a7b7078fcb597246dfbc1889a530cc`. Its 92 tracked files match upstream byte for byte. `baseline-manifest.json` records every file hash. The source contains no Git history.

The reference changes only `src/anyio/_backends/_asyncio.py`. The original task-group file remains unchanged. `results.json` records the local macOS and offline Linux Docker results for the baseline, reference, and three incomplete fixes.

Run the groups with Python 3.12.12 and `environment/requirements.txt` installed.

```sh
python tests/run_tests.py --repo environment/repo --group all --output-dir /tmp/anyio-baseline
cp -R environment/repo /tmp/anyio-reference
sh solution/solve.sh /tmp/anyio-reference
python tests/run_tests.py --repo /tmp/anyio-reference --group all --output-dir /tmp/anyio-reference-proof
```

The baseline has 145 passing public cases and 15 passing private cases. Five private asyncio journeys fail after a five-second bound because cancellation never reaches an awaited event. The reference has 145 passing public cases and 20 passing private cases. Each private case runs on asyncio and Trio in its own process. Events establish readiness and release. A process timeout bounds hangs but does not establish ordering.

The public group deselects 66 uvloop parametrizations. It retains the original upstream skips for generator-based coroutines removed by Python 3.11 and the two upstream expected failures for ambiguous timeout cancellation. `provenance.json` records the exact four nodeids and reasons. JUnit represents both skips and expected failures as skipped entries.

The real rejected immediate-parent fix passes the public group but fails three private cases. The two constructed fixes also fail behavior checks. No control is described as a valid fix.

Build the verification image from the task directory.

```sh
docker build -t anyio-cancel-scope-proof:20261030 environment
```

`docker-runs.json` records the exact offline Docker commands used for all five variants. Each run mounts the selected source tree read-only and writes fresh XML and logs to its own evidence directory. `docker-solve` separately applies `solve.sh` twice inside a fresh container, then checks the resulting source.

All pinned Python dependencies pass `pip check` on macOS arm64 and Linux arm64. Linux arm64 requires `gcc` and `libc6-dev` to build the pinned psutil release. The Dockerfile includes those packages.
