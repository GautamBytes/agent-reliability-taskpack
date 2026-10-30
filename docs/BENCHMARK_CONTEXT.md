# How this pack relates to established benchmarks

This is a personal collection of agent repair tasks, using native Harbor format. The closest comparison is task authoring rather than building a new evaluation framework.

## Harbor provides the execution format

Harbor's [task-creation guide](https://docs.harborframework.com/tutorials/create-a-task) separates the problem statement, configuration, environment, reference solution and verifier. Its [separate-verifier mode](https://docs.harborframework.com/tasks/separate-verifier) transfers collected artifacts into a fresh grading environment. This pack uses that structure and has recorded native Harbor runs.

The recorded pack uses task schema 1.4 with Harbor 0.25.0. Current official examples can use newer schemas. Reproduction instructions pin the version that actually ran here.

| Harbor concept | Where it lives here |
| --- | --- |
| Agent-facing problem | `tasks/<task>/instruction.md` |
| Configuration and deadlines | `tasks/<task>/task.toml` |
| Agent workspace | `tasks/<task>/environment/` |
| Reference solution | `tasks/<task>/solution/` |
| Separate verifier | `tasks/<task>/tests/` |
| Agent artifacts and results | `evidence/trials/` and `evidence/replays/` |

## Terminal-Bench shares the authoring pattern

For a concrete official example, [session-window-debug](https://github.com/harbor-framework/terminal-bench/tree/main/tasks/session-window-debug) gives an agent a broken processor, collects changed source and uses a separate verifier to produce a reward. Its [configuration](https://github.com/harbor-framework/terminal-bench/blob/main/tasks/session-window-debug/task.toml) and [test entry point](https://github.com/harbor-framework/terminal-bench/blob/main/tasks/session-window-debug/tests/test.sh) make that workflow inspectable.

This pack follows the same broad workflow. That similarity does not establish equal difficulty or acceptance. Current [Terminal-Bench contribution guidance](https://github.com/harbor-framework/terminal-bench/blob/main/CONTRIBUTING.md#task-guidelines) seeks challenging expert work and open-internet evaluation. These recorded trials restrict networking, use historical issues and have only six attempts from one model family. All six saved patches pass. They are not evidence of frontier-level task difficulty.

The [official implementation rubric](https://github.com/harbor-framework/terminal-bench/blob/main/docs/prompts/task-implementation.toml) also evaluates functional verification, instruction alignment, reproducibility and reviewability. Those are useful design criteria. This repository does not claim to have passed the official submission process.

## SWE-bench shares the real-issue repair pattern

[SWE-bench](https://github.com/SWE-bench/SWE-bench) evaluates patches against real GitHub issues. Its [grading implementation](https://github.com/SWE-bench/SWE-bench/blob/main/swebench/harness/grading.py) distinguishes tests that must start passing from tests that must keep passing.

This pack likewise checks repaired behaviour and preserved behaviour. It adds extra cases and incomplete-fix controls around attributed source revisions. Its native format remains Harbor. It is not a SWE-bench dataset export, leaderboard result or accepted SWE-bench contribution.

## What the project demonstrates

The evidence demonstrates that these tasks can be built and run, that their reference fixes pass, that the original bugs and selected incomplete fixes fail, and that recorded agent patches can be replayed. It also shows a verifier-fairness correction with the original results retained.

The evidence does not establish broad benchmark coverage, independently calibrated difficulty, training-data independence, commissioned company work or external benchmark acceptance. Those are separate claims that would need separate proof.

Sources checked on 30 October 2026. Upstream documentation and benchmark requirements can change.
