# Reviewed web Lance SDK dependency repair

- Branch: `codex/ci-reviewed-web-regressions-20261110`
- PR: `817`
- Source before: `36f9a5909ade46e0505bf83a7de3380f717ddd54`
- Repair commit: `ea82333a5826b203b0d38bd7e40237717216f8dd`
- Scope: dependency/install contract only; no browser, model or provider.

## Hosted PR817 failure preserved

The step `Run reviewed web authority and library regression controls` failed
`8 failed, 54 passed in 138.56s` on exact `36f9a5909`.

The explicit error was:

```text
core/lancedb_handler.py:1799: in _ordered_documents_frame
    from lance.dataset import ColumnOrdering
E   ModuleNotFoundError: No module named 'lance'
```

The public API therefore returned the typed
`503 DOCUMENT_LISTING_UNAVAILABLE`; the zero-length control failed with
`DocumentListingUnavailable: native ordered document scan failed: No module
named 'lance'`. The exact root failure log is referenced by SHA-256 in
`ci_failure_reference.json`. No failed check was relabeled, no test was
skipped, and no prefix-sort or vector-materialization fallback was added.

## Why `pylance` is required

- `lancedb==0.24.3` deliberately leaves `pylance` optional. Its installed
  `LanceTable.to_lance()` imports `lance` and otherwise raises:
  `The lance library is required to use this function. Please install with
  pip install pylance.`
- The document-list path also imports `lance.dataset.ColumnOrdering`.
- lancedb issue #1793 records the hard dependency being dropped in favour of
  the optional SDK: <https://github.com/lancedb/lancedb/issues/1793>.
- The Python SDK reference documents `Table.to_lance`:
  <https://lancedb.github.io/lancedb/python/python/>.

A standard backend installation must therefore declare the SDK; a CI-only
install would leave normal installs broken.

## Dependency choice

`backend/requirements.txt` now declares, next to `lancedb==0.24.3`:

```text
pylance==0.39.0
```

Metadata-only verification from PyPI for `pylance 0.39.0`:

- `Requires-Python >=3.9`
- `cp39-abi3` wheels for macOS x86_64/arm64, manylinux 2014/2_17 and
  manylinux_2_28 x86_64/aarch64, and Windows x86_64
- `Requires-Dist: pyarrow>=14`, `numpy>=1.22`, `lance-namespace>=0.0.20`

The accepted local environment is `lancedb 0.24.3`, `pylance 0.39.0`,
`pyarrow 21.0.0`, `numpy 1.26.4`, `lance-namespace 0.4.3`. This satisfies the
existing `pyarrow>=14,<26` and numpy<2 constraints. No wheel was downloaded
or installed for this repair.

## Regression and controls

Added `test_standard_requirements_include_the_lance_sdk_scanner` to the
already-selected document pagination suite. It verifies the normal
requirements declare the SDK and that the installed environment exposes
`LanceTable.to_lance` and `lance.dataset.ColumnOrdering`.

Targeted reviewed web controls:

```text
pytest tests/api/test_web_canvas_authority.py \
       tests/api/test_web_canvas_restore_ordering.py \
       tests/api/test_document_library_pagination.py \
       tests/api/test_web_training_proposal_authority.py
63 passed, exit 0
```

That selection includes the real 130-row global ordering, boundaries, foreign
scope/auth, fresh-handler readback and typed-503 controls. The prior reported
local baseline (62 API + 27 CI-ledger checks) was not regenerated here.

## Limits

- All 13 hosted CI jobs were **not** rerun locally; root must independently
  run exact CI before merge.
- `requirements-py314.txt` remains a separate supplemental set using
  `lancedb==0.38.0`; this repair does not force the 3.14 quickstart.
- No install/download/uninstall, provider/model, browser, credential, spend
  or deployment.
- Root-owned CI YAML and additive ledger were not edited. Only the two files
  in `source_files` changed.
