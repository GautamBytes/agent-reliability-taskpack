# Hard version scope

This version adds byte-preserving fragmented decoding, SP/HTAB delimiter padding, trueEOF closing delimiters and invalid boundary-lookalike preservation. Exact supported behavior is in instruction.md. This is a bounded parser repair contract, not a claim of complete RFC conformance. Selected31 upstream preservation cases remain required;18 obsolete intermediate-fragment expectations are excluded explicitly. No live service, unbounded performance guarantee or new dependency is required. The local reference extension has not been accepted upstream.
