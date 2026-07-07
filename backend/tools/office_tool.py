"""
Office Document Automation Tools

Exposes agent-native tools for reading, writing, and rendering Office documents.
These tools are auto-discovered by the Atom Tool Registry.
"""

import logging
from typing import Any, Dict, Optional
from core.office_service import OfficeService
from core.office_sync_service import OfficeSyncService

logger = logging.getLogger(__name__)
office_service = OfficeService()


async def read_excel_cell(
    user_id: str,
    file_path: str,
    cell_path: str = ""
) -> Dict[str, Any]:
    """
    Read value or formula from an Excel spreadsheet cell/range.

    Args:
        user_id: User requesting the action
        file_path: Absolute path to the Excel file
        cell_path: DOM-like path to cell(s), e.g. '/Sheet1/A1' or '/Sheet1/A1:B10'
    """
    try:
        res = office_service.excel.read_range(file_path, cell_path)
        return res
    except Exception as e:
        logger.error(f"Excel read tool failed: {e}")
        return {"success": False, "error": str(e)}


async def write_excel_cell(
    user_id: str,
    file_path: str,
    cell_path: str,
    value: Any,
    is_formula: bool = False
) -> Dict[str, Any]:
    """
    Write value or formula to an Excel spreadsheet cell.

    Args:
        user_id: User requesting the action
        file_path: Absolute path to the Excel file
        cell_path: Coordinate path, e.g. '/Sheet1/A1'
        value: Value or formula string (e.g. '=SUM(A1:A5)')
        is_formula: Boolean flag if the value is an Excel formula
    """
    try:
        res = office_service.excel.write_cell(
            file_path=file_path,
            cell_path=cell_path,
            value=value,
            is_formula=is_formula
        )
        return res
    except Exception as e:
        logger.error(f"Excel write tool failed: {e}")
        return {"success": False, "error": str(e)}


async def read_word_document(
    user_id: str,
    file_path: str
) -> Dict[str, Any]:
    """
    Read paragraphs and tables from a Word (.docx) document.

    Args:
        user_id: User requesting the action
        file_path: Absolute path to the Word document
    """
    try:
        res = office_service.word.read_document(file_path)
        return res
    except Exception as e:
        logger.error(f"Word read tool failed: {e}")
        return {"success": False, "error": str(e)}


async def modify_word_document(
    user_id: str,
    file_path: str,
    action: str,
    content: str,
    target: Optional[str] = None,
    style: str = "Normal"
) -> Dict[str, Any]:
    """
    Modify or overwrite paragraphs/placeholders in a Word document.

    Args:
        user_id: User requesting the action
        file_path: Absolute path to the Word document
        action: Change action ('append' or 'replace')
        content: Text content to write or insert
        target: Placeholder target text to replace (required if action='replace')
        style: Optional paragraph style name
    """
    try:
        options = {"style": style, "target": target}
        res = office_service.word.modify_document(
            file_path=file_path,
            action=action,
            content=content,
            options=options
        )
        return res
    except Exception as e:
        logger.error(f"Word modify tool failed: {e}")
        return {"success": False, "error": str(e)}


async def read_pptx_slides(
    user_id: str,
    file_path: str
) -> Dict[str, Any]:
    """
    Read layouts and text shape data from a PowerPoint slide deck.

    Args:
        user_id: User requesting the action
        file_path: Absolute path to the PowerPoint presentation
    """
    try:
        res = office_service.pptx.read_slides(file_path)
        return res
    except Exception as e:
        logger.error(f"PowerPoint read tool failed: {e}")
        return {"success": False, "error": str(e)}


async def modify_pptx_slides(
    user_id: str,
    file_path: str,
    action: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    layout_idx: int = 1
) -> Dict[str, Any]:
    """
    Modify slides in a PowerPoint presentation.

    Args:
        user_id: User requesting the action
        file_path: Absolute path to the PowerPoint file
        action: Change action ('add_slide')
        title: Optional slide title
        content: Optional slide text box content
        layout_idx: Index of layout template (default: 1 for Title + Content)
    """
    try:
        options = {"title": title, "content": content, "layout_idx": layout_idx}
        res = office_service.pptx.modify_slides(
            file_path=file_path,
            action=action,
            options=options
        )
        return res
    except Exception as e:
        logger.error(f"PowerPoint modify tool failed: {e}")
        return {"success": False, "error": str(e)}


async def present_coedit_canvas(
    user_id: str,
    file_path: str,
    canvas_id: Optional[str] = None,
    title: Optional[str] = None
) -> Dict[str, Any]:
    """
    Open the interactive document co-editing preview panel on the user's Canvas interface.

    Args:
        user_id: User ID to present the Canvas to
        file_path: Path to the target document
        canvas_id: Optional unique ID for the canvas tracking session
        title: Optional custom title for the Canvas panel header
    """
    from core.database import get_db_session
    import uuid

    try:
        canvas_id = canvas_id or f"canvas_{uuid.uuid4().hex[:12]}"
        with get_db_session() as db:
            sync_service = OfficeSyncService(db)
            sync_service.broadcast_file_update(
                canvas_id=canvas_id,
                file_path=file_path,
                user_id=user_id
            )

        return {
            "success": True,
            "canvas_id": canvas_id,
            "message": f"Presented co-editing canvas successfully for: {file_path}"
        }
    except Exception as e:
        logger.error(f"Coedit present tool failed: {e}")
        return {"success": False, "error": str(e)}
