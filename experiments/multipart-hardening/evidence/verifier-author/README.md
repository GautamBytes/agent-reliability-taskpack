# Verifier coverage and fixed-source controls

The final authoritative records are `basic-final/summary.json` and `hard-final/summary.json`. Earlier development and reviewed directories record pre-freeze work. They do not replace the final verdicts. No coding-agent attempts are counted in these directories.

Both versions preserve the same 31 selected upstream multipart and form-parser cases. The same 18 obsolete intermediate-fragment assertions remain excluded. Basic adds five real `Request.from_values` trailing-newline cases, for 36 required checks. Hard retains the earlier 34 private cases and adds 35 parameterized cases, for 100 required checks.

| New hard family | Parameter cases | Observable behaviour |
| --- | ---: | --- |
| Padding at every two-chunk split | 4 | Opening, intermediate and closing SP/HTAB padding preserves fields and file bytes. |
| Closing delimiter at true EOF | 3 | Bare and padded closings complete correctly at every split and in one-byte reads. |
| False closing delimiters | 6 | Invalid suffixes remain byte-exact payload before a later valid delimiter. |
| False padded separators | 3 | Padding followed by a non-delimiter stays payload. |
| One-byte and seeded partitions | 3 | Mixed fields, files, repeated names and empty files survive partitions with plain, regex-special and 70-byte boundaries. |
| Public parser paths and short reads | 6 | FormDataParser and Request preserve fields, filenames, content types and bytes with actual capped reads. |
| Invalid final close | 4 | Strict parsing rejects messages with no valid closing delimiter. |
| Ambiguous close prefix | 3 | Neither Epilogue nor a final Data event is emitted before a valid line ending or true EOF resolves the prefix. |
| Streaming before EOF | 1 | A large padded part emits a correct byte prefix without buffering the entire message. |
| Epilogue separation | 2 | Epilogue bytes never become file payload. |

Each split or random partition inside a case is a subcase, not another independent test. Expected part values are built from explicit fixture payloads rather than output computed by the reference parser.

Trusted pytest assertions run without importing candidate code. A separate worker drops to UID 1000 before candidate imports. It returns ordinary API outputs through JSON RPC. Worker event loops drain until NeedData or Epilogue without assuming a particular Data event size. The trusted RPC deadline is four seconds per call; private pytest cases have a five-second deadline. Each verifier stage is bounded at 90 seconds.

The positive `fragmented-data` control extends the complete hard reference with an equivalent implementation that splits large Data events into at most 64 bytes. It preserves their concatenation and final more_data flag. It passes both task versions. This catches the earlier arbitrary event-count cap and demonstrates that the final grader accepts a different intermediate event strategy.

Two additional pre-freeze review fixes made observations faithful to the public contract. The short-read stream caps both read and readinto, because the two public parser paths use different methods. The ambiguous-close probe records final Data events as well as Epilogue events. These harness fixes were completed before any counted coding-agent attempt.

`baseline-integrity.json` confirms both copies of the agent source and verifier baseline match the old task byte for byte. Case manifests were generated from actual collection in the pinned verifier images. Every final control has zero skips.

Run a new fixed-source control matrix with a new output directory:

```sh
python3 evidence/verifier-author/run_controls.py hard --output /tmp/new-hard-controls --variant reference --variant fragmented-data --variant baseline --variant old-complete --variant upstream-3089-only --variant strip-payload-newlines
```

The script builds the verifier image and uses a fresh candidate tree and offline container for each variant. Root-owned logs are copied from a container-owned anonymous volume after execution. No model login or inference call is involved.
