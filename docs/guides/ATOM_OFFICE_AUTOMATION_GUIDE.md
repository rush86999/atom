# Atom Office Automation & Canvas Co-Editing Guide

Atom provides native, python-based automation and real-time co-editing capabilities for Microsoft Office documents: Word (`.docx`), Excel (`.xlsx`), and PowerPoint (`.pptx`).

No Microsoft Office installation is required. Excel workbooks run through a **formula-evaluating workbook runtime** (`core/workbook_runtime.py`) — LibreOffice headless when available (full recalculation + pixel-accurate rendering + structural edits), the pure-Python `formulas` library as a fallback, and openpyxl cached values as a last resort. Word and PowerPoint remain pure-Python (python-docx / python-pptx).

See [WORKBOOK_RUNTIME.md](../architecture/WORKBOOK_RUNTIME.md) for the Excel engine architecture.

---

## Key Features

1. **AI-Native Manipulation**: Core python libraries edit OpenXML files directly. Excel writes trigger `WorkbookRuntime.recalculate()` so formulas are evaluated and the agent sees computed results immediately.
2. **DOM-like Spreadsheet Paths**: Select and write spreadsheet values or formulas using locator paths like `/SheetName/A1`. Written formulas are re-evaluated and the computed result is returned.
3. **Canvas Co-Editing**: Presents a live, editable document representation, allowing real-time collaboration between the user and the agent. Canvases open in two places: an **embedded panel inside chat** (for office-file co-editing) and a **standalone workspace at `/canvas`** with full CRUD, a side chat panel, and version history. See [Canvas Workspace](#standalone-canvas-workspace) below.
4. **Real-Time Sync**: Modifications made inside the Canvas editor sync instantly back to the filesystem source, and modifications by the agent update the Canvas.
5. **Live Formula Evaluation**: Excel writes trigger recalculation (LibreOffice headless + `formulas` fallback) so agents read computed values, not unevaluated formula strings. HTML render includes conditional formatting and charts.

---

## CLI Reference

Atom OS provides CLI tools under the `office` command group:

### Excel Sheets
- **Read**: `atom-os office excel-read <file_path> [cell_path]`
  - Example: `atom-os office excel-read /data/financials.xlsx /Q1/B5:C12`
- **Write**: `atom-os office excel-write <file_path> <cell_path> <value> [--formula]`
  - Example: `atom-os office excel-write /data/financials.xlsx /Q1/C13 "=SUM(C5:C12)" --formula`

### Word Documents
- **Read**: `atom-os office word-read <file_path>`
- **Write**: `atom-os office word-write <file_path> <content> [--action append|replace] [--target placeholder] [--style Normal]`
  - Example: `atom-os office word-write letter.docx "John Doe" --action replace --target "[Client Name]"`

### PowerPoint Presentations
- **Read**: `atom-os office pptx-read <file_path>`
- **Write**: `atom-os office pptx-write <file_path> <slide_content> [--title "Slide Title"] [--layout-idx 1]`

### Render Previews
- **HTML Render**: `atom-os office render <file_path>`
  - Generates HTML conversion of the document.

---

## API Reference

Endpoints are exposed under the `/api/v1/office` prefix:

- `GET /api/v1/office/excel`: Reads worksheet cells.
- `POST /api/v1/office/excel`: Writes cell value/formula (auto-recalculates and returns computed result).
- `GET /api/v1/office/word`: Reads document paragraphs/tables.
- `POST /api/v1/office/word`: Modifies word file paragraphs or replaces placeholders.
- `GET /api/v1/office/pptx`: Reads presentation shapes and layouts.
- `POST /api/v1/office/pptx`: Appends new slides to presentation.
- `POST /api/v1/office/present`: Opens co-editing canvas panel.
- `POST /api/v1/office/sync-update`: Syncs user edits from Canvas back to filesystem.
- `POST /api/v1/office/excel/recalculate`: Force recalculation of all formulas.
- `POST /api/v1/office/excel/insert-rows`: Insert rows + recalculate to fix references.
- `POST /api/v1/office/excel/insert-columns`: Insert columns + recalculate.
- `GET /api/v1/office/excel/formula-result`: Get computed result of a formula cell.

---

## How It Works: Co-Editing Sync

```mermaid
sequenceDiagram
    User->>Canvas UI: Edits Text / Cell (onBlur)
    Canvas UI->>REST API: POST /api/v1/office/sync-update
    REST API->>OfficeSyncService: sync_canvas_to_file()
    OfficeSyncService->>Filesystem: Write file (docx/xlsx/pptx)
    OfficeSyncService->>OfficeSyncService: Render file to HTML
    OfficeSyncService->>WebSocket: Broadcast 'canvas:update' (rendered HTML)
    WebSocket->>Canvas UI: Refresh preview to match disk
```

---

## Standalone Canvas Workspace

In addition to the in-chat co-editing panel described above, Atom provides a
**dedicated workspace at `/canvas`** where canvases live outside the chat window.
This is the recommended place to browse and manage canvases created during chat
sessions.

### Routes

| Route | Purpose |
|---|---|
| `/canvas` | Lists every canvas for the current user, filterable by type |
| `/canvas/[id]` | Opens a single canvas with a side-chat panel and version history |

### Capabilities

- **Full CRUD** on canvases (read, list, update, delete). New canvases are
  created by agents from chat — the index page explains this and surfaces any
  canvas an agent has presented.
- **Seven canvas types**: `sheets`, `email`, `docs`, `coding`, `terminal`,
  `orchestration`, and `generic` (charts live inside `generic`).
- **Side chat panel** ("Agent Co-Editor") for live co-editing: user messages go
  out over HTTP with the current canvas context injected, and agent edits stream
  back over the `canvas:update` WebSocket event.
- **Version history** via the append-only `CanvasAudit` trail — every
  present / update / delete is recorded and viewable per canvas.
- **AI accessibility on every canvas type** — each open canvas registers its
  state under `window.atom.canvas` so agents can read it back synchronously.

### Relationship to office-file co-editing

The standalone workspace and the office automation flow above are **two separate
but interoperating systems**:

- **Office automation** (`/api/v1/office/...`) is **file-backed**: `/present`
  opens a canvas for a `.docx`/`.xlsx`/`.pptx` on disk and `/sync-update` writes
  edits back to that file. The **file is the source of truth**.
- **Standalone `/canvas` workspace** (`/api/canvas/...`) is **database-backed**:
  the append-only `CanvasAudit` table is the source of truth, with no filesystem
  binding.

Both broadcast the same `canvas:update` WebSocket event on the user channel, so
a canvas presented in chat also appears in the `/canvas` list and can be opened
standalone.
