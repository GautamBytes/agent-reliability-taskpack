# OSS task pack v2 work plan

Outcome: replace the portfolio's synthetic tasks with three reproducible upstream issue repairs, evaluate fresh coding-agent attempts against private verifiers, and write an evidence-backed application answer under 2,000 characters. Quality ratings remain judgments. A numeric target cannot substitute for verified gates or external acceptance.

## Figure-it-out workflow

1. Read the Principles section of poteto-mode. Done.
2. Frame. Three full-repository tasks, two fresh native coding-agent attempts per task, source provenance, reference/baseline/partial-fix controls and a report. Risks are historical dependency reproduction, native model connectivity and benchmark contamination.
3. Design. Pin source trees and dependencies. Build baseline verification before authoring prompts or running coding agents. Use Harbor's existing separate-verifier contract.
4. Run the loop. Each task must fail its intended regressions at the actual upstream baseline, pass with the attributed upstream fix, and preserve working behavior. Reject broken environments rather than counting them as agent failures.
5. Keep the audit trail. The coordinator alone appends decisions.tsv. Each task author owns a distinct task directory, image tag, fixture and evidence directory.
6. Verify and hand back. Re-run the final controls, audit trial logs and source artifacts, package the current version inside the existing Downloads project, and rewrite the answer using only verified facts.

## Throughput checkpoint

- Blocking first steps. Prove native Harbor Codex accepts the configured model/login. Prove each upstream regression at its pinned revision and establish dependency locks.
- Independent workstreams. AnyIO, Better Auth and Werkzeug authoring run in separate directories and containers. The coordinator owns native agent setup, trial scheduling, aggregation and packaging.
- Shared mutable state. No shared repository checkout, candidate tree, test database, container name or output directory. Only the coordinator writes manifests and the audit trail.
- Smallest safe decomposition. One owner per upstream task. A fresh independent reviewer checks instructions, tests and attribution before trials count as final.

## Architecture decision

Compare native Codex inside Harbor's container with host Codex using a restricted Docker tool gateway. Choose native Harbor because it already supports protected authentication, independent agent containers and a separate verifier. Prompt-only host workspace isolation is not sufficient. Solve-time networking must permit model connectivity while preventing retrieval of upstream fixes where practical; record the measured boundary and remaining model-memory contamination risk.

## Definition of done

- Immutable baseline/fix source, license, issue/PR URLs and production-file scope recorded for all three tasks.
- Runnable full-repository workspaces. No future Git history or private/reference files in agent images.
- Baseline regression failure and reference success reproduced in the same pinned runtime; preservation checks run and zero unaccounted skips.
- Credible partial fixes rejected. Include an upstream-rejected simplification where reproducible.
- At least two independent native coding-agent attempts per task, with fixed public instructions, explicit deadlines/budgets, submitted source/patches and trace-backed outcomes.
- Private tests exist only in a fresh verifier. Root rewards remain separate from candidate execution. Infrastructure errors are reported independently of correctness failures.
- Final Harbor lint/oracle/no-op evidence, reproducible commands, verified archive and truthful answer.
- Independent portfolio assessment explains strengths and remaining limits, without promising a shortlist or upstream acceptance.
