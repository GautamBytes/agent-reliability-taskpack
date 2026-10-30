# Scope and remaining limits

This is a focused repair of the newline/fragmentation regression family, not a claim of full multipart RFC conformance. The graded new grammar uses unpadded CRLF delimiters. Existing selected public tests preserve additional ordinary behavior.

Independent review found two separate behaviors outside the reference patch's scope:

- Long optional transport padding after a delimiter can still make parsing depend on segmentation.
- A malformed closing-boundary lookalike such as `\r\n--b--X\r\n` may retain the pinned parser's truncation behavior.

The public instructions state those exclusions. The task does not hide them or count their absence as proof of universal correctness. Neither limitation invalidates the reproduced byte loss on valid ordinary uploads or the authored correction for splitting the terminal closing dashes.

The 34 authored holdouts run as trusted assertions without importing candidate code. They query a separate UID 1000 worker through JSON, and their expected values and reports stay root-only. The 31 upstream preservation cases execute in an unprivileged pytest process. Their JUnit results are validated against the exact expected case list. This is a practical evaluation boundary, not a formal proof against every possible malicious candidate program.
