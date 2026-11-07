# Root integration review

PR748 now targets main after Article746 merged as2d251acdf. Native harness could not edit the PR base, so root performed that normal metadata action. This coherent correction push starts ordinary main-targeted checks; no force push or policy bypass.

Root compared all10 source files in the standard manifest: native executed6cf37cb7d and merge447909e73 are byte-identical. AST inspection finds no duplicate top-level definitions in the mutation/verifier modules. No new runtime behavior or browser/model replay is claimed.

The manifest originally called447 the executed source despite explicitly recording no rerun. Corrected executed_source to actual native6cf; runtime_source447 is the equivalent integrated candidate. Original root33-control log belongs to3801b0da5/runtimeec0a98dc2, separately retained. All original logs remain byte-identical. Exact source equality supports reuse of the native6cf controls, not a fabricated run on447.

Raw URL-only and provider-transform content remain unverified. Strict image sub-contract only; no live provider/CDN/model or general image-ingestion qualification.
