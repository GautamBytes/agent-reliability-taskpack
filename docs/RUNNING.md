# Run or inspect a task

You can review the [saved proof](../REVIEW.md) without installing anything. These steps are for reproducing a result or making a new attempt.

## Check saved evidence without Docker

Use Git and Python 3.11 or newer.

```sh
git clone https://github.com/GautamBytes/agent-reliability-taskpack.git
cd agent-reliability-taskpack
python3 tools/report.py
```

Expect `"all_gates_passed": true`. The program compares recorded controls, submitted patches, source hashes, verifier revisions and replay results. It does not execute the task tests or call a model.

## Prepare to execute a task

Install and start Docker. Install the recorded Harbor version using an isolated tool environment:

```sh
uv tool install 'harbor==0.25.0'
docker info
harbor --version
```

`uv` must already be installed. Harbor should report version 0.25.0. The checked-in runtime uses Python 3.12.12, Node 24.11.1, Codex 0.166.0 and pnpm 11.1.1. Source and direct dependencies are pinned. Image builds need access to package registries; the verifier itself runs offline.

Run native task lint:

```sh
harbor lint tasks/anyio-cancel-scope tasks/better-auth-indexes tasks/werkzeug-multipart --json
```

The recorded result is an empty findings array, `[]`.

## Run a reference and an unchanged baseline

The oracle agent applies the attributed reference patch. The no-op agent leaves the original buggy source unchanged. Neither needs a model login.

Use a new output directory:

```sh
pack_run_dir="$(mktemp -d /tmp/agent-pack-controls.XXXXXX)"
harbor run -p tasks/anyio-cancel-scope -a oracle --ek auto_mounting=false -n 1 -r 0 -o "$pack_run_dir" --job-name anyio-reference
harbor run -p tasks/anyio-cancel-scope -a nop --ek auto_mounting=false -n 1 -r 0 -o "$pack_run_dir" --job-name anyio-baseline
```

Expect reference reward `1` and baseline reward `0`. The baseline's private cancellation failures are the intended result. They should not be counted as environment failures.

Open each job's `result.json` for its native Harbor summary. Each trial's `verifier/results.json` contains named case results, and `verifier/reward.txt` contains the reward. Compare with [the recorded release audit](../evidence/release-audit.json).

Replace the task path with `tasks/better-auth-indexes` or `tasks/werkzeug-multipart` to check another task. Use new job names. Use `-p tasks` to run all three.

Keep `--ek auto_mounting=false`. Writable host-mounted logs did not enforce the intended permission boundary on the recorded Docker Desktop setup. The verified setup uses container-owned logs that Harbor downloads after grading.

## Replay an actual saved agent patch

A replay uses the committed source patch and submitted source hashes. It does not ask a model to solve the task again.

```sh
pack_replay_dir="$(mktemp -d /tmp/agent-pack-replay.XXXXXX)"
python3 tools/replay.py anyio-cancel-scope-standard --output "$pack_replay_dir/anyio-standard"
```

The output directory passed to `--output` must not already exist. Expect reward `1`, `source_hashes_verified: true` and `matches_all_expected_case_statuses: true`. Read its `replay.json`, `results.json` and captured logs.

Choose another trial ID from [TRIALS.md](../TRIALS.md). The Better Auth replay uses the corrected verifier and compares with the stored corrected results. Original native results remain separate.

## Make a fresh coding-agent attempt

This requires your own authorized model login and access to the recorded model. The wrapper uses native Harbor authentication support and the fixed `gpt-6.1-sol` model. Authentication material is not included in this repository. Use [Harbor's supported authentication flow](https://docs.harborframework.com/agents/agent-auth-resolution).

Give the new attempt its own name and store its output outside this repository:

```sh
pack_episode_dir="$(mktemp -d /tmp/agent-pack-episode.XXXXXX)"
python3 tools/episodes.py anyio-cancel-scope --profile standard --job-name anyio-fresh-standard --output "$pack_episode_dir"
```

Use `--profile extended` for the recorded 600-second, high-reasoning profile. Standard uses 300 seconds and medium reasoning. Setup and verification are outside the agent solve deadline. Run at most two local coding-agent attempts concurrently.

The output contains the episode specification, console log and native Harbor job. Inspect that new job's own results. A timeout must remain a timeout even if the source saved at the deadline later passes functional checks.

Do not copy new results over `evidence/trials/` or reuse historical rescoring as the result of a new attempt. `tools/collect_trials.py` is the export utility used for the recorded experiment; it is not required for this fresh-run walkthrough.

## Understand the outputs

| Record | Meaning |
| --- | --- |
| Native Harbor `result.json` | Job or trial outcome, reward and exception information. |
| Verifier `results.json` | Named case statuses and check counts. |
| `submitted.patch` | The production source changes collected from a recorded attempt. |
| `submitted-source-sha256.json` | Hashes of the permitted source submitted by that attempt. |
| `replay.json` | Whether reconstructing that patch reproduces the expected case statuses. |
| `FAIRNESS_REVISION.json` | The explicit correction to overly strict Better Auth checks. |

The [saved-evidence GitHub check](https://github.com/GautamBytes/agent-reliability-taskpack/actions/workflows/evidence-audit.yml) validates committed records and file hashes. It does not run Docker or launch new agents. New experiments should keep their own results and should not silently update the historical proof.
