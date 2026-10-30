# Independent behavioural verifier

The after task requires **171 named cases** with zero skips. It preserves all 100 cases from the previous hard task and adds 71 parameter cases for the public upload-quota and resource-ownership contract. These counts describe parameterized checks, not 171 independent bugs.

The final fixed-source matrix is [final-171/summary.json](final-171/summary.json). Each row records the exact patch hash and confirms that all 59 production source hashes graded by the verifier match the reconstructed candidate. The unchanged before verifier has a [separate control matrix](before-final/summary.json).

| Submitted after source | Passed | Reward |
| --- | ---: | ---: |
| New reference | 171/171 | 1 |
| ExitStack ownership alternative | 171/171 | 1 |
| Early-collection alternative | 171/171 | 1 |
| Original baseline | 59/171 | 0 |
| Previous complete hard reference | 103/171 | 0 |
| Quotas without complete writes or rollback | 127/171 | 0 |
| Close only the current sink | 156/171 | 0 |
| Ignore short-write results | 161/171 | 0 |
| Trust declared part length | 161/171 | 0 |
| Catch Exception but not BaseException | 165/171 | 0 |
| Omit Request quota forwarding | 167/171 | 0 |
| Close only the first duplicate field | 169/171 | 0 |

These are offline fixed-source controls, not model attempts. The incomplete variants each apply to the same original source. The old reference still satisfies all 100 retained checks. Its three other passing cases do not establish the new quota or ownership contract.

## What the added cases observe

- All four public entry paths enforce inclusive per-file and aggregate raw-payload limits. Configuration validation is not silenced. New keyword-only arguments and Request defaults follow the stated public interface.
- Quotas count raw UTF-8 bytes and actual streamed content. Repeated names, empty files, false part Content-Length, headers, padding and epilogue follow the explicit accounting rules. Retried writes do not count bytes twice. The new limits do not affect URL-encoded input.
- Short writes preserve both files exactly. Invalid write results fail rather than silently truncate or spin.
- Reader, writer, seek, later factory, decoder and return-collection errors release all acquired streams. Ordinary exceptions and cancellation-style BaseException values retain the original exception object.
- A failing close does not prevent cleanup of other owned streams or replace the primary failure. Shared sink identities receive one parser-initiated cleanup call.
- Successful parses leave their output streams open. A later failure on a reused parser does not close streams already transferred by an earlier successful parse. New parse counters start fresh.
- Request.close visits repeated file names, deduplicates shared streams per call, continues after ordinary close errors and does not trigger lazy parsing or close borrowed input.

The [coverage map](coverage.json) lists exact parameter-group counts. The [baseline integrity record](baseline-integrity.json) confirms both vendored starting trees are byte-equal to the previous pinned source and every old named case remains present.

## Fairness and isolation

Trusted pytest assertions stay in the protected root process. A JSON worker drops supplementary groups and switches to UID 1000 before importing the candidate. Tests invoke public interfaces and inspect output bytes, exceptions and visible stream lifecycle effects. The grader restores trusted tests and baseline configuration before overlaying permitted production source. Docker grading has no network, a read-only root filesystem and protected container-owned output.

No case requires a specific helper, algorithm, Data-event split or cleanup order. Quota failures permit different accepted prefixes, provided no sink receives bytes beyond a limit. Return-collection fault tests inject at constructor calls and accept failures before any input has been read. The early-collection positive control verifies that constructing mutable result collections before parsing is accepted. Immutable Request collections retain their original construction behaviour.

## Changes made before freezing

The initial [development-reference](development-reference/summary.json) check exposed a fixture mistake. A URL-encoded read-all operation was accidentally limited to seven bytes by the multipart short-read fixture. That test now uses a complete read, because URL-encoded streaming repair is outside this contract. The initial early-collection alternative also failed to support ImmutableMultiDict and was corrected before serving as a positive control.

The [prefreeze-168](prefreeze-168/summary.json) matrix passed all three complete implementations and rejected all incomplete controls. Three final cases then covered ownership transferred across a later failed parse, field-quota rollback after an earlier completed file, and the explicitly specified public keyword-only/default API. The final 171-case matrix passed all three complete implementations. No counted model attempt was used to tune these assertions.

The existing task-pack limits on arbitrary malicious candidate introspection still apply. This is evidence of controlled behavioural evaluation, not a universal sandbox-security claim.
