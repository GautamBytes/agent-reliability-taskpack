# Primary sources

Each task has a machine-readable provenance record with immutable source and reference hashes. These links identify the upstream problems and work being credited.

- [AnyIO issue 642](https://github.com/agronholm/anyio/issues/642) and [accepted PR 648](https://github.com/agronholm/anyio/pull/648). The [rejected simplification](https://github.com/agronholm/anyio/commit/a7284b73067a965aa6f037ecc703449b05f644db) supplies a real wrong-fix control.
- [Better Auth issue 10025](https://github.com/better-auth/better-auth/issues/10025) and [accepted PR 10059](https://github.com/better-auth/better-auth/pull/10059). The task credits the collective fix and identifies Gautam's three commits separately.
- [Werkzeug issue 3065](https://github.com/pallets/werkzeug/issues/3065), [issue 3077](https://github.com/pallets/werkzeug/issues/3077) and [issue 3088](https://github.com/pallets/werkzeug/issues/3088), with [PR 3081](https://github.com/pallets/werkzeug/pull/3081) and [PR 3089](https://github.com/pallets/werkzeug/pull/3089). This task transparently combines the regression family and adds a separately attributed local correction.
- [Harbor configuration](https://docs.harborframework.com/tasks/configuration), [separate verifier](https://docs.harborframework.com/tasks/separate-verifier) and [task creation](https://docs.harborframework.com/tutorials/create-a-task). These define the task format and native execution model used here.
- [Terminal-Bench implementation rubric](https://github.com/harbor-framework/terminal-bench/blob/main/docs/prompts/task-implementation.toml). Its separation, reproducibility and behavior-based verification criteria informed the work.
- [SWE-bench grading implementation](https://github.com/SWE-bench/SWE-bench/blob/main/swebench/harness/grading.py). Its distinction between regression resolution and preservation checks informed the score gates.

No upstream contribution or affiliation is implied by packaging these sources into personal evaluation tasks. The source licenses remain with each repository.
