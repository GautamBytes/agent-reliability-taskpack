# Repair streaming uploads with quotas and transactional resource ownership

An upload service sees corrupted files and incomplete forms. Some files lose CR near a 64KiB read boundary. Other payloads gain bytes, or end early, when a boundary-like string is split between network reads. Repair the pinned Werkzeug repository at `/app/repo`.

## Required behaviour

1. Preserve the exact final bytes and metadata of fields and files through `MultipartDecoder`, `FormDataParser` and `Request`. CR, LF, CRLF, NUL and other binary bytes may be genuine payload. Keep repeated field names, part order, empty fields and empty files. Boundary tokens can contain valid characters that also have meaning in regular expressions.
2. Results must be independent of read fragmentation. A split may occur at any byte in a header, separator line break, opening or intermediate delimiter, padding or closing delimiter. One-byte input reads are valid. For the added fragmentation cases, `Data` events may be split differently provided concatenated bytes and part completion match. The selected original tests remain required, including their legacy complete-buffer event expectations.
3. Handle delimiter lines with optional transport padding. For the new CRLF grammar, an opening or intermediate line is `--BOUNDARY` followed by zero or more ASCII spaces or horizontal tabs and CRLF. A closing line is `--BOUNDARY--`, optional spaces or tabs, then CRLF or the true end of input. Existing selected upstream acceptance of legacy CR-only and LF-only line endings must continue to work.
4. A chunk ending immediately after `--BOUNDARY--`, or its padding, is still ambiguous while more input may arrive. Do not accept a bare closing token until the stream is declared complete. A complete line ending can confirm closure earlier. Apparent delimiter strings with invalid trailing characters remain byte-for-byte payload. Examples include `--BOUNDARY--X`, `--BOUNDARY--!`, `--BOUNDARY---`, `--BOUNDARY----` and a token followed by padding then `X`. A later valid delimiter must still be recognized.
5. Preserve streaming progress. Large ordinary payloads must produce `Data` before EOF rather than buffering the whole upload. Retaining a suffix that could become an incomplete delimiter is valid. Preserve strict rejection when no valid closing delimiter exists, existing memory limits and part-count limits.
6. Keep existing public calls compatible while adding the optional quota settings below. Preserve other selected multipart/form-parser behaviour. This is a bounded parser repair contract, not a request to implement every MIME feature or all RFC compliance. No additional runtime dependency is needed.

## Caller contract

Add optional keyword-only `max_file_size=None` and `max_form_data_size=None` to `parse_form_data`, `FormDataParser` and `MultiPartParser`. Add Request attributes with the same names and defaults. `Request.make_form_data_parser` forwards both settings. Existing call signatures and defaults continue to work.

Each setting accepts None or a nonnegative integer, excluding bool. Invalid values raise ValueError when constructing a parser or calling the convenience function, even if silent=True. A Request with invalid settings raises ValueError when constructing its form parser. These new settings affect multipart input only.

`max_file_size` counts actual payload bytes independently for each file. `max_form_data_size` counts actual payload bytes across all fields and files in the current parse. Headers, delimiters, transport padding and epilogue do not count. Count bytes before text decoding. Repeated names count separately. Ignore missing, false, negative or oversized per-part Content-Length for these counters. Limits are inclusive. Zero permits empty payloads. None disables that limit. Every parse starts fresh counters, including reuse after failure.

Before forwarding each Data event to a file sink or accumulating a field, reject an event that would exceed either applicable limit with RequestEntityTooLarge. Do not forward bytes beyond a limit. There is no requirement to write the permitted prefix of a rejected event. Keep existing memory, part-count and total-request limits. RequestEntityTooLarge must propagate even with silent=True.

## Partial writes and ownership

Higher-level multipart parsing must also remain streaming. Process available decoder events before requesting another input chunk. Create a file sink when its File event is recognized, and forward each accepted file Data event before reading more input or moving to a later part. Equivalent observable ordering is valid, with any legal Data chunk sizes. Do not buffer the entire form or defer all sink creation and writes until final success. This applies through MultiPartParser, FormDataParser and Request.

A file sink may return a positive integer smaller than the offered byte count from write. Continue writing the unaccepted suffix until all bytes are accepted. A return value of zero, None, bool, a negative integer, a noninteger or a value larger than the offered suffix raises OSError rather than looping or silently truncating. Empty Data events do not require a write. Blocking binary sinks are in scope. Nonblocking readiness and retry protocols are not.

The parser owns each stream successfully returned by its stream_factory until the entire multipart parse, including construction of both return collections, succeeds. On success, ownership passes to the caller through FileStorage and the streams remain open. Factory sinks are distinct from the caller's input stream. Never close that borrowed input stream. Short-write rules apply only to file writes, not field-list append.

On any BaseException before success, close every owned sink, including earlier completed files and the active partial file. Failures include input reading, decoder validation, quota checking, later stream creation, writing, seeking and return-collection construction. Make one parser-initiated cleanup call for every unique sink identity even if a close raises. A callback may itself close a stream. Its calls are not counted as parser-initiated cleanup. Cleanup errors must not replace the original exception object. A factory call that raises before returning a sink does not transfer that sink to the parser. Preserve FormDataParser's existing silent ValueError fallback after cleanup.

Request.close closes all cached files, including repeated field names. It does not trigger lazy parsing. Close each unique underlying stream identity once per call and attempt the rest if a close raises an ordinary Exception. To match FileStorage.close, suppress those ordinary exceptions. No extra BaseException handling is required for Request.close itself. Do not close the input stream. Calling Request.close repeatedly on already closed ordinary streams remains safe. No new behaviour is required for application overrides of FileStorage.close.

## Example configuration

```python
from werkzeug.formparser import FormDataParser, MultiPartParser, parse_form_data
from werkzeug.wrappers import Request

parser = FormDataParser(max_file_size=4, max_form_data_size=6, silent=False)
stream_parser = MultiPartParser(max_file_size=4, max_form_data_size=6)
# A four-byte file plus a two-byte field is within both inclusive limits.
# Five file bytes, or seven total field/file payload bytes, must raise 413.

class UploadRequest(Request):
    max_file_size = 4
    max_form_data_size = 6

# The convenience function exposes the same keyword-only options.
# parse_form_data(environ, max_file_size=4, max_form_data_size=6)
```

The parser must work with custom blocking binary file streams and factories. The caller may reuse a parser object for a later request. Failed parsing must not leak streams or leave counters that affect that next request.

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

## Attribution and scope

The parser repair builds on attributed Werkzeug issues #3065, #3077 and #3088. The resource-cleanup problem is also documented in upstream PR #3101. The two quota options and the explicit partial-write and ownership rules are local task requirements, not claimed accepted upstream features. This task has no wall-clock performance target and asks for no new dependencies.

## Submission

Change production source under `src/werkzeug`. The grader restores that source into a clean trusted checkout and runs public preservation and private behaviour checks in a separate offline environment. Candidate edits to tests, configuration, dependencies or Git metadata do not replace the grader's originals. Do not download a newer version or add packages. The required Python 3.12 dependencies are installed.
