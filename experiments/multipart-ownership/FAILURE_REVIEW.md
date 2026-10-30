# Native outcomes and collected-source correctness

Native completion and collected-source correctness are separate observations. The primary normal-completion measure was frozen before testing, while the original native verifier reward remains visible for every attempt.

| Attempt | Native outcome | Agent phase, s | Collected checks | Interpretation |
| --- | --- | ---: | ---: | --- |
| [after-01](runs/curated/after-01/harbor-result.json) | TIMEOUT | 300.2 | 171/171 | Deadline reached with passing collected source; not an incorrect-repair result |
| [after-02](runs/curated/after-02/harbor-result.json) | PASS | 208.4 | 171/171 | Normal completion with passing collected source |
| [after-03](runs/curated/after-03/harbor-result.json) | PASS | 268.8 | 171/171 | Normal completion with passing collected source |
| [after-04](runs/curated/after-04/harbor-result.json) | PASS | 272.7 | 171/171 | Normal completion with passing collected source |
| [after-05](runs/curated/after-05/harbor-result.json) | PASS | 188.7 | 171/171 | Normal completion with passing collected source |
| [after-06](runs/curated/after-06/harbor-result.json) | PASS | 210.3 | 171/171 | Normal completion with passing collected source |
| [after-07](runs/curated/after-07/harbor-result.json) | PASS | 266.4 | 171/171 | Normal completion with passing collected source |
| [after-08](runs/curated/after-08/harbor-result.json) | PASS | 283.1 | 171/171 | Normal completion with passing collected source |
| [before-01](runs/curated/before-01/harbor-result.json) | PASS | 176.4 | 100/100 | Normal completion with passing collected source |
| [before-02](runs/curated/before-02/harbor-result.json) | PASS | 189.6 | 100/100 | Normal completion with passing collected source |
| [before-03](runs/curated/before-03/harbor-result.json) | PASS | 184.8 | 100/100 | Normal completion with passing collected source |
| [before-04](runs/curated/before-04/harbor-result.json) | PASS | 198.0 | 100/100 | Normal completion with passing collected source |
| [before-05](runs/curated/before-05/harbor-result.json) | PASS | 212.6 | 100/100 | Normal completion with passing collected source |
| [before-06](runs/curated/before-06/harbor-result.json) | PASS | 227.2 | 100/100 | Normal completion with passing collected source |
| [before-07](runs/curated/before-07/harbor-result.json) | PASS | 219.7 | 100/100 | Normal completion with passing collected source |
| [before-08](runs/curated/before-08/harbor-result.json) | PASS | 164.3 | 100/100 | Normal completion with passing collected source |

All 16 saved patches were independently reconstructed and replayed in clean offline verifiers. 0 collected repairs fail a required check. 1 native attempt reached the solve deadline.

There is no demonstrated reduction in collected-source functional correctness in this study. A timeout with a passing patch is not evidence of a wrong repair. It remains a nonpass under the separately specified normal-completion criterion.

Harbor downloads artifacts after execution and does not establish an atomic filesystem snapshot exactly at the 300-second cutoff. The collected-source metric therefore describes the source Harbor actually supplied to verification. The original exception and timestamps are preserved. No unsuccessful attempt was replaced or silently rerun.

Eight attempts per condition from one model family do not establish a broad difficulty ranking or statistical significance. More requirements and stronger incomplete-fix rejection demonstrate added task scope. They do not alone prove a lower model solve probability.
