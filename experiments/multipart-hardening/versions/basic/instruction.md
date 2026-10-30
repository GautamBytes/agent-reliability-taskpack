# Repair uploaded file byte loss at the 64KiB read boundary

A service using Werkzeug loses a byte from some uploaded files. A file whose payload ends in CR can return 65,535 bytes after 65,536 bytes were sent. Fix this in the pinned repository at `/app/repo`.

Preserve every uploaded payload byte, including genuine trailing CR, LF and CRLF bytes. The public `Request.from_values` upload path must return the exact submitted file content around the 64KiB buffer boundary. Preserve the package's existing multipart and form-parser behaviour. Do not normalize or strip payload line endings.

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

Work under `src/werkzeug`. The grader overlays only this production source onto a clean copy of the pinned repository. Candidate changes to tests, package configuration and dependencies do not replace trusted files. Python 3.12 and required dependencies are installed. Do not add dependencies or download a newer package.

You may add local tests. The public preservation command is:

```sh
PYTHONPATH=src python -m pytest tests/sansio/test_multipart.py tests/test_formparser.py -q -k 'not test_decoder_data_start_with_different_newline_positions'
```

Eighteen old intermediate-fragment assertions are excluded because they encode a known incorrect split. The selected 31 original cases remain required. This task asks for exact final file content through ordinary uploads. Broader arbitrary-fragment decoder repairs and extended delimiter grammar are outside this basic version's contract.
