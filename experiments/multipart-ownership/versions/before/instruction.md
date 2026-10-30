# Repair streaming multipart parsing across fragmented and ambiguous delimiters

An upload service sees corrupted files and incomplete forms. Some files lose CR near a 64KiB read boundary. Other payloads gain bytes, or end early, when a boundary-like string is split between network reads. Repair the pinned Werkzeug repository at `/app/repo`.

## Required behaviour

1. Preserve the exact final bytes and metadata of fields and files through `MultipartDecoder`, `FormDataParser` and `Request`. CR, LF, CRLF, NUL and other binary bytes may be genuine payload. Keep repeated field names, part order, empty fields and empty files. Boundary tokens can contain valid characters that also have meaning in regular expressions.
2. Results must be independent of read fragmentation. A split may occur at any byte in a header, separator line break, opening or intermediate delimiter, padding or closing delimiter. One-byte input reads are valid. For the added fragmentation cases, `Data` events may be split differently provided concatenated bytes and part completion match. The selected original tests remain required, including their legacy complete-buffer event expectations.
3. Handle delimiter lines with optional transport padding. For the new CRLF grammar, an opening or intermediate line is `--BOUNDARY` followed by zero or more ASCII spaces or horizontal tabs and CRLF. A closing line is `--BOUNDARY--`, optional spaces or tabs, then CRLF or the true end of input. Existing selected upstream acceptance of legacy CR-only and LF-only line endings must continue to work.
4. A chunk ending immediately after `--BOUNDARY--`, or its padding, is still ambiguous while more input may arrive. Do not accept a bare closing token until the stream is declared complete. A complete line ending can confirm closure earlier. Apparent delimiter strings with invalid trailing characters remain byte-for-byte payload. Examples include `--BOUNDARY--X`, `--BOUNDARY--!`, `--BOUNDARY---`, `--BOUNDARY----` and a token followed by padding then `X`. A later valid delimiter must still be recognized.
5. Preserve streaming progress. Large ordinary payloads must produce `Data` before EOF rather than buffering the whole upload. Retaining a suffix that could become an incomplete delimiter is valid. Preserve strict rejection when no valid closing delimiter exists, existing memory limits and part-count limits.
6. Keep the existing public API and other selected multipart/form-parser behaviour. This is a bounded parser repair contract, not a request to implement every MIME feature or all RFC compliance. No additional runtime dependency is needed.

## Public reproduction and checks

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

The current source returns 65,535 bytes instead of 65,536. It also mishandles some fragmented delimiter and closing-lookalike inputs described above. You may add local tests to explore those requirements.

```sh
PYTHONPATH=src python -m pytest tests/sansio/test_multipart.py tests/test_formparser.py -q -k 'not test_decoder_data_start_with_different_newline_positions'
```

The selected 31 original tests preserve working behaviour. Eighteen old intermediate `Data`-fragment assertions are excluded because they encode a known incorrect split. Exact final payload preservation remains required.

## Submission

Change production source under `src/werkzeug`. The grader restores that source into a clean trusted checkout and runs public preservation and private behaviour checks in a separate offline environment. Candidate edits to tests, configuration, dependencies or Git metadata do not replace the grader's originals. Do not download a newer version or add packages. The required Python 3.12 dependencies are installed.
