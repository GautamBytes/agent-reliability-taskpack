# Contracts to implement before freezing

## Common

Use the exact vendored Werkzeug baseline b48878cf16dfca3c89ac58aca47ab1ecfcb71354, Python3.12.12 and the current task runtime. Only production src/werkzeug source is overlaid into a clean verifier. Preserve selected31 upstream multipart/form-parser tests, excluding the same18 obsolete intermediate-fragment assertions. No new dependency. Each version has its own hidden grader and an attributed/local reference. The old three published tasks and records stay unchanged.

## Basic

Repair the real public Request.from_values upload bug at the 64KiB read boundary. Preserve every byte of a file whose final payload contains CR, LF or CRLF. Same31 public preservation checks plus a focused private trailing-newline family, ideally5 cases matching the current real-request payload variants. Other fragmented decoder behavior is outside this version's repair scope. Use an actual upstream-only reference if it satisfies this narrower contract, otherwise the existing attributed complete reference with its full provenance.

## Hard

Include all current34 private fragmentation/preservation checks and their explicit public contract, plus the following coherent decoder requirements. This extends the previous task rather than silently adding requirements to an old trial.

1. New delimiter grammar uses CRLF line framing. Opening and intermediate delimiter lines may have zero or more ASCII SP or HTAB bytes after the boundary and before CRLF. Closing delimiter lines use boundary plus two terminal dashes, optional SP/HTAB, then CRLF or true end-of-input. EOF closure is accepted only when the stream is declared complete. Preserve existing selected public newline behavior outside these new cases.
2. An apparent boundary with any other trailing character (including --BOUNDARY--X, --BOUNDARY---, or padding then X) is payload, not a delimiter. Its CR/LF and spaces/tabs must be returned byte-for-byte. A full valid delimiter later must still be found. A chunk ending immediately after --BOUNDARY-- must not discard remaining bytes or assume EOF.
3. Values and metadata must be unchanged by every two-chunk split and by one-byte and seeded multi-chunk partitions. Cover binary payload, fields and files, empty parts, repeated field names, regex-special valid boundary tokens, and lookalike tokens interleaved with later valid parts.
4. Exercise public Request/FormDataParser/MultipartDecoder paths. Require strict rejection when no valid closing delimiter exists, part-count/memory limits, and real Data progress before EOF for large ordinary payloads. Do not add a timing microbenchmark or require an internal algorithm/helper.
5. Bound fixtures and subprocesses so hangs fail deterministically. No live network or external service in verification. Clearly label semantic cases vs parameter combinations. The local reference is not an accepted upstream fix and must be credited separately.

Reference author and verifier author should independently construct grammar cases from this contract and resolve questions before freezing. Consult RFC2046 section5.1.1/RFC7578 for delimiter grammar, but this is a bounded repair contract, not a full RFC-compliance claim.
