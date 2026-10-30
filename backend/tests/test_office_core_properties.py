"""Office core-property bounds.

Word/PPTX core properties are capped at 255 characters. A long multi-source
provenance string must be truncated, not fail the artifact write.
"""
from __future__ import annotations

from core.office_service import OfficeService


def test_word_artifact_survives_multi_source_provenance(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    target = tmp_path / "long-sources.docx"
    sources = [
        "Connected workbook: Consolidated Price List 2019.xlsx "
        "(OneDrive item 01P3INOW7U35MJ76UHXZFLQBL4A2WXP5CG, version "
        "2abb1bf40ec31d131e5ae96abb173ac463426ef7); Sheet: US$ SCOTCH PARTS; "
        "Local canvas snapshot: b92aaf07eb1d219b"
    ]
    result = OfficeService().word.create_from_markdown(
        str(target), "# Report\n\nBody text.", title="Report", sources=sources,
    )
    assert result["success"] is True
    assert target.exists() and target.stat().st_size > 0
