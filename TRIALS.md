# Native coding-agent trials

All attempts used Codex 0.166.0 and gpt-6.1-sol through native Harbor 0.25.0. Each started fresh with the same public task and no private feedback.

| Task | Profile | Deadline | Original checks | Final checks | Run outcome |
| --- | --- | ---: | ---: | ---: | --- |
| anyio-cancel-scope | extended / high | 600s | 165/169 | 165/169 | Completed |
| anyio-cancel-scope | standard / medium | 300s | 165/169 | 165/169 | Completed |
| better-auth-indexes | extended / high | 600s | 82/83 | 83/83 | Completed |
| better-auth-indexes | standard / medium | 300s | 80/83 | 83/83 | Timed out; saved patch passes |
| werkzeug-multipart | extended / high | 600s | 65/65 | 65/65 | Completed |
| werkzeug-multipart | standard / medium | 300s | 65/65 | 65/65 | Completed |

AnyIO has four separately allowlisted upstream nonpasses: two Python-version skips and two xfails. The 165 required checks pass. No unexpected skip is accepted.

The Better Auth verifier originally rejected valid Drizzle bracket notation and bracket-quoted SQL Server OBJECT_ID syntax. A later independent review also found a whitespace-sensitive Prisma check. The corrected verifier executes generated Drizzle schemas and accepts the documented Prisma formatting alternatives. The public tasks and submitted patches did not change. All native attempts had finished before the correction. Original results, intermediate grader versions and exact case-status changes remain in the evidence. See FAIRNESS_REVISION.json and evidence/rescored/.

Five attempts completed normally. One exhausted its 300-second agent deadline. All six saved source patches pass the final functional checks and were reconstructed from their patches in fresh offline verifier containers. The timeout remains a timeout, and rescoring is not a new agent attempt.

This is a usability check of three historically public tasks at two budgets from one model family. It does not estimate general model accuracy, establish training-data independence or demonstrate frontier-model difficulty.
