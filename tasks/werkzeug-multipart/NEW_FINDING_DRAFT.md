# Draft upstream report, not submitted

## Multipart closing-delimiter fragmentation can add a CR to file data

I reproduced a byte-preservation problem on the immutable upstream snapshot `45444750e693d3cdff977482904bb15ce37a0768`. I first found it while extending regression tests for the older fixes in PRs 3081 and 3089. This is a local finding. No upstream issue, acceptance, security severity or disclosure outcome is claimed.

A two-chunk message that ends its first chunk with `\r\n--boundary-` can cause the decoder to emit the preceding CR as payload. Completing the next chunk with the second terminal dash then closes the part, leaving an extra CR in the reconstructed body. The same effect appears through `Request` with one- or two-byte WSGI reads.

The parser retains enough suffix for `CRLF + -- + boundary`, but an incomplete closing delimiter may also contain one of its two terminal dashes. Extending the conservative retention length to include those dashes fixes the tested cases without changing the public event API.

```python
from werkzeug.sansio.multipart import Data, Epilogue, MultipartDecoder, NeedData

decoder = MultipartDecoder(b"boundary")
header = b'--boundary\r\nContent-Disposition: form-data; name="f"; filename="f.bin"\r\n\r\n'
emitted = b""
for chunk in (header + b"\r\n--boundary-", b"-\r\n", None):
    decoder.receive_data(chunk)
    while True:
        event = decoder.next_event()
        if isinstance(event, (NeedData, Epilogue)):
            break
        if isinstance(event, Data):
            emitted += event.data
print(repr(emitted))
```

The empty file should not emit content. The pinned upstream snapshot emits `b'\r'`. The task's local reference emits `b''`. Private tests also cover all split positions for small binary fixtures, genuine trailing newlines, mixed parts and real request parsing.

The preservation check excludes one historical parameterized test that asserted a buggy intermediate fragment. It retains 31 other original multipart/form-parser cases. The authored verifier runs 34 additional parameterized checks. Individual checks may exercise many partition arrangements; those arrangements are not reported as independent scenarios.
