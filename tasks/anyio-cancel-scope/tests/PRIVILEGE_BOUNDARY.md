The verifier and private pytest parent run as root with candidate import paths and pytest plugin autoload disabled. Private test collection uses only trusted string names. Each journey starts through `private_case_runner.py`, which compiles the protected case source before dropping all supplementary groups and switching to UID/GID 1000. Only then does it add candidate `src` to the import path and execute the journey. The event assertions in `cancellation_cases.py` are unchanged.

Public upstream pytest runs as UID/GID 1000. Its writable JUnit destination is separate from the root-owned private report directory. Candidate processes cannot read the private case source or expected manifest, or rewrite the internal private JUnit report. Public helper files remain readable.

This provides filesystem and process privilege separation for standard behavioral evaluation. It does not make arbitrary malicious Python uncheatable. Candidate code executes in the same interpreter as an individual journey and can counterfeit its internal completion marker.

`python3 -I /tests/check_privilege_boundary.py --output /out/control` runs a local control in the verifier image. It checks the candidate import UID, denied private-file reads and report writes, and failure of all private journeys when imports exit early without a completion marker.
