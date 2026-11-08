# Exact algorithm-qualified evidence digests

Executed source: `c90dd03ed` (full commit in MANIFEST).

The existing Git evidence verifier accepts both legacy bare SHA-256 and explicit `sha256:<64 lowercase hexadecimal characters>` values. It always compares all 256 bits against the selected immutable Git blob. No truncated digest, unknown algorithm, malformed encoding, wrong material, non-string value, workspace file substitution or changed-reference shortcut is accepted.

Pattern: [OCI descriptor digests](https://github.com/opencontainers/image-spec/blob/main/descriptor.md#digests). This is notation support in the existing verifier, not a new evidence engine. Legacy manifests and strict unlisted-file checks retain their contract.

Verification: 23 controls passed on each Python3.14 and3.11, using scratch Git repositories and explicit scratch DB/data paths. The controls exercise real Git committed/index refs, mixed old/new notation, complete bytes, wrong algorithms/encodings/material and concurrent HEAD movement. No model/browser/provider or deployment operation.

Document runtime evidence remains attributed to executed28e193690 in the companion packet; all its retained log/spec/exit/helper bytes are unchanged from the original packet at ab20d7769. The document API runtime/probe files match the previously tested bytes. PR768 and incident39818286 remain preserved, with no history rewrite or scanner waiver. A clean successor must independently pass all hosted checks before acceptance.
