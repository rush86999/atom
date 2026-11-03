# Extraction identity contract — source 637a6e178

One shared producer/consumer identity contract for document.text:

- automated extractions are versioned `ev<extractor>:<digest>` hashes of
  extracted text;
- the current extractor version is `ev4`;
- indexed metadata, the authoritative document row and the binding must carry
  the same versioned revision and digest;
- older `ev3` or malformed versions refuse; prefixes are never stripped to
  promote legacy evidence;
- bare manual-upload revisions remain supported only as exact opaque matches;
- result/verification carries the exact authoritative revision while
  extraction lineage retains the raw indexed label, extractor version,
  source revision and separate extracted-text digest.

No model inference or live provider was used.
