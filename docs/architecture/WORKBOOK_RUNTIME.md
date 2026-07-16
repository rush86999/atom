# Workbook Runtime

> **Last Updated**: July 14, 2026
>
> **Status**: Fully implemented and wired. LibreOffice headless when available
> (Docker image installs `libreoffice-calc`); `formulas` library fallback for
> pure-Python evaluation; openpyxl cached-values as last resort.

## The Problem

openpyxl is a file-format library — a parser and serializer. It can write
`=SUM(A1:A10)` into a cell, but it **can't evaluate it**. The formula stays
as a literal string until Excel or LibreOffice opens and recalculates the
file. This means:

- **Agents write formulas blind** — they write `=SUM(A1:A10)` but can't see
  that it evaluates to 60 until the next read (which returns stale/None
  cached values).
- **No structural operations** — inserting a row/column wasn't implemented at
  all. And even if it were, formula references (`A1:A10`) wouldn't update.
- **Rendering is stale** — `xlsx2html` rendered whatever cached values
  openpyxl saw (possibly absent for agent-written files). No conditional
  formatting, no charts, no live evaluation.

The user's critique was precise: *"openpyxl is to an Excel workbook what a
parser is to source code. You need a runtime — something that evaluates the
workbook like Excel would."*

## The Fix

A three-tier workbook runtime (`core/workbook_runtime.py`) that every Excel
write/render/read flows through:

```
Agent writes formula                     Agent reads cell
        │                                       │
        ▼                                       ▼
┌─────────────────┐                  ┌──────────────────┐
│  write_cell()   │                  │ read_range()     │
│  saves to disk  │                  │ (data_only=True) │
└────────┬────────┘                  └────────┬─────────┘
         │                                    │
         ▼                                    │
┌─────────────────────────────────┐           │
│  WorkbookRuntime.recalculate()  │           │
│                                 │           │
│  Tier 1: LibreOffice headless   │           │
│    soffice --calc --convert-to  │           │
│    (evaluates ALL formulas)     │           │
│                                 │           │
│  Tier 2: formulas library       │           │
│    (pure Python, ~80% funcs)    │           │
│                                 │           │
│  Tier 3: openpyxl cached values │           │
│    (stale/None — last resort)   │           │
└────────────────┬────────────────┘           │
                  │                            │
                  ▼                            ▼
         Computed values in the file ──→ Agent sees "60", not "=SUM(A1:A10)"
```

### Tier 1: LibreOffice headless (full runtime)
When `soffice` is on the PATH (the Docker image installs `libreoffice-calc`):
- **Recalculate**: `soffice --headless --calc --convert-to xlsx` — opens the
  workbook in Calc's real engine, evaluates every formula, saves with cached values.
- **Render to HTML**: `soffice --headless --convert-to html` — pixel-accurate
  output with conditional formatting, charts, and evaluated values.
- **Structural edits**: `insert_rows`/`insert_cols` via openpyxl, then recalc
  to fix all formula references.

### Tier 2: `formulas` library (pure Python)
When `soffice` is not installed but `formulas>=1.2.0` is (in requirements.txt):
- Evaluates ~80% of common Excel functions in-process.
- No rendering (falls back to basic openpyxl HTML table).
- Formula references maintained on structural edits via recalc.

### Tier 3: openpyxl (always available, last resort)
- Reads cached values from the file (may be stale or None for agent-written files).
- No evaluation. The previous behavior.

## Architecture

### Write path (with auto-recalc)
`ExcelManager.write_cell()` → saves the formula → calls
`WorkbookRuntime.recalculate()` → reads back with `data_only=True` → returns
both `value` (computed result) and `formula` (the expression string).

### Render path
`DocumentRenderer.render_to_html()` for `.xlsx` → calls
`WorkbookRuntime.render_to_html()` → LibreOffice HTML (pixel-accurate with CF
and charts) or basic openpyxl table fallback.

### Structural operations
`insert_rows`/`insert_columns` → openpyxl shifts cells → `recalculate()` fixes
all formula references automatically.

### Agent tools
- `get_excel_formula_result` — forces recalc, returns computed value
- `insert_excel_rows` / `insert_excel_columns` — structural ops + recalc
- `recalculate_excel` — force full workbook recalculation

### API endpoints
- `POST /api/v1/office/excel/recalculate`
- `POST /api/v1/office/excel/insert-rows`
- `POST /api/v1/office/excel/insert-columns`
- `GET /api/v1/office/excel/formula-result`

## Key files

| File | Role |
|------|------|
| `backend/core/workbook_runtime.py` | The runtime engine (recalc, render, structural ops) |
| `backend/core/office_service.py` | ExcelManager (write_cell with auto-recalc, renderer) |
| `backend/core/office_sync_service.py` | Canvas sync (renders after recalc) |
| `backend/tools/office_tool.py` | Agent-callable tools |
| `backend/api/office_routes.py` | HTTP API endpoints |
| `Dockerfile` | Installs `libreoffice-calc` |

## Limitations (honest)

- **Not 100% Excel-identical rendering**: LibreOffice Calc is very close but
  not pixel-perfect vs. Excel. Some advanced conditional formatting rules or
  chart types may render slightly differently.
- **Chart/table/defined-name mutation**: structural inserts work (references
  are maintained), but programmatically creating or editing charts, pivot
  tables, or defined names is not yet exposed. Recalc maintains existing ones.
- **Recalc latency**: LibreOffice headless takes ~1-3s per recalc. For
  high-frequency cell writes (e.g. bulk import), use batch writes + a single
  recalc at the end rather than per-cell recalc.
- **No real-time collaborative recalc**: the canvas shows a snapshot after
  each recalc, not a live Google-Sheets-style updating view.

## References

- [Office Automation Guide](../guides/ATOM_OFFICE_AUTOMATION_GUIDE.md)
- [Learning LLM Router](LEARNING_LLM_ROUTER.md) — analogous architecture pattern
