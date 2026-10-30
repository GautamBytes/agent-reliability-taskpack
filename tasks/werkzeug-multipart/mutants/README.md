# Partial-fix controls

Each patch applies to the exact buggy baseline. These are negative controls, not reference solutions.

- `upstream-3081-only.patch` contains only the production change from the actual first accepted fix. It fixes trailing-data handling but retains a later-reported newline error.
- `upstream-3089-only.patch` contains the complete attributed upstream parser change through the second accepted fix. It still emits a CR when an incomplete closing delimiter contains only the first terminal dash. The private partition and WSGI short-read checks reject it.
- `strip-payload-newlines.patch` starts from the task reference but strips newline bytes from emitted payload. It is a plausible corruption-hiding shortcut that violates exact binary preservation.

The final task reference contains the upstream fixes plus an authored suffix-retention correction for incomplete closing delimiters. That additional correction has not been submitted to or accepted by upstream.
