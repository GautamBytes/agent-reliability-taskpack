# Verified scope and results

This report describes three personal, AI-assisted evaluation tasks. The source issues and fixes are attributed in SOURCES.md and each task's provenance record. They are full-repository repair tasks with separate private verifiers, packaged in Harbor format.

## Required checks

| Task | Required upstream preservation | Authored behavioral holdouts | Other required checks | Known upstream nonpasses |
| --- | ---: | ---: | ---: | ---: |
| AnyIO cancellation scopes | 145 | 20 | 0 | 4 |
| Better Auth portable indexing | 50 | 32 | 1 focused TypeScript compile | 0 |
| Werkzeug multipart bytes | 31 | 34 | 0 | 0 |
| Total | 226 | 86 | 1 | 4 |

The final reference patches pass all 313 required checks. Reports contain 317 entries because AnyIO retains two Python-version skips and two upstream xfails. These are exact allowlisted cases. Unexpected skips, missing reports and missing expected case names fail verification. Parameterized checks are not independent production bugs.

AnyIO excludes 66 optional uvloop parameter cases at collection. Better Auth excludes nine PostgreSQL-only migration cases because no PostgreSQL service is provided. Werkzeug excludes 18 intermediate-fragment assertions that contradict the repaired streaming behavior. The supported observable behavior is concatenated payload bytes. None of these exclusions is counted as a passing check.

## Controls

Native Harbor runs the three reference patches successfully and rejects the three unchanged upstream baselines, with zero infrastructure exceptions. The final task-level matrices reject ten partial fixes. Three of those represent actual historical upstream repair attempts. Better Auth also accepts three valid alternatives that change a MySQL local variable, a SQL Server string bound and Prisma attribute formatting.

The authoritative control records are:

- `evidence/native-controls/final-references/` and `final-baselines/`.
- `evidence/final-anyio-controls/summary.json`.
- `tasks/better-auth-indexes/evidence/release-semantic-matrix/summary.json`.
- `tasks/werkzeug-multipart/evidence/docker-adversarial-controls/summary.json`.

Werkzeug's separate report-forgery probe manufactures a public report but still fails the root-side private assertions. Its manufactured public case records are not additional executed tests or part of the 313 required-pass count. AnyIO's privilege probe confirms candidate imports run as UID 1000 and protected files cannot be read or rewritten. The documented in-process marker and JavaScript report-trust limits remain.

## Coding-agent trials

Six actual native Harbor Codex attempts used gpt-6.1-sol. Each task ran once with medium reasoning and a 300-second solve deadline, and once with high reasoning and a 600-second deadline. Each attempt started in a new container with the original public task, full pinned source and installed dependencies. No earlier attempt's private feedback was supplied.

Five attempts completed normally. One Better Auth attempt exhausted its 300-second deadline. All six saved source patches pass the final functional checks. Each was reconstructed from its exact production patch, checked against submitted source hashes and graded again in a fresh offline container. TRIALS.md preserves the distinction between normal completion and a functionally passing cutoff artifact.

The original Better Auth results were 80/83 and 82/83. Review showed that the failures rejected valid generated Drizzle notation and SQL Server quoting. The verifier was corrected after all attempts had finished. A further independent review reproduced a Prisma formatting false negative and validated the alternative with the official formatter offline. The public contracts, case identities and agent patches stayed unchanged. Original reports and intermediate grader copies remain preserved in FAIRNESS_REVISION.json, `evidence/rescored/` and per-task evidence. The coding agents were not rerun to replace these outcomes.

## Isolation and reproduction

Agent images contain no private verifier, reference patch or future Git objects. An internal Docker network routes allowed model and authentication traffic through a domain-only proxy. Each startup probe confirms that GitHub requests through the proxy and direct internet access fail. Actual allowed API and denied GitHub connections are included for every attempt. This prevents normal shell retrieval of a public fix during solving. It does not prove that a historical fix was absent from training data.

Only permitted production source is overlaid on a clean verifier baseline. Candidate tests, package manifests, dependencies and configuration do not replace trusted files. Verification has no network. Candidate execution is unprivileged, while root owns the reward and trusted reports where the framework supports an external assertion process. Container-owned logs and `--ek auto_mounting=false` avoid the ineffective host-bind permission boundary observed on Docker Desktop.

Python and Node base images are pinned by digest. Codex, pnpm and direct task dependencies are pinned. Operating-system packages still come from build-time apt repositories, so this is not a claim of bit-for-bit identical image rebuilds.

`python3 tools/report.py` checks the curated evidence, current verifier revision, patch hashes, case counts, network probes, trial fingerprints and control outcomes. `python3 tools/replay.py TRIAL_ID --output /tmp/new-replay-directory` rebuilds a verifier and replays a submitted source patch. It requires Docker and image-build network access. The verifier itself remains offline.

## Limits and assessment

SQLite queries, migrations and constraints execute directly. Generated Drizzle schemas execute against installed builder metadata. MySQL, SQL Server, PostgreSQL and Prisma receive representation checks rather than live engine integration. The compiler check covers the stated type contract rather than the entire Better Auth monorepo.

The multipart task combines a documented regression family and includes a local closing-delimiter correction. An unsent reproducer also checks one explicitly pinned newer source snapshot. The finding has not been submitted, accepted or established as novel. Its delimiter grammar is bounded in the task's LIMITS.md.

This pack has three historically public tasks and trials from one model family. All six saved patches passed. These results demonstrate runnable tasks and functioning verification, not a broad or statistically calibrated frontier-model difficulty benchmark. The privilege controls do not prove resistance to every malicious candidate program.

A fresh delegated review checked source bytes, patch hashes, case counts and verifier fairness. This was an automated review from the same available model family. It is not independent human review or external benchmark acceptance.

Model the Domain kept the three repair contracts distinct. Test Behavior, Not Implementation led to the semantic Drizzle checks and valid Prisma formatting control. Prove It Works required final baselines, references and exact-source patch replays. Separate Before Serializing Shared State kept each attempt's source and runtime independent.
