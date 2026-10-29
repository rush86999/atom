"""
Office Automation Service for Atom

Provides core utilities for reading, modifying, and rendering Word (.docx),
Excel (.xlsx), and PowerPoint (.pptx) documents without native Office dependencies.
"""

from core.asyncio_compat import get_event_loop, iscoroutinefunction
import logging
import os
import re
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Third-party imports (lazy loaded / imported defensively)
import openpyxl
import docx
try:
    import pptx
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

try:
    import mammoth
    MAMMOTH_AVAILABLE = True
except ImportError:
    MAMMOTH_AVAILABLE = False

try:
    import xlsx2html
    XLSX2HTML_AVAILABLE = True
except ImportError:
    XLSX2HTML_AVAILABLE = False

logger = logging.getLogger(__name__)


def _run_async_sync(coro):
    """Run an async runtime call from a sync method.

    FastAPI sync routes run in a worker thread (no running loop), but tests
    and tool callers may invoke this from inside one. In that case run the
    coroutine on a private thread's loop instead of raising "already running".
    """
    import asyncio
    import threading

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result = {}
    error = {}

    def _worker():
        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:  # noqa: BLE001 — re-raised in caller
            error["error"] = exc

    thread = threading.Thread(target=_worker)
    thread.start()
    thread.join()
    if "error" in error:
        raise error["error"]
    return result.get("value")


def _validate_office_path(file_path: str) -> str:
    """Contain user-supplied file paths to the configured office directory.

    Office endpoints accept a user-controlled ``file_path``; without containment
    that's arbitrary file read/write (path traversal — reading /etc/passwd or
    overwriting config). Resolve to an absolute path and require it to live
    under ATOM_OFFICE_DIR (default ./data/office). Raises ValueError otherwise.
    """
    if not file_path:
        raise ValueError("file_path is required")
    base = Path(os.getenv("ATOM_OFFICE_DIR", os.path.join("data", "office"))).resolve()
    try:
        resolved = Path(file_path).resolve()
    except (OSError, ValueError) as e:
        raise ValueError("Invalid file path")
    # Resolve symlinks/relative escapes: the resolved path must be under base.
    if base not in resolved.parents and resolved != base:
        raise ValueError(
            f"Access denied: path '{file_path}' is outside the allowed office directory"
        )
    return str(resolved)




def _parse_markdown_table(lines, start):
    """Parse one contiguous GitHub-style table starting at ``lines[start]``.

    Returns ``(rows, next_index)`` or ``(None, start)``. Separator rows are
    dropped; the header row is retained.
    """
    import re as _re
    if start + 1 >= len(lines):
        return None, start
    if "|" not in lines[start] or not _re.match(
            r"^\s*\|?\s*:?-{2,}", lines[start + 1] or ""):
        return None, start
    rows = []
    idx = start
    while idx < len(lines):
        line = lines[idx]
        if "|" not in line or not line.strip():
            break
        if idx == start + 1 and _re.match(r"^\s*\|?\s*:?-{2,}", line):
            idx += 1
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
        idx += 1
    return (rows if len(rows) >= 2 else None), idx


def _markdown_blocks(markdown: str):
    """Yield (kind, payload) blocks: heading, paragraph, bullets, table."""
    lines = str(markdown or "").replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        rows, nxt = _parse_markdown_table(lines, i)
        if rows:
            yield "table", rows
            i = nxt
            continue
        if stripped.startswith("#"):
            level = min(len(stripped) - len(stripped.lstrip("#")), 3)
            yield "heading", (level, stripped.lstrip("#").strip())
            i += 1
            continue
        if stripped.startswith(("- ", "* ", "+ ")):
            items = []
            while i < len(lines):
                item = lines[i].strip()
                if item.startswith(("- ", "* ", "+ ")):
                    items.append(item[2:].strip())
                    i += 1
                elif not item and i + 1 < len(lines) and lines[i + 1].strip().startswith(("- ", "* ", "+ ")):
                    i += 1
                else:
                    break
            yield "bullets", items
            continue
        para = [stripped]
        i += 1
        while i < len(lines):
            nxt_line = lines[i].strip()
            if not nxt_line or nxt_line.startswith("#") or nxt_line.startswith(("- ", "* ", "+ ")):
                break
            if _parse_markdown_table(lines, i)[0]:
                break
            para.append(nxt_line)
            i += 1
        yield "paragraph", " ".join(para)


def _extract_sources(markdown: str):
    """Source references explicitly present in the draft (Source: lines or a
    Sources section). They are copied to the artifact, never invented."""
    import re as _re
    found = []
    in_sources = False
    for raw in str(markdown or "").splitlines():
        line = raw.strip()
        if _re.match(r"^#{1,6}\s*sources?\s*$", line, _re.I):
            in_sources = True
            continue
        if in_sources and line.startswith("#"):
            in_sources = False
        match = _re.match(r"^(?:source|sources|reference|references)\s*:\s*(.+)$", line, _re.I)
        if match:
            found.append(match.group(1).strip())
        elif in_sources and line.startswith(("- ", "* ", "+ ")):
            found.append(line[2:].strip())
        elif in_sources and line and not line.startswith("#"):
            found.append(line)
    return [item for item in dict.fromkeys(found) if item]


class ExcelManager:
    """Manages Excel sheet operations using openpyxl."""

    @staticmethod
    def parse_path(path: str) -> Tuple[str, str]:
        """
        Parses a DOM-like path.
        Example: '/Sheet1/A1:B10' -> ('Sheet1', 'A1:B10')
                 '/Sheet1/A1' -> ('Sheet1', 'A1')
                 'A1' -> ('', 'A1')
        """
        path = path.strip()
        if path.startswith('/'):
            parts = [p for p in path.split('/') if p]
            if len(parts) >= 2:
                return parts[0], '/'.join(parts[1:])
            elif len(parts) == 1:
                return parts[0], ""
        return "", path

    def read_range(self, file_path: str, cell_path: str) -> Dict[str, Any]:
        """Read values from a cell or cell range."""
        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found"}

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheet_name, coordinate = self.parse_path(cell_path)

            if sheet_name and sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
            else:
                ws = wb.active
                sheet_name = ws.title

            if not coordinate:
                # Return sheet overview (including EVERY sheet's used
                # rectangle) so the canvas hydrates the full workbook instead
                # of truncating at a hardcoded A1:Z500 window.
                return {
                    "success": True,
                    "sheet_name": sheet_name,
                    "dimensions": ws.dimensions,
                    "sheet_names": wb.sheetnames,
                    "sheets": [
                        {
                            "name": sheet.title,
                            "dimensions": sheet.dimensions,
                            "max_row": sheet.max_row,
                            "max_column": sheet.max_column,
                        }
                        for sheet in wb.worksheets
                    ],
                }

            # Check if it's a range or a single cell
            if ":" in coordinate:
                cells_range = ws[coordinate]
                data = []
                for row in cells_range:
                    row_data = []
                    for cell in row:
                        row_data.append({
                            "cell_ref": cell.coordinate,
                            "value": cell.value,
                            "cell_type": "formula" if cell.value and str(cell.value).startswith('=') else "text"
                        })
                    data.append(row_data)
                # data_only=True strips formulas — read raw so range consumers
                # (the canvas hydration path) get the Sheet→coord→'=...'' map
                # the formula bar renders, same shape as the WS snapshot.
                raw_wb = openpyxl.load_workbook(file_path, data_only=False)
                raw_ws = raw_wb[sheet_name] if sheet_name in raw_wb.sheetnames else raw_wb.active
                formulas: Dict[str, str] = {}
                computed = {
                    cell.get("cell_ref"): cell.get("value")
                    for row in data for cell in row
                    if isinstance(cell, dict)
                }
                for raw_row in raw_ws[coordinate]:
                    for raw_cell in raw_row:
                        if isinstance(raw_cell.value, str) and raw_cell.value.startswith('='):
                            formulas[raw_cell.coordinate] = raw_cell.value
                # A formula with no cached value is NOT a blank cell: the
                # engine did not support/evaluate it. Name it explicitly.
                formula_gaps = [
                    coord for coord in formulas
                    if computed.get(coord) is None
                ]
                return {
                    "success": True,
                    "sheet_name": sheet_name,
                    "coordinate": coordinate,
                    "cells": data,
                    "formulas": formulas,
                    "formula_gaps": formula_gaps,
                    "sheet_names": wb.sheetnames
                }
            else:
                cell = ws[coordinate]
                raw_wb = openpyxl.load_workbook(file_path, data_only=False)
                raw_ws = raw_wb[sheet_name] if sheet_name in raw_wb.sheetnames else raw_wb.active
                raw_cell = raw_ws[coordinate]
                
                is_formula = str(raw_cell.value).startswith('=') if raw_cell.value else False
                formula = str(raw_cell.value) if is_formula else None

                return {
                    "success": True,
                    "sheet_name": sheet_name,
                    "coordinate": coordinate,
                    "value": cell.value,
                    "formula": formula,
                    "cached_value_missing": bool(is_formula and cell.value is None),
                    "cell_type": "formula" if is_formula else "text"
                }
        except Exception as e:
            logger.error(f"Error reading Excel range: {e}")
            return {"success": False, "error": "Failed to read Excel range"}

    def create_spreadsheet(self, file_path: str, rows: List[List[Any]]) -> Dict[str, Any]:
        """Create a new .xlsx from row data (chat-table drafts → office
        canvas). One workbook open/save, unlike per-cell write_cell.
        Numeric-looking strings become real numbers so Excel formulas and
        sums work instead of tripping over text cells."""
        def coerce(value: Any) -> Any:
            if isinstance(value, str):
                stripped = value.strip()
                if re.fullmatch(r"-?\d+", stripped):
                    return int(stripped)
                if re.fullmatch(r"-?\d*\.\d+", stripped):
                    return float(stripped)
            return value

        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Sheet1"
            for row in rows or []:
                ws.append([coerce(cell) for cell in row])
            os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
            wb.save(file_path)
            return {"success": True, "file_path": file_path, "rows": len(rows or [])}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_cell(self, file_path: str, cell_path: str, value: Any, is_formula: bool = False) -> Dict[str, Any]:
        """Write value or formula to a cell."""
        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        try:
            if os.path.exists(file_path):
                wb = openpyxl.load_workbook(file_path)
            else:
                wb = openpyxl.Workbook()
            sheet_name, coordinate = self.parse_path(cell_path)

            if sheet_name:
                if sheet_name not in wb.sheetnames:
                    wb.create_sheet(title=sheet_name)
                ws = wb[sheet_name]
            else:
                ws = wb.active
                sheet_name = ws.title

            if not coordinate:
                return {"success": False, "error": "Cell coordinate not specified"}

            # Cast value appropriately if not a formula
            if is_formula and not str(value).startswith('='):
                value = f"={value}"
            elif not is_formula:
                # Try to cast to float/int if possible
                if isinstance(value, str):
                    if value.isdigit():
                        value = int(value)
                    else:
                        try:
                            value = float(value)
                        except ValueError:
                            pass

            ws[coordinate] = value
            if not is_formula and isinstance(value, str) and value.startswith("="):
                cell = ws[coordinate]
                cell.data_type = "s"
            wb.save(file_path)

            # Recalculate via the workbook runtime so the agent sees computed
            # results immediately (not stale formula strings). This MUST run
            # for a plain value edit too: editing A1 is exactly how a dependent
            # =SUM(A1:B1) changes. The old `and is_formula` gate certified the
            # formula string while leaving every dependent stale.
            computed_value = value
            recalculated = False
            recalc_engine = "none"
            recalc_status = "not_applicable"
            formula_gaps: List[str] = []
            formula_cells: List[tuple] = []
            try:
                from core.workbook_runtime import get_workbook_runtime
                runtime = get_workbook_runtime()
                recalc_engine = runtime.engine
                raw_wb = openpyxl.load_workbook(file_path, data_only=False)
                for ws_any in raw_wb.worksheets:
                    for row_any in ws_any.iter_rows():
                        for c in row_any:
                            if isinstance(c.value, str) and c.value.startswith('='):
                                formula_cells.append((ws_any.title, c.coordinate))
                if formula_cells:
                    if not runtime.can_evaluate:
                        recalc_status = "unavailable"
                        formula_gaps = [f"{sheet}!{cell}" for sheet, cell in formula_cells]
                    else:
                        _run_async_sync(runtime.recalculate(file_path))
                        wb2 = openpyxl.load_workbook(file_path, data_only=True)
                        ws2 = wb2[sheet_name] if sheet_name in wb2.sheetnames else wb2.active
                        computed_value = ws2[coordinate].value
                        evaluated = 0
                        for ws_name, cell_ref in formula_cells:
                            calc_ws = wb2[ws_name] if ws_name in wb2.sheetnames else None
                            value_now = calc_ws[cell_ref].value if calc_ws is not None else None
                            if value_now is None:
                                formula_gaps.append(f"{ws_name}!{cell_ref}")
                            else:
                                evaluated += 1
                        recalculated = evaluated == len(formula_cells)
                        recalc_status = "complete" if not formula_gaps else "partial"
                else:
                    recalc_status = "not_applicable"
            except Exception as recalc_err:
                logger.warning(f"Recalc after write failed (non-fatal): {recalc_err}")
                recalc_status = "failed"
                formula_gaps = [f"{sheet}!{cell}" for sheet, cell in formula_cells] or ["<recalc_failed>"]

            return {
                "success": True,
                "sheet_name": sheet_name,
                "coordinate": coordinate,
                "value": computed_value,
                "formula": value if is_formula else None,
                "recalculated": recalculated,
                "recalc_status": recalc_status,
                "recalc_engine": recalc_engine,
                "formula_gaps": formula_gaps,
                "message": f"Updated {sheet_name}!{coordinate} successfully"
            }
        except Exception as e:
            logger.error(f"Error writing Excel cell: {e}")
            return {"success": False, "error": "Failed to write Excel cell"}

    @staticmethod
    async def insert_rows(file_path: str, sheet_name: str, row: int, count: int = 1) -> Dict[str, Any]:
        """Insert rows and recalculate formulas to maintain references."""
        from core.workbook_runtime import get_workbook_runtime
        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}
        runtime = get_workbook_runtime()
        return await runtime.insert_rows(file_path, sheet_name, row, count)

    @staticmethod
    async def insert_columns(file_path: str, sheet_name: str, col: int, count: int = 1) -> Dict[str, Any]:
        """Insert columns and recalculate formulas to maintain references."""
        from core.workbook_runtime import get_workbook_runtime
        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}
        runtime = get_workbook_runtime()
        return await runtime.insert_cols(file_path, sheet_name, col, count)

    @staticmethod
    async def get_evaluated_range(file_path: str, cell_path: str) -> Dict[str, Any]:
        """Read a range with freshly evaluated formula results."""
        from core.workbook_runtime import get_workbook_runtime
        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}
        runtime = get_workbook_runtime()
        sheet_name, cell_range = ExcelManager.parse_path(cell_path)
        parts = cell_range.split(":") if ":" in cell_range else [cell_range]
        start = parts[0] if parts else "A1"
        end = parts[1] if len(parts) > 1 else None
        return await runtime.get_evaluated_range(file_path, sheet_name, start, end)

    @staticmethod
    async def recalculate(file_path: str) -> Dict[str, Any]:
        """Force recalculation of all formulas in the workbook."""
        from core.workbook_runtime import get_workbook_runtime
        from pathlib import Path
        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}
        runtime = get_workbook_runtime()
        await runtime.recalculate(Path(file_path))
        return {"success": True, "engine": runtime.engine}

    @staticmethod
    async def add_pivot_table(
        file_path: str, sheet_name: str, pivot_sheet_name: str,
        data_range: str, rows: List[str], columns: List[str],
        values: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Create a styled pivot table summary sheet."""
        from core.workbook_runtime import get_workbook_runtime
        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}
        runtime = get_workbook_runtime()
        return await runtime.add_pivot_table(
            file_path, sheet_name, pivot_sheet_name, data_range, rows, columns, values
        )

    @staticmethod
    async def run_excel_macro(file_path: str, macro_name: str) -> Dict[str, Any]:
        """Run macro inside workbook via sandboxed execution."""
        from core.workbook_runtime import get_workbook_runtime
        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}
        runtime = get_workbook_runtime()
        return await runtime.run_macro(file_path, macro_name)


class WordManager:
    """Manages Word document operations using python-docx."""

    def read_document(self, file_path: str) -> Dict[str, Any]:
        """Read content from a Word document."""
        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}

        try:
            doc = docx.Document(file_path)
            paragraphs = []
            for i, p in enumerate(doc.paragraphs):
                if p.text.strip():
                    paragraphs.append({
                        "index": i,
                        "text": p.text,
                        "style": p.style.name
                    })

            tables = []
            for t_idx, table in enumerate(doc.tables):
                table_data = []
                for row in table.rows:
                    row_data = [cell.text.strip() for cell in row.cells]
                    table_data.append(row_data)
                tables.append({
                    "index": t_idx,
                    "rows": table_data
                })

            return {
                "success": True,
                "paragraphs": paragraphs,
                "tables": tables,
                "metadata": {
                    "paragraphs_count": len(doc.paragraphs),
                    "tables_count": len(doc.tables)
                }
            }
        except Exception as e:
            logger.error(f"Error reading Word document: {e}")
            return {"success": False, "error": "Failed to read Word document"}


    def create_from_markdown(
        self,
        file_path: str,
        markdown: str,
        title: Optional[str] = None,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a REAL .docx from a markdown draft.

        Headings become Word headings, bullets become list paragraphs, and
        markdown tables become real Word tables (the old generator flattened
        every line into a paragraph, so "requested table" was never a table).
        Source references already present in the draft are carried into the
        document metadata and a Sources section.
        """
        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        try:
            document = docx.Document()
            blocks = list(_markdown_blocks(markdown))
            first_heading = next(
                (payload[1] for kind, payload in blocks if kind == "heading" and payload[1]),
                "",
            )
            if title and str(title).strip().lower() != str(first_heading).strip().lower():
                document.add_heading(str(title), level=0)
            for kind, payload in blocks:
                if kind == "heading":
                    level, text = payload
                    if text:
                        document.add_heading(text, level=level)
                elif kind == "bullets":
                    for item in payload:
                        document.add_paragraph(item, style="List Bullet")
                elif kind == "table":
                    rows = payload
                    cols = max(len(row) for row in rows)
                    table = document.add_table(rows=len(rows), cols=cols)
                    table.style = "Table Grid"
                    for r_idx, row in enumerate(rows):
                        for c_idx in range(cols):
                            cell = table.cell(r_idx, c_idx)
                            cell.text = row[c_idx] if c_idx < len(row) else ""
                            if r_idx == 0:
                                for run in cell.paragraphs[0].runs:
                                    run.bold = True
                else:
                    text = str(payload or "").strip()
                    if text:
                        document.add_paragraph(text)
            source_list = [str(item) for item in (sources or []) if str(item).strip()]
            has_sources_heading = any(
                kind == "heading" and str(payload[1]).strip().lower() in ("source", "sources")
                for kind, payload in blocks
            )
            if source_list and not has_sources_heading:
                document.add_heading("Sources", level=1)
                for item in dict.fromkeys(source_list):
                    document.add_paragraph(item, style="List Bullet")
            props = document.core_properties
            props.title = title or "Atom generated document"
            props.subject = "Generated by Atom"
            # Word's core-property fields are capped at 255 characters. Long
            # multi-source provenance used to fail document.save() outright.
            props.comments = (
                "Grounded artifact; sources: "
                + ("; ".join(source_list) or "none recorded")
            )[:255]
            props.author = "Atom"
            os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
            document.save(file_path)
            return {
                "success": True,
                "file_path": file_path,
                "format": "docx",
                "tables": sum(1 for kind, _ in _markdown_blocks(markdown) if kind == "table"),
                "sources": source_list,
                "size_bytes": os.path.getsize(file_path),
            }
        except Exception as e:
            logger.error(f"Error creating Word document: {e}")
            return {"success": False, "error": "Failed to create Word document"}

    def modify_document(self, file_path: str, action: str, content: str, options: dict = None) -> Dict[str, Any]:
        """Modify a Word document."""
        options = options or {}
        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        try:
            doc = docx.Document(file_path) if os.path.exists(file_path) else docx.Document()

            if action == "append":
                style = options.get("style", "Normal")
                doc.add_paragraph(content, style=style)
            elif action == "replace":
                target = options.get("target")
                if not target:
                    return {"success": False, "error": "Replace action requires a target placeholder"}
                
                replaced_count = 0
                for p in doc.paragraphs:
                    if target in p.text:
                        p.text = p.text.replace(target, content)
                        replaced_count += 1
                
                # Check tables too
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            if target in cell.text:
                                cell.text = cell.text.replace(target, content)
                                replaced_count += 1
            else:
                return {"success": False, "error": f"Unknown modification action: {action}"}

            doc.save(file_path)
            return {
                "success": True,
                "message": f"Word document modified successfully (Action: {action})"
            }
        except Exception as e:
            logger.error(f"Error modifying Word document: {e}")
            return {"success": False, "error": "Failed to modify Word document"}


class PowerPointManager:
    """Manages PowerPoint slide decks using python-pptx."""

    def read_slides(self, file_path: str) -> Dict[str, Any]:
        """Read content from a PowerPoint deck."""
        if not PPTX_AVAILABLE:
            return {"success": False, "error": "python-pptx library not installed"}
        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}

        try:
            prs = pptx.Presentation(file_path)
            slides = []

            for idx, slide in enumerate(prs.slides):
                shapes = []
                for shape in slide.shapes:
                    if shape.has_table:
                        table_data = []
                        for row in shape.table.rows:
                            row_data = [cell.text for cell in row.cells]
                            table_data.append(row_data)
                        shapes.append({
                            "type": "table",
                            "name": shape.name,
                            "table": table_data
                        })
                    elif shape.has_text_frame and shape.text_frame.text:
                        shapes.append({
                            "type": "text",
                            "name": shape.name,
                            "text": shape.text_frame.text,
                            "is_title": bool(getattr(shape, "is_placeholder", False)
                                             and shape.placeholder_format.idx == 0),
                        })
                notes = ""
                try:
                    if slide.has_notes_slide:
                        notes = slide.notes_slide.notes_text_frame.text or ""
                except Exception:
                    notes = ""
                slides.append({
                    "slide_index": idx,
                    "slide_number": idx + 1,
                    "shapes": shapes,
                    "notes": notes,
                })

            return {
                "success": True,
                "slides": slides,
                "slide_count": len(prs.slides)
            }
        except Exception as e:
            logger.error(f"Error reading PowerPoint: {e}")
            return {"success": False, "error": "Failed to read PowerPoint"}


    def create_from_markdown(
        self,
        file_path: str,
        markdown: str,
        title: Optional[str] = None,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a REAL .pptx from a Slide N: outline.

        Body lines can be bullets, prose, or markdown tables; tables become
        native PowerPoint tables. Speaker notes and source references are
        written to the notes pane so they survive reopen/download. Text boxes
        stay inside the slide bounds and shrink for dense slides (no clipping).
        """
        if not PPTX_AVAILABLE:
            return {"success": False, "error": "python-pptx library not installed"}
        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        try:
            from core.chat_draft_classifier import extract_slide_outline
            from pptx.util import Inches, Pt

            slides_data = extract_slide_outline(markdown)
            if not slides_data:
                return {
                    "success": False,
                    "error": "No `Slide N:` outline found; a presentation was not generated.",
                }
            prs = pptx.Presentation()
            prs.slide_width = Inches(13.333)
            prs.slide_height = Inches(7.5)
            title_layout = prs.slide_layouts[5]  # Title Only (real placeholder)
            source_list = [str(item) for item in (sources or []) if str(item).strip()]

            for deck_slide in slides_data:
                slide = prs.slides.add_slide(title_layout)
                title_shape = slide.shapes.title
                if title_shape is None:
                    title_shape = slide.shapes.add_textbox(
                        Inches(0.55), Inches(0.35), Inches(12.2), Inches(0.9))
                title_shape.left = Inches(0.55)
                title_shape.top = Inches(0.35)
                title_shape.width = Inches(12.2)
                title_shape.height = Inches(0.9)
                title_frame = title_shape.text_frame
                title_frame.word_wrap = True
                title_frame.text = deck_slide.get("title") or "Slide"
                for para in title_frame.paragraphs:
                    for run in para.runs:
                        run.font.size = Pt(28)
                        run.font.bold = True

                body_lines = str(deck_slide.get("content") or "").splitlines()
                notes_lines = []
                kept = []
                for line in body_lines:
                    stripped = line.strip()
                    if stripped.lower().startswith(("notes:", "speaker notes:")):
                        notes_lines.append(stripped.split(":", 1)[1].strip())
                    elif stripped.lower().startswith(("source:", "sources:", "reference:", "references:")):
                        notes_lines.append(stripped)
                    else:
                        kept.append(line)
                table_rows = None
                table_start = 0
                for i in range(len(kept)):
                    rows, nxt = _parse_markdown_table(kept, i)
                    if rows:
                        table_rows = rows
                        table_start = nxt
                        break
                if table_rows:
                    rows_n = len(table_rows)
                    cols_n = max(len(row) for row in table_rows)
                    table_top = Inches(1.45)
                    table_height = Inches(min(0.42 * rows_n, 4.9))
                    shape = slide.shapes.add_table(
                        rows_n, cols_n, Inches(0.55), table_top,
                        Inches(12.2), table_height,
                    )
                    table = shape.table
                    font_size = Pt(12 if rows_n <= 8 else 9)
                    for r_idx, row in enumerate(table_rows):
                        for c_idx in range(cols_n):
                            cell = table.cell(r_idx, c_idx)
                            cell.text = row[c_idx] if c_idx < len(row) else ""
                            for para in cell.text_frame.paragraphs:
                                for run in para.runs:
                                    run.font.size = font_size
                                    if r_idx == 0:
                                        run.font.bold = True
                    remainder = "\n".join(kept[table_start:]).strip()
                    if remainder:
                        below = slide.shapes.add_textbox(
                            Inches(0.55), Inches(1.45 + min(0.42 * rows_n, 4.9) + 0.2),
                            Inches(12.2), Inches(1.4))
                        below.text_frame.word_wrap = True
                        below.text_frame.text = remainder
                        for para in below.text_frame.paragraphs:
                            for run in para.runs:
                                run.font.size = Pt(12)
                else:
                    body = "\n".join(kept).strip()
                    if body:
                        body_box = slide.shapes.add_textbox(
                            Inches(0.55), Inches(1.45), Inches(12.2), Inches(5.55))
                        frame = body_box.text_frame
                        frame.word_wrap = True
                        frame.text = body
                        dense = len([ln for ln in body.splitlines() if ln.strip()]) > 10
                        for para in frame.paragraphs:
                            for run in para.runs:
                                run.font.size = Pt(12 if dense else 16)

                notes_text = "\n".join(
                    item for item in dict.fromkeys(notes_lines + source_list) if item
                )
                if notes_text:
                    try:
                        slide.notes_slide.notes_text_frame.text = notes_text
                    except Exception:
                        pass

            props = prs.core_properties
            props.title = title or "Atom generated presentation"
            props.subject = "Generated by Atom"
            # Same 255-character core-property cap as Word.
            props.comments = (
                "Grounded artifact; sources: "
                + ("; ".join(source_list) or "none recorded")
            )[:255]
            props.author = "Atom"
            os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
            prs.save(file_path)
            return {
                "success": True,
                "file_path": file_path,
                "format": "pptx",
                "slides": len(slides_data),
                "sources": source_list,
                "size_bytes": os.path.getsize(file_path),
            }
        except Exception as e:
            logger.error(f"Error creating PowerPoint: {e}")
            return {"success": False, "error": "Failed to create PowerPoint"}

    def modify_slides(self, file_path: str, action: str, options: dict) -> Dict[str, Any]:
        """Modify slide deck."""
        if not PPTX_AVAILABLE:
            return {"success": False, "error": "python-pptx library not installed"}
        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        try:
            prs = pptx.Presentation(file_path) if os.path.exists(file_path) else pptx.Presentation()

            if action == "add_slide":
                # Standard slide layouts: 0=Title, 1=Title+Content, etc.
                layout_idx = options.get("layout_idx", 1)
                if layout_idx >= len(prs.slide_layouts):
                    layout_idx = 1
                
                blank_layout = prs.slide_layouts[layout_idx]
                slide = prs.slides.add_slide(blank_layout)
                
                title = options.get("title")
                if title and slide.shapes.title:
                    slide.shapes.title.text = title
                
                content = options.get("content")
                if content and len(slide.placeholders) > 1:
                    slide.placeholders[1].text = content
            elif action == "update_slide":
                # Canvas co-editing: update title/body text of an existing slide
                # (1-based slide_number) without touching other slides.
                slide_number = int(options.get("slide_number", 0))
                if slide_number < 1 or slide_number > len(prs.slides):
                    return {"success": False, "error": f"Slide number out of range: {slide_number}"}
                slide = prs.slides[slide_number - 1]

                new_title = options.get("title")
                if new_title is not None and slide.shapes.title is not None:
                    slide.shapes.title.text = str(new_title)

                new_content = options.get("content")
                if new_content is not None:
                    # Exclude the title by stable shape identity. A proxy
                    # identity check (`shape is not title_shape`) can fail in
                    # python-pptx, which made a body edit overwrite the slide
                    # title when the slide had no body placeholder.
                    title_shape = slide.shapes.title
                    title_id = getattr(title_shape, "shape_id", None)
                    target = None
                    for ph in slide.placeholders:
                        try:
                            idx = ph.placeholder_format.idx
                        except Exception:
                            continue
                        if idx == 1 and ph.has_text_frame:
                            target = ph
                            break
                    if target is None:
                        for shape in slide.shapes:
                            if not shape.has_text_frame:
                                continue
                            if title_id is not None and getattr(shape, "shape_id", None) == title_id:
                                continue
                            target = shape
                            break
                    if target is not None:
                        target.text_frame.text = str(new_content)
                    else:
                        # No body shape: create one below the title instead of
                        # mutating an unrelated shape or silently dropping text.
                        from pptx.util import Inches as _Inches
                        box = slide.shapes.add_textbox(
                            _Inches(0.6), _Inches(1.5), _Inches(8.5), _Inches(4.5))
                        box.text_frame.word_wrap = True
                        box.text_frame.text = str(new_content)

            elif action == "set_shape_text":
                # Canvas co-edit: replace the text of an existing shape while
                # preserving the shape itself, its position, and its layout.
                slide_index = options.get("slide_index")
                shape_name = options.get("shape_name")
                text = options.get("text", "")
                if not isinstance(slide_index, int) or slide_index < 0 or slide_index >= len(prs.slides):
                    return {"success": False, "error": f"Invalid slide_index: {slide_index}"}
                if not shape_name:
                    return {"success": False, "error": "shape_name required for set_shape_text"}

                slide = prs.slides[slide_index]
                shape = next((s for s in slide.shapes if s.name == shape_name), None)
                if shape is None or not shape.has_text_frame:
                    return {"success": False, "error": f"Text shape '{shape_name}' not found on slide {slide_index}"}

                # Setting .text replaces all runs with a single run inheriting
                # the paragraph's style — the least destructive simple edit.
                shape.text_frame.text = str(text)
            else:
                return {"success": False, "error": f"Unknown PowerPoint action: {action}"}

            prs.save(file_path)
            return {"success": True, "message": f"PowerPoint modified successfully (Action: {action})"}
        except Exception as e:
            logger.error(f"Error modifying PowerPoint: {e}")
            return {"success": False, "error": "Failed to modify PowerPoint"}


class DocumentRenderer:
    """Renders Word, Excel, and PowerPoint documents to HTML or PNG images."""

    @staticmethod
    def render_to_html(file_path: str) -> Dict[str, Any]:
        """Convert a document into an HTML string for previewing."""
        try:
            file_path = _validate_office_path(file_path)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        ext = Path(file_path).suffix.lower()

        if ext == ".docx":
            if not MAMMOTH_AVAILABLE:
                return {"success": False, "error": "mammoth library not installed"}
            try:
                with open(file_path, "rb") as docx_file:
                    result = mammoth.convert_to_html(docx_file)
                    # Mammoth provides conversion messages
                    return {
                        "success": True,
                        "html": f"<div class='office-word-preview'>{result.value}</div>",
                        "warnings": [m.message for m in result.messages]
                    }
            except Exception as e:
                logger.error(f"Error rendering Word to HTML: {e}")
                return {"success": False, "error": "Failed rendering Word to HTML"}

        elif ext == ".xlsx":
            # Use the workbook runtime for pixel-accurate rendering (LibreOffice
            # when available — includes conditional formatting, charts, and
            # evaluated formulas). Falls back to a basic openpyxl HTML table.
            try:
                from core.workbook_runtime import get_workbook_runtime
                import asyncio as _asyncio
                runtime = get_workbook_runtime()
                try:
                    # `import asyncio as _asyncio` above — this call read
                    # `_get_event_loop()`, a name that never existed, so the
                    # whole xlsx branch died in its own except and EVERY Excel
                    # canvas silently fell back to the basic HTML table (live
                    # stderr, 2026-09-10: "Error rendering Excel to HTML: name
                    # '_get_event_loop' is not defined").
                    loop = _asyncio.get_event_loop()
                    if loop.is_running():
                        # We're in an async context — can't await here directly.
                        # Fall back to basic render (the sync path).
                        html_val = runtime._render_html_basic(Path(file_path))
                    else:
                        html_val = loop.run_until_complete(runtime.render_to_html(file_path))
                except RuntimeError:
                    html_val = runtime._render_html_basic(Path(file_path))
                return {
                    "success": True,
                    "html": f"<div class='office-excel-preview'>{html_val}</div>",
                    "engine": runtime.engine,
                }
            except Exception as e:
                logger.error(f"Error rendering Excel to HTML: {e}")
                return {"success": False, "error": "Failed rendering Excel to HTML"}

        elif ext == ".pptx":
            if not PPTX_AVAILABLE:
                return {"success": False, "error": "python-pptx library not installed"}
            try:
                prs = pptx.Presentation(file_path)
                html_slides = []
                for i, slide in enumerate(prs.slides):
                    texts = []
                    for shape in slide.shapes:
                        if shape.has_text_frame and shape.text_frame.text:
                            texts.append(f"<p>{shape.text_frame.text}</p>")
                    
                    slide_content = "\n".join(texts)
                    html_slides.append(f"""
                        <div class="slide" style="border:1px solid #ccc; padding:20px; margin-bottom:20px; aspect-ratio:16/9; background:#fff; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                            <h3>Slide {i+1}</h3>
                            <div class="slide-content">{slide_content}</div>
                        </div>
                    """)
                return {
                    "success": True,
                    "html": f"<div class='office-pptx-preview' style='background:#f4f4f4; padding:20px;'>{''.join(html_slides)}</div>"
                }
            except Exception as e:
                logger.error(f"Error rendering PPTX to HTML: {e}")
                return {"success": False, "error": "Failed rendering PPTX to HTML"}

        return {"success": False, "error": f"Unsupported format: {ext}"}


class OfficeService:
    """Primary service coordinating Office document manipulation."""

    def __init__(self):
        self.excel = ExcelManager()
        self.word = WordManager()
        self.pptx = PowerPointManager()
        self.renderer = DocumentRenderer()

    def get_manager_for_file(self, file_path: str) -> Any:
        """Get the appropriate manager depending on file suffix."""
        ext = Path(file_path).suffix.lower()
        if ext == ".xlsx":
            return self.excel
        elif ext == ".docx":
            return self.word
        elif ext == ".pptx":
            return self.pptx
        else:
            raise ValueError(f"Unsupported file format: {ext}")
