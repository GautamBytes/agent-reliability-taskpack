# Hard-version reference attribution

The baseline is the pinned Werkzeug repository named in provenance.json, with the original BSD-3-Clause notice retained. The reference includes the previously attributed multipart repair family from PR3081 and PR3089, plus a local experimental delimiter scanner.

The local scanner distinguishes a complete delimiter from an ambiguous token suffix, retains incomplete prefixes and padding, confirms EOF-only closure only after true completion, and treats invalid closing lookalikes as payload. It preserves the selected original public behaviour. This is not an accepted upstream fix, and no novelty claim is made.

The additional hard contract and private checks are part of the personal task-authoring experiment. Original-source, prior-fix and incomplete-fix controls distinguish the version contracts.
