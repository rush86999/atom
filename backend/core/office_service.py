"""
Office Automation Service for Atom

Provides core utilities for reading, modifying, and rendering Word (.docx),
Excel (.xlsx), and PowerPoint (.pptx) documents without native Office dependencies.
"""

import logging
import os
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
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheet_name, coordinate = self.parse_path(cell_path)

            if sheet_name and sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
            else:
                ws = wb.active
                sheet_name = ws.title

            if not coordinate:
                # Return sheet overview or all cells if range is empty
                return {
                    "success": True,
                    "sheet_name": sheet_name,
                    "dimensions": ws.dimensions,
                    "sheet_names": wb.sheetnames
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
                return {
                    "success": True,
                    "sheet_name": sheet_name,
                    "coordinate": coordinate,
                    "cells": data
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
                    "cell_type": "formula" if is_formula else "text"
                }
        except Exception as e:
            logger.error(f"Error reading Excel range: {e}")
            return {"success": False, "error": str(e)}

    def write_cell(self, file_path: str, cell_path: str, value: Any, is_formula: bool = False) -> Dict[str, Any]:
        """Write value or formula to a cell."""
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
            wb.save(file_path)

            # Recalculate via the workbook runtime so the agent sees computed
            # results immediately (not stale formula strings). Best-effort:
            # a runtime failure doesn't break the write.
            computed_value = value
            try:
                from core.workbook_runtime import get_workbook_runtime
                runtime = get_workbook_runtime()
                if runtime.can_evaluate and is_formula:
                    # Run recalc synchronously (write_cell is a sync method).
                    import asyncio
                    try:
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(runtime.recalculate(file_path))
                        loop.close()
                    except Exception:
                        pass  # Recalc failed — keep the formula as the value.
                    # Read the now-computed value.
                    wb2 = openpyxl.load_workbook(file_path, data_only=True)
                    ws2 = wb2[sheet_name] if sheet_name in wb2.sheetnames else wb2.active
                    computed_value = ws2[coordinate].value
            except Exception as recalc_err:
                logger.debug(f"Recalc after write skipped (non-fatal): {recalc_err}")

            return {
                "success": True,
                "sheet_name": sheet_name,
                "coordinate": coordinate,
                "value": computed_value,
                "formula": value if is_formula else None,
                "message": f"Updated {sheet_name}!{coordinate} successfully"
            }
        except Exception as e:
            logger.error(f"Error writing Excel cell: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def insert_rows(file_path: str, sheet_name: str, row: int, count: int = 1) -> Dict[str, Any]:
        """Insert rows and recalculate formulas to maintain references."""
        from core.workbook_runtime import get_workbook_runtime
        runtime = get_workbook_runtime()
        return await runtime.insert_rows(file_path, sheet_name, row, count)

    @staticmethod
    async def insert_columns(file_path: str, sheet_name: str, col: int, count: int = 1) -> Dict[str, Any]:
        """Insert columns and recalculate formulas to maintain references."""
        from core.workbook_runtime import get_workbook_runtime
        runtime = get_workbook_runtime()
        return await runtime.insert_cols(file_path, sheet_name, col, count)

    @staticmethod
    async def get_evaluated_range(file_path: str, cell_path: str) -> Dict[str, Any]:
        """Read a range with freshly evaluated formula results."""
        from core.workbook_runtime import get_workbook_runtime
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
        runtime = get_workbook_runtime()
        await runtime.recalculate(Path(file_path))
        return {"success": True, "engine": runtime.engine}


class WordManager:
    """Manages Word document operations using python-docx."""

    def read_document(self, file_path: str) -> Dict[str, Any]:
        """Read content from a Word document."""
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

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
            return {"success": False, "error": str(e)}

    def modify_document(self, file_path: str, action: str, content: str, options: dict = None) -> Dict[str, Any]:
        """Modify a Word document."""
        options = options or {}
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
            return {"success": False, "error": str(e)}


class PowerPointManager:
    """Manages PowerPoint slide decks using python-pptx."""

    def read_slides(self, file_path: str) -> Dict[str, Any]:
        """Read content from a PowerPoint deck."""
        if not PPTX_AVAILABLE:
            return {"success": False, "error": "python-pptx library not installed"}
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        try:
            prs = pptx.Presentation(file_path)
            slides = []

            for idx, slide in enumerate(prs.slides):
                shapes = []
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        shapes.append({
                            "type": "text",
                            "name": shape.name,
                            "text": shape.text_frame.text
                        })
                    elif shape.has_table:
                        table_data = []
                        for row in shape.table.rows:
                            row_data = [cell.text for cell in row.cells]
                            table_data.append(row_data)
                        shapes.append({
                            "type": "table",
                            "name": shape.name,
                            "table": table_data
                        })

                slides.append({
                    "slide_index": idx,
                    "shapes": shapes
                })

            return {
                "success": True,
                "slides": slides,
                "slide_count": len(prs.slides)
            }
        except Exception as e:
            logger.error(f"Error reading PowerPoint: {e}")
            return {"success": False, "error": str(e)}

    def modify_slides(self, file_path: str, action: str, options: dict) -> Dict[str, Any]:
        """Modify slide deck."""
        if not PPTX_AVAILABLE:
            return {"success": False, "error": "python-pptx library not installed"}

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
            else:
                return {"success": False, "error": f"Unknown PowerPoint action: {action}"}

            prs.save(file_path)
            return {"success": True, "message": f"PowerPoint modified successfully (Action: {action})"}
        except Exception as e:
            logger.error(f"Error modifying PowerPoint: {e}")
            return {"success": False, "error": str(e)}


class DocumentRenderer:
    """Renders Word, Excel, and PowerPoint documents to HTML or PNG images."""

    @staticmethod
    def render_to_html(file_path: str) -> Dict[str, Any]:
        """Convert a document into an HTML string for previewing."""
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
                return {"success": False, "error": f"Failed rendering Word to HTML: {str(e)}"}

        elif ext == ".xlsx":
            # Use the workbook runtime for pixel-accurate rendering (LibreOffice
            # when available — includes conditional formatting, charts, and
            # evaluated formulas). Falls back to a basic openpyxl HTML table.
            try:
                from core.workbook_runtime import get_workbook_runtime
                import asyncio as _asyncio
                runtime = get_workbook_runtime()
                try:
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
                return {"success": False, "error": f"Failed rendering Excel to HTML: {str(e)}"}

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
                return {"success": False, "error": f"Failed rendering PPTX to HTML: {str(e)}"}

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
