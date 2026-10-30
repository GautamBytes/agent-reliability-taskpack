# Agent Reliability Task Pack

Three coding-agent repair tasks based on real bugs in AnyIO, Better Auth and Werkzeug. I built this personal project. The original source and fixes keep their authorship and licenses.

**[Review the proof without running anything →](REVIEW.md)**

The guide includes screenshots, result tables, direct links to logs and all six submitted code patches. [Recorded agent attempts](TRIALS.md) and [grading corrections](FAIRNESS_REVISION.json) are kept together so the final scores have context.

## Recorded results

| Check | Result |
| --- | --- |
| Required checks in reference solutions | 313 pass |
| Original buggy versions | All 3 fail |
| Incomplete fix controls | All 10 rejected |
| Valid alternative fix controls | All 3 accepted |
| Fresh native Codex attempts | 5 finish normally, 1 reaches its solve deadline |
| Saved code patches replayed in clean verifiers | All 6 pass final checks |

There are 317 reported entries. Four are known AnyIO skips or xfails and are separately allowlisted. The 313 required checks include 226 original-project preservation checks, 86 additional behavioural checks and one focused TypeScript compile check.

The GitHub **Saved-evidence audit** checks the committed records, source hashes and file manifest. It does not launch new coding-agent attempts.

## See the saved results

This is an actual browser screenshot of the saved JSON result viewer. It is not a screenshot of a new live test run. The [review guide](REVIEW.md) links each result to its underlying records.

![Original source and reference results](docs/proof/controls.jpg)

[See all agent attempts and audit screenshots](REVIEW.md#screenshots-of-the-saved-results).

## What the tasks ask an agent to fix

| Task | Original issue | What the verifier checks |
| --- | --- | --- |
| [AnyIO cancellation scopes](tasks/anyio-cancel-scope/instruction.md) | [AnyIO #642](https://github.com/agronholm/anyio/issues/642) | Cancellation ownership, nested shields and preserved task-group behaviour on asyncio and Trio. |
| [Better Auth portable indexes](tasks/better-auth-indexes/instruction.md) | [Better Auth #10025](https://github.com/better-auth/better-auth/issues/10025) | Device-code indexes, migrations, schema output, portable names and validation. The collective upstream fix includes my contribution. |
| [Werkzeug multipart parsing](tasks/werkzeug-multipart/instruction.md) | [#3065](https://github.com/pallets/werkzeug/issues/3065), [#3077](https://github.com/pallets/werkzeug/issues/3077), [#3088](https://github.com/pallets/werkzeug/issues/3088) | Exact uploaded bytes when delimiters split across reads. Combines the regression family and adds a local closing-delimiter correction. |

## Read the result limits

The tests were hidden from agents during solving. They are public here for review. Trials use one model family at two budgets. Historical public fixes may be present in model training.

The two Better Auth attempts originally scored 80/83 and 82/83 because some verifier assertions rejected valid schema syntax. I corrected the verifier after all attempts finished and replayed the unchanged patches. The original scores and the timeout remain in the records. All six saved patches passing does not mean all six attempts finished before their deadlines.

Live database verification uses SQLite. Other engines receive representation checks; generated Drizzle code runs against builder metadata. This project has no external benchmark acceptance or employer commissioning. [Full scope and limits](VERIFICATION.md) · [Authorship](OWNERSHIP.md) · [Source credits](SOURCES.md) · [Licenses](NOTICE.md).

## Reproduce

Install Docker and Harbor 0.25.0. The Dockerfiles pin the Python and Node base-image digests, Codex 0.166.0, pnpm 11.1.1 and task dependencies. Each task contains its own build context. Dependencies are installed during image build. Verification runs without network access.

```sh
harbor lint tasks/anyio-cancel-scope tasks/better-auth-indexes tasks/werkzeug-multipart --json
harbor run -p tasks -a oracle --ek auto_mounting=false -n 1 -o /tmp/oss-pack-controls-new --job-name reference
harbor run -p tasks -a nop --ek auto_mounting=false -n 1 -o /tmp/oss-pack-controls-new --job-name baseline
```

The oracle applies the attributed reference patch. The no-op agent leaves the original buggy source unchanged. Reward 1 requires every required check to pass and only the explicitly known upstream nonpasses to remain.

## Run a fresh coding-agent trial

The recorded trials use the account's configured `gpt-6.1-sol` model through Codex's existing ChatGPT login, forwarded by Harbor's native support. No credential contents are stored in this pack. Other users need their own authorized login or supported provider setup.

```sh
for task in anyio-cancel-scope better-auth-indexes werkzeug-multipart; do
	python3 tools/episodes.py "$task" --profile standard
	python3 tools/episodes.py "$task" --profile extended
done
python3 tools/collect_trials.py --final
```

Supply `--harbor /absolute/path/to/harbor` if it is not on PATH. The standard profile uses medium reasoning and a 300-second solve deadline. The extended profile uses high reasoning and a 600-second solve deadline. Setup, source collection and verification are outside that solve deadline. Each invocation starts from the same original public task in a fresh container, with no previous private feedback. Run at most two coding-agent trials concurrently on a local machine.

The agent container contains full baseline source and installed dependencies, one fresh baseline Git commit where applicable, and public instructions/checks. It has no private tests, reference patch, future Git objects or host workspace mount. An internal Docker network permits model/authentication connections through an allowlisted proxy. A startup probe checks that direct internet access and GitHub retrieval fail. Domain-only proxy logs are retained without request headers or bodies. This prevents solving-time public-fix retrieval through normal shell networking; it does not establish that a historical fix was absent from training data.

Keep `--ek auto_mounting=false`. Writable host-mounted verifier logs did not enforce the intended permission boundary on this Docker Desktop installation. Native Harbor instead downloads logs after grading from container-owned storage.

## What gets graded

The full source artifact is collected, but only the permitted production trees enter a clean verifier checkout. Candidate changes to tests, configuration, dependencies or package manifests do not replace the verifier's original files. The runtime reconstructs the trusted baseline, overlays the permitted source and runs the selected public and private checks.

Candidate code runs unprivileged. Root owns rewards and private assertions where the framework permits external checks. The verifier rejects empty/incomplete reports, missing expected cases and unexpected skips. [Framework-specific limitations](OWNERSHIP.md) remain explicit rather than being hidden behind a broad anti-cheating claim.

## Review the work

- [Verification report](VERIFICATION.md) and [trial table](TRIALS.md).
- [Upstream sources](SOURCES.md) and per-task `provenance.json` files.
- [Unsubmitted multipart finding](tasks/werkzeug-multipart/NEW_FINDING_DRAFT.md), with a minimal reproducer and a local correction. The report names the exact additional source snapshot checked and does not claim the finding is novel or accepted upstream.
- [Decision trail](decisions.tsv), including independent-review changes and environment findings.
- `evidence/trials/` retains each submitted production patch, source hashes, private results, native Harbor result and trajectory, and the network boundary evidence.

Run `python3 tools/report.py` to audit the included curated evidence. Run `python3 tools/replay.py TRIAL_ID --output /tmp/new-replay-directory` to reconstruct and verify a saved patch in Docker. The review archive omits duplicate raw workspaces, calibration runs and raw agent conversation files. Curated trajectories contain tool calls and results, with reasoning text omitted. Fresh episode runs create their own raw output for `collect_trials.py`.

The current private-file hashes are in `evidence/release-task-fingerprints.json`. Earlier per-task freezes document earlier phases and remain unchanged. `FAIRNESS_REVISION.json` identifies the later Better Auth verifier corrections and preserved originals.

Model the Domain shaped the separate cancellation, index and parser contracts. Test Behavior, Not Implementation led to real API/database/byte checks and valid alternative-implementation controls. Prove It Works required pinned baseline failures, reference success and actual native coding-agent runs. Separate Before Serializing Shared State gave each attempt a new source tree, container and output directory.
