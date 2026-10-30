# Better Auth task verification

The final `release-semantic-matrix/summary.json` is the authoritative task-level control evidence. Earlier frozen runs and `grader-freeze.json` document prior phases. The current hashes are in the portfolio-level `evidence/release-task-fingerprints.json`. See `FAIRNESS_REVISION.json` for the explicit later corrections. The runtime uses Python 3.12.12 and Node 24.11.1, an unprivileged candidate process, a read-only container root, no network and container-owned verifier logs.

| Variant | Passed | Failed | Skipped | Reward |
| --- | ---: | ---: | ---: | ---: |
| baseline | 51 | 32 | 0 | 0 |
| reference | 83 | 0 | 0 | 1 |
| mysql_without_existence_guard | 82 | 1 | 0 | 0 |
| schema_only | 53 | 30 | 0 | 0 |
| unchecked_custom_codes | 79 | 4 | 0 | 0 |
| utf16_index_names | 81 | 2 | 0 | 0 |

The 83 checks comprise 44 original device authorization checks, six extracted original SQLite migration checks, 32 authored holdouts and one focused TypeScript compilation check. The PostgreSQL-only upstream group is explicitly excluded and is not counted as a pass. MySQL, SQL Server, PostgreSQL and Prisma receive representation checks. Generated Drizzle TypeScript executes against the actual provider builders and table metadata. Only SQLite is executed as a database engine.

The public command passed all 50 preservation checks in the actual agent image. See public-image-tests.log. Earlier author-local directories record development runs under Node 24.19.0 and are not the frozen release verdict.

The baseline and reference run the same private suite. The reference patch is the attributed 11-production-file selection from the collective accepted upstream fix. All four deliberately incomplete fixes are rejected. Three valid alternative fixes pass. Native coding-agent trials and final portfolio-wide controls are included in the portfolio-level report.
