# Reference provenance

The full reference starts from pinned Werkzeug commit `b48878cf16dfca3c89ac58aca47ab1ecfcb71354`. Its multipart decoder includes the previous task's local delimiter scanner, built on the attributed upstream repair family in issues #3065, #3077 and #3088 and PRs #3081 and #3089. Philip Jones and Pallets maintainers retain credit for that upstream work.

The stream-ownership problem is independently documented in [Werkzeug PR #3101](https://github.com/pallets/werkzeug/pull/3101), by David Lord and Pallets maintainers. This reference is a local implementation of the explicitly broader task contract. The new quota API, short-write completion, exception identity protection and Request cleanup rules are not claimed to be that upstream patch or accepted upstream features.

`reference.patch` uses per-parse byte counters and an identity-keyed sink dictionary with rollback on BaseException. `alternative-exitstack.patch` uses ExitStack rollback callbacks and transfers ownership with pop_all after both return collections have been constructed. Both include all three production changes relative to the original baseline. Neither requires one private helper or one Data-event chunking strategy from candidate solutions.

Original source licenses and copyright remain in the vendored repository. No novelty, complete RFC conformance or external benchmark acceptance is claimed.
