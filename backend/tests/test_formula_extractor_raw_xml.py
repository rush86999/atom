"""Raw-XML formula extraction fallback for workbooks openpyxl cannot open.

Regression context (2026-09-03): Zoho Sheet exports (e.g. Consolidated Price
List 2019.xlsx) hard-fail openpyxl's strict reader, so formula memory never
saw their pricing logic even though the formulas are plain well-formed XML.
"""

import io
import zipfile

import pytest

from core.formula_extractor import FormulaExtractor


def _build_hostile_xlsx() -> bytes:
    """Minimal xlsx whose sharedStrings trips openpyxl's read_strings
    (phonetic <rPh> with non-numeric sb/eb), with a header row and a
    formula cell on row 2."""
    ct = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    wb = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Pricing" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
        "</Relationships>"
    )
    sst = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1" uniqueCount="1">'
        "<si><rPh sb=\"x\" eb=\"y\"><t>ph</t></rPh><t>Total Price</t></si>"
        "</sst>"
    )
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        '<row r="1"><c r="C1" t="s"><v>0</v></c></row>'
        '<row r="2"><c r="A2"><v>42</v></c><c r="B2"><v>1.25</v></c>'
        '<c r="C2"><f>A2*B2</f><v>52.5</v></c></row>'
        "</sheetData></worksheet>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/sharedStrings.xml", sst)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


@pytest.fixture
def hostile_workbook(tmp_path):
    path = tmp_path / "hostile.xlsx"
    path.write_bytes(_build_hostile_xlsx())
    return str(path)


def test_extract_from_excel_survives_openpyxl_hostile_workbook(hostile_workbook):
    extractor = FormulaExtractor()
    formulas = extractor.extract_from_excel(hostile_workbook, auto_store=False)
    assert formulas, "raw-XML fallback must extract formulas openpyxl cannot"
    top = formulas[0]
    assert top["original_formula"] == "=A2*B2"
    assert top["name"] == "Total Price"
    assert top["source_sheet"] == "Pricing"


def test_dedupes_identical_name_expression_pairs(hostile_workbook, tmp_path):
    import zipfile

    # duplicate the formula row ten times over (like a price-book column)
    path = tmp_path / "dupes.xlsx"
    content = _build_hostile_xlsx()
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content)) as zin, zipfile.ZipFile(
        buf, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                data = data.replace(
                    b"</sheetData>",
                    b"<row r=\"3\"><c r=\"C3\"><f>A3*B3</f><v>52.5</v></c></row>"
                    b"<row r=\"4\"><c r=\"C4\"><f>A4*B4</f><v>52.5</v></c></row>"
                    b"</sheetData>",
                )
            zout.writestr(item, data)
    path.write_bytes(buf.getvalue())
    formulas = FormulaExtractor().extract_from_excel(str(path), auto_store=False)
    exprs = [(f["name"], f["original_formula"]) for f in formulas]
    assert len(exprs) == len(set(exprs)), "identical pairs must dedupe"
