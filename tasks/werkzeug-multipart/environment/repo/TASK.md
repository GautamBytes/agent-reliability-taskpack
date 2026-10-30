# Repair streaming multipart byte preservation

An upload service sees two intermittent failures. Uploaded files ending in CR lose a byte around the 64 KiB read boundary. Other files gain CR or LF bytes when a delimiter is split between reads. The input bytes are the same; the result changes with network segmentation.

Repair the pinned Werkzeug repository in `/app/repo`. Change production code under `src/werkzeug`. Do not replace the package or download a newer version. The grader restores your production source onto a clean copy of this repository. It ignores candidate changes to tests, configuration and dependencies.

## Required behavior

- For the unpadded CRLF delimiter grammar described below, parse `multipart/form-data` through `MultipartDecoder`, `FormDataParser` and `Request` without losing, adding or normalizing payload bytes. CR, LF and CRLF can be genuine file or text-field content.
- The final part values and metadata must be independent of read fragmentation. Support a split at any position in headers, separator CRLF, opening delimiters and closing delimiters, including between their two terminal dashes. One-byte input reads are valid.
- Preserve mixed text fields, binary files, empty files, empty fields and field order. Partial boundary-prefix strings and a boundary followed by a non-delimiter character such as `X` or `!` remain payload data. Boundary strings may contain characters with meaning in regular expressions.
- Maintain streaming behavior. Large payloads must produce `Data` before EOF instead of buffering the whole request. It is valid to retain a suffix that could become an incomplete delimiter.
- Preserve rejection of truncated multipart messages in strict parsing mode and the existing memory and part-count limits.
- Preserve the rest of the package's current behavior. The exact number and sizes of intermediate `Data` events are not part of this task, provided their concatenation preserves the part payload and completion semantics.

The service uses Python 3.12 and the installed dependencies. No additional runtime dependency is needed. The source tree contains the pinned upstream public tests. Some old assertions in `test_decoder_data_start_with_different_newline_positions` describe an incorrect intermediate event fragment. They are not a requirement to retain that incorrect split. The private verifier checks full byte preservation and runs the other original multipart/form-parser preservation tests.

For this repair, opening and intermediate delimiters are `--BOUNDARY\r\n` after the separator CRLF, and the closing delimiter is `--BOUNDARY--\r\n`. Optional transport padding after a boundary and malformed closing tokens such as `--BOUNDARY--X` are outside the repair scope. Preserve their baseline behavior; this task does not ask for complete RFC grammar conformance or fixes to those separate edge cases.

## Public reproduction

```sh
PYTHONPATH=src python - <<'PY'
import io
from werkzeug.wrappers import Request

payload = b"\0" * 65535 + b"\r"
with Request.from_values(data={"file": (io.BytesIO(payload), "sample.bin")}, method="POST") as request:
    actual = request.files["file"].read()
    assert actual == payload, (len(payload), len(actual))
PY
```

The current source returns 65,535 bytes instead of 65,536. Fix this and the related fragmentation cases described above. You may add your own local tests. Only production-source changes are collected.

## Public development checks

```sh
PYTHONPATH=src python -m pytest tests/sansio/test_multipart.py tests/test_formparser.py -q -k 'not test_decoder_data_start_with_different_newline_positions'
```

These checks preserve ordinary behavior but do not cover the full reported failures. Do not infer correctness from their passing alone.
