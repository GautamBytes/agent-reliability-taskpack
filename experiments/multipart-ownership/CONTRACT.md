# Transactional streaming upload limits

The before condition is the previous 100-check multipart task. The after condition preserves that complete contract and adds the public behaviour below. Both start from the same pinned Werkzeug source. No requirement depends on how a repair names helpers or splits internal Data events.

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

## Scope and proof

This is a local extension of the previous repair task. Real upstream resource-lifecycle work is credited to Werkzeug PR #3101. The quota API and stricter partial-write/cleanup contract are authored for this task and are not claimed to be accepted upstream features.

No timing threshold, desired agent failure rate or reduced solve budget is part of correctness. The reference, a structurally different valid implementation, original baseline and incomplete fixes must be checked before the counted study is frozen.
