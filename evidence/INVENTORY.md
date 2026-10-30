# Evidence index

`release-audit.json` is the generated final verdict. Regenerate it with `python3 tools/report.py --write`. `release-task-fingerprints.json` identifies the current private programs and public task contracts. `harbor-lint.json` contains the native lint result.

`native-controls/final-references/` and `final-baselines/` retain the final native Harbor job/trial results and verifier reports. Earlier native jobs and calibration workspaces are omitted from the curated review export.

`final-anyio-controls/` uses the hardened final grader. Better Auth's final matrix is under `tasks/better-auth-indexes/evidence/release-semantic-matrix/`. Werkzeug's authoritative matrix is under `tasks/werkzeug-multipart/evidence/docker-adversarial-controls/`. Earlier per-task author and frozen runs remain historical records, not current grader fingerprints.

`trials/` contains six collected coding-agent records, submitted production patches, complete permitted-source hashes, network logs, original private results and tool-only trajectories. Better Auth additionally includes corrected-results.json. `trial-summary.json` preserves original and final metrics together. Raw conversation reasoning is omitted.

`rescored/` records unchanged Better Auth source replays after the initial semantic correction, including the changed private case statuses. `pre-formatting-replays/` preserves the next replay phase. `replays/` contains the final exact-source replays, after the final Prisma formatting correction. No additional coding attempt occurred during rescoring or replay.

`independent-review/` records the source/fairness assessment and actual generated Prisma output with parser/formatter proof. This is delegated review from the available model family, not independent human or cross-family model validation.

Source archives, original licenses, immutable revision records and per-task provenance are retained inside each task. Development logs may record failed setup or intermediate assertions. Those are preserved as history and do not override the named final records.
