# Incomplete-fix controls

These are fixed source variants, not coding-agent attempts. Each patch applies to the original pinned baseline. Names describe deliberately missing behaviour, not a claimed upstream defect.

| Control | Missing behaviour |
| --- | --- |
| old-full-repair | Previous task's complete delimiter fix, without the new quota and ownership API. |
| quota-only | Quotas are wired through the APIs, but failed parses leak sinks and short writes truncate data. |
| close-current-only | Rollback closes only the most recently opened sink and leaks earlier completed files. |
| one-write | Each Data event is offered once, ignoring a valid short-write return count. |
| trust-content-length | Per-file accounting trusts the part's declared length instead of actual payload bytes. |
| exception-only-cleanup | Ordinary exceptions trigger rollback, but cancellation-style BaseException failures leak sinks. |
| omit-request-forwarding | Direct parsers enforce quotas, but Request does not forward its two settings. |
| close-first-duplicate | Request.close visits only the first file per field name. |

Historical parser controls are retained separately: upstream-3081-only, upstream-3089-only, strip-payload-newlines and prior-complete-fix. Their upstream attribution and intentional local mutations remain as recorded in provenance.json and the previous experiment. The completed study must link measured control outcomes rather than assuming all variants are rejected.
