# Token-counter flag correction

Root independent frozen192 probe failed: `count_tokens` returns `(count, estimated)`, but the estimator treated the flag as exact. Its heuristic branch sent265 input tokens to pricing for2000UTF8bytes. This was a failure to apply the claimed fallback bound; no live token usage or overspend was measured.

Frozen4559 correction always retains the UTF8 byte bound for supported byte-aligned text and schema, regardless of a generic tokenizer flag. Permanent atomic tests cover both flags; independent combined gate135 passed. Original negative bytes and repeatable probe are retained here. Existing numeric/free-price and unknown-liability controls remain.

This does not qualify streaming/gateway physical retries or arbitrary image/provider preprocessing bounds. Those are a separate active worker slice. Fresh all13 exact-head CI and independent merge review remain mandatory.
