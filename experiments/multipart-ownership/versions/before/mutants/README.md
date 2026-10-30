# Hard-version incomplete-fix controls

Every patch applies to the same pinned original baseline. These controls are not complete reference solutions for the hard version.

- `upstream-3081-only.patch` contains the first accepted production repair. It fixes some trailing-data handling while retaining later-reported errors.
- `upstream-3089-only.patch` contains the complete attributed upstream parser change through the second accepted repair. It is a valid reference for the basic version, but misses parts of the hard contract.
- `prior-complete-fix.patch` is the original task pack's full reference, including its local terminal-dash suffix correction. It passes the original task but does not implement the newly explicit ambiguous-closing and padded-delimiter contract.
- `strip-payload-newlines.patch` strips newline bytes from payload. It is a corruption-hiding shortcut and violates exact binary preservation.

The hard reference is a local delimiter-scanner extension. It retains the original licenses and credits upstream fixes separately. It has not been accepted upstream and is not claimed to be novel.
