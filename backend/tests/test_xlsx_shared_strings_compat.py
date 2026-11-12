# -*- coding: utf-8 -*-
"""Regression: openpyxl rejects well-formed font ``family`` ids > 14.

The synthetic packages below are built entirely in this test. openpyxl 3.1
raises ``ValueError: Max value is 14`` in two independent readers, both before
any worksheet row is read:

* ``xl/sharedStrings.xml`` rich-text ``<rPr><family val="34"/>`` (read as
  ``InlineFont.family``); and
* direct ``xl/styles.xml`` ``<fonts><font><family val="..."/>`` entries (read
  as ``Font.family``) — the observed WorkDrive sequence was a package whose
  shared strings normalised successfully and then still failed in the
  stylesheet.

The shared structured workbook reader must still answer from those bytes while
keeping the original provider digest/byte length/lineage and the formula's
cached value. The compatibility copy is private to the parse; the input bytes
must never be mutated and no global openpyxl patch is installed.
"""
from __future__ import annotations

import hashlib
import io
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest

from core.workbook_read_artifact import (
    inspect_workbook_bytes,
    workbook_artifact_observations,
)
from core.xlsx_openpyxl_compat import (
    SHARED_STRINGS_PART,
    SPREADSHEETML_NAMESPACE,
    STYLES_PART,
    openpyxl_compatible_bytes,
)

FILE_NAME = "Synthetic WorkDrive Price List.xlsx"
RESOURCE_ID = "synthetic-workdrive-file-1"
SHA256 = hashlib.sha256


_SST_NS = f"{{{SPREADSHEETML_NAMESPACE}}}"


def _replace_member(
    package: bytes,
    part_name: str,
    payload: bytes,
    *,
    remove_name: str = "",
) -> bytes:
    """Test-only package rewrite: swap one member's bytes verbatim."""
    removed = remove_name or part_name
    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(package)) as source, zipfile.ZipFile(
        buffer, "w", zipfile.ZIP_DEFLATED,
    ) as target:
        for info in source.infolist():
            if info.filename == removed:
                continue
            target.writestr(info, source.read(info))
        target.writestr(part_name, payload)
    return buffer.getvalue()


def _replace_shared_strings(
    package: bytes,
    shared_strings: bytes,
    *,
    part_name: str = SHARED_STRINGS_PART,
) -> bytes:
    """Test-only package rewrite: swap the sharedStrings part verbatim."""
    return _replace_member(
        package, part_name, shared_strings, remove_name=SHARED_STRINGS_PART)


def _replace_styles(package: bytes, styles: bytes) -> bytes:
    """Test-only package rewrite: swap the styles part verbatim."""
    return _replace_member(package, STYLES_PART, styles)


def _styles_xml(font_families, *, extra: str = "") -> str:
    fonts = "".join(
        '<font><sz val="11"/><name val="Calibri"/>'
        f'<family val="{family}"/></font>'
        for family in font_families
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<fonts count="{len(font_families)}">{fonts}</fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        f"{extra}"
        "</styleSheet>"
    )


def _build_synthetic_xlsx(
    *,
    shared_string_family: int = 34,
    style_families=(2,),
) -> bytes:
    """Minimal OOXML package with the requested font-family defect conditions.

    Rows: header ``Model | List Price``; data ``U-22 | =100*1.1`` with cached
    value ``110``. The model cell is a rich-text shared string split across
    two runs, and the first run's ``rPr`` carries
    ``family val=shared_string_family``. The stylesheet font table carries one
    direct ``font/family`` per entry in ``style_families``.
    """
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Price List" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )
    shared_strings = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'count="3" uniqueCount="3">'
        "<si><t>Model</t></si>"
        "<si>"
        "<r><rPr><b/><sz val=\"11\"/><color theme=\"1\"/>"
        f"<rFont val=\"Calibri\"/><family val=\"{shared_string_family}\"/>"
        "<scheme val=\"minor\"/>"
        "</rPr><t>U-</t></r>"
        "<r><t>22</t></r>"
        "</si>"
        "<si><t>List Price</t></si>"
        "</sst>"
    )
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<dimension ref="A1:B2"/><sheetData>'
        '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>2</v></c></row>'
        '<row r="2"><c r="A2" t="s"><v>1</v></c>'
        '<c r="B2"><f>100*1.1</f><v>110</v></c></row>'
        "</sheetData></worksheet>"
    )
    styles = _styles_xml(style_families)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr(SHARED_STRINGS_PART, shared_strings)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
        archive.writestr("xl/styles.xml", styles)
    return buffer.getvalue()


@pytest.fixture()
def synthetic_xlsx() -> bytes:
    return _build_synthetic_xlsx()


def test_fixture_reproduces_openpyxl_rejection_before_rows(synthetic_xlsx):
    from openpyxl import load_workbook

    # The condition exists in the package itself.
    with zipfile.ZipFile(io.BytesIO(synthetic_xlsx)) as archive:
        assert b'<family val="34"/>' in archive.read(SHARED_STRINGS_PART)

    for read_only in (False, True):
        with pytest.raises(ValueError) as excinfo:
            load_workbook(
                io.BytesIO(synthetic_xlsx),
                read_only=read_only,
                data_only=True,
                rich_text=False,
            )
        message = str(excinfo.value)
        assert "could not read strings" in message or "Max value is 14" in message


def test_compatibility_copy_preserves_values_and_formula_cache(synthetic_xlsx):
    from openpyxl import load_workbook

    compatible = openpyxl_compatible_bytes(synthetic_xlsx)
    assert compatible is not None
    assert compatible != synthetic_xlsx
    # The caller's bytes and the provider's sharedStrings part are untouched.
    assert b'<family val="34"/>' in zipfile.ZipFile(
        io.BytesIO(synthetic_xlsx)).read(SHARED_STRINGS_PART)
    assert b'family val="0"' in zipfile.ZipFile(
        io.BytesIO(compatible)).read(SHARED_STRINGS_PART)

    formulas = load_workbook(
        io.BytesIO(compatible), data_only=False, rich_text=False)
    values = load_workbook(
        io.BytesIO(compatible), data_only=True, rich_text=False)
    assert formulas["Price List"]["A2"].value == "U-22"  # runs concatenated
    assert formulas["Price List"]["B2"].value == "=100*1.1"
    assert values["Price List"]["A2"].value == "U-22"
    assert values["Price List"]["B2"].value == 110  # cached result, untouched


def test_compatibility_copy_is_semantically_namespaced(synthetic_xlsx):
    """Assert namespaces by URI, not by serialized prefix spellings."""
    namespace_map_before = dict(ET._namespace_map)
    compatible = openpyxl_compatible_bytes(synthetic_xlsx)
    assert compatible is not None
    # No process-global namespace registration was installed.
    assert dict(ET._namespace_map) == namespace_map_before

    with zipfile.ZipFile(io.BytesIO(compatible)) as archive:
        part = archive.read(SHARED_STRINGS_PART)
    root = ET.fromstring(part)
    assert root.tag == _SST_NS + "sst"
    assert [child.tag for child in root] == [_SST_NS + "si"] * 3
    rpr = root.find(f".//{_SST_NS}rPr")
    assert rpr is not None
    family = rpr.find(f"{_SST_NS}family")
    assert family is not None
    assert family.get("val") == "0"
    assert [node.text for node in root.iter(_SST_NS + "t")] == [
        "Model", "U-", "22", "List Price",
    ]


def _assert_openpyxl_max_family_error(package: bytes) -> str:
    """The package fails in openpyxl with ``Max value is 14`` somewhere."""
    from openpyxl import load_workbook

    with pytest.raises(ValueError) as excinfo:
        load_workbook(
            io.BytesIO(package), data_only=True, rich_text=False)
    messages = []
    current = excinfo.value
    while current is not None:
        messages.append(str(current))
        current = current.__cause__ or current.__context__
    assert any("Max value is 14" in message for message in messages)
    return messages[0]


def _direct_stylesheet_families(styles: bytes):
    root = ET.fromstring(styles)
    assert root.tag == _SST_NS + "styleSheet"
    fonts = root.find(f"{_SST_NS}fonts")
    assert fonts is not None
    return [
        family.get("val")
        for font in fonts.findall(f"{_SST_NS}font")
        for family in font.findall(f"{_SST_NS}family")
    ]


def test_both_font_defects_in_one_package_are_repaired():
    """The observed package needs sharedStrings AND stylesheet repair."""
    package = _build_synthetic_xlsx(
        shared_string_family=34, style_families=(34, 35, 36))
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        assert b'<family val="34"/>' in archive.read(SHARED_STRINGS_PART)
        assert archive.read(STYLES_PART).count(b'<family val="') == 3
        original_members = {
            info.filename: archive.read(info) for info in archive.infolist()
        }
    _assert_openpyxl_max_family_error(package)

    digest_before = SHA256(package).hexdigest()
    compatible = openpyxl_compatible_bytes(package)
    assert compatible is not None
    assert SHA256(package).hexdigest() == digest_before  # input untouched

    with zipfile.ZipFile(io.BytesIO(compatible)) as archive:
        shared_strings = archive.read(SHARED_STRINGS_PART)
        styles = archive.read(STYLES_PART)
        assert set(archive.namelist()) == set(original_members)
        changed = {
            name
            for name, payload in original_members.items()
            if archive.read(name) != payload
        }
    # Exactly the two font-metadata parts were rebuilt.
    assert changed == {SHARED_STRINGS_PART, STYLES_PART}
    # Serialised prefixes may differ; assert by URI-aware element values.
    assert b'family val="0"' in shared_strings
    assert b'family val="34"' not in shared_strings
    assert _direct_stylesheet_families(styles) == ["0", "0", "0"]

    from openpyxl import load_workbook

    formulas = load_workbook(
        io.BytesIO(compatible), data_only=False, rich_text=False)
    values = load_workbook(
        io.BytesIO(compatible), data_only=True, rich_text=False)
    assert formulas["Price List"]["A2"].value == "U-22"
    assert formulas["Price List"]["B2"].value == "=100*1.1"
    assert values["Price List"]["A2"].value == "U-22"
    assert values["Price List"]["B2"].value == 110  # cached result, untouched


def test_stylesheet_only_recovery_after_shared_strings_would_pass():
    """Exactly the observed sequence: sharedStrings valid, stylesheet fails."""
    package = _build_synthetic_xlsx(
        shared_string_family=2, style_families=(34, 35, 36))
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        original_shared_strings = archive.read(SHARED_STRINGS_PART)
        original_styles = archive.read(STYLES_PART)
    assert original_styles.count(b'<family val="34"/>') == 1
    outer = _assert_openpyxl_max_family_error(package)
    assert "could not read stylesheet" in outer

    digest_before = SHA256(package).hexdigest()
    compatible = openpyxl_compatible_bytes(package)
    assert compatible is not None
    assert SHA256(package).hexdigest() == digest_before

    with zipfile.ZipFile(io.BytesIO(compatible)) as archive:
        # Only the stylesheet member was rebuilt for a stylesheet-only defect.
        assert archive.read(SHARED_STRINGS_PART) == original_shared_strings
        styles = archive.read(STYLES_PART)
    assert _direct_stylesheet_families(styles) == ["0", "0", "0"]

    from openpyxl import load_workbook

    values = load_workbook(
        io.BytesIO(compatible), data_only=True, rich_text=False)
    assert values["Price List"]["A2"].value == "U-22"
    assert values["Price List"]["B2"].value == 110


def test_stylesheet_matching_is_exact_part_root_and_direct_path():
    baseline = _build_synthetic_xlsx(
        shared_string_family=2, style_families=(2,))
    styles_defect = _styles_xml((34, 35, 36)).encode("utf-8")

    # Case-variant part path is not the OOXML styles part.
    wrong_path = _replace_member(baseline, "xl/Styles.xml", styles_defect)
    assert openpyxl_compatible_bytes(wrong_path) is None

    # Same-named root in another namespace is not the stylesheet.
    wrong_root = _styles_xml((34,)).replace(
        SPREADSHEETML_NAMESPACE, "urn:not-ooxml").encode("utf-8")
    assert openpyxl_compatible_bytes(
        _replace_styles(baseline, wrong_root)) is None

    # A direct defect is repaired; dxf/font/family is not on the eligible
    # path and keeps its original value even in the compatibility copy.
    mixed = _styles_xml(
        (34,),
        extra=(
            '<dxfs count="1"><dxf><font><family val="35"/></font></dxf>'
            "</dxfs>"
        ),
    ).encode("utf-8")
    compatible = openpyxl_compatible_bytes(_replace_styles(baseline, mixed))
    assert compatible is not None
    with zipfile.ZipFile(io.BytesIO(compatible)) as archive:
        styles = archive.read(STYLES_PART)
    root = ET.fromstring(styles)
    assert _direct_stylesheet_families(styles) == ["0"]
    dxf_family = root.find(
        f".//{_SST_NS}dxf/{_SST_NS}font/{_SST_NS}family")
    assert dxf_family is not None
    assert dxf_family.get("val") == "35"

    # A family element outside the SpreadsheetML namespace is not eligible.
    foreign_family = (
        f'<styleSheet xmlns="{SPREADSHEETML_NAMESPACE}" '
        'xmlns:x="urn:not-ooxml">'
        "<fonts><font><x:family val=\"34\"/></font></fonts></styleSheet>"
    )
    assert openpyxl_compatible_bytes(_replace_styles(
        baseline, foreign_family.encode("utf-8"))) is None


def test_compatibility_copy_leaves_all_other_members_byte_identical(
    synthetic_xlsx,
):
    digest_before = SHA256(synthetic_xlsx).hexdigest()
    with zipfile.ZipFile(io.BytesIO(synthetic_xlsx)) as source:
        original = {
            info.filename: (
                source.read(info),
                info.date_time,
                info.compress_type,
                info.CRC,
                info.file_size,
                info.external_attr,
            )
            for info in source.infolist()
        }

    compatible = openpyxl_compatible_bytes(synthetic_xlsx)
    assert compatible is not None
    # The caller's input package is never rewritten in place.
    assert SHA256(synthetic_xlsx).hexdigest() == digest_before

    with zipfile.ZipFile(io.BytesIO(compatible)) as copy:
        assert set(copy.namelist()) == set(original)
        changed = []
        for name, (
            payload, date_time, compress_type, crc, file_size, external_attr,
        ) in original.items():
            if copy.read(name) != payload:
                changed.append(name)
            if name == SHARED_STRINGS_PART:
                continue
            member = copy.getinfo(name)
            assert copy.read(name) == payload
            assert member.date_time == date_time
            assert member.compress_type == compress_type
            assert member.CRC == crc
            assert member.file_size == file_size
            assert member.external_attr == external_attr
        assert changed == [SHARED_STRINGS_PART]


@pytest.mark.parametrize(
    "shared_strings",
    [
        # Internal DTD + entity; the family quirk is present so a successful
        # parse would otherwise produce a compatibility copy.
        (
            '<!DOCTYPE sst [<!ENTITY x "y">]>'
            f'<sst xmlns="{SPREADSHEETML_NAMESPACE}"><si><r><rPr>'
            '<family val="34"/></rPr><t>&x;</t></r></si></sst>'
        ),
        # External DTD must be refused before any fetch.
        (
            '<!DOCTYPE sst SYSTEM "file:///etc/passwd">'
            f'<sst xmlns="{SPREADSHEETML_NAMESPACE}"><si><r><rPr>'
            '<family val="34"/></rPr><t>U-22</t></r></si></sst>'
        ),
    ],
)
def test_dtd_and_entities_are_rejected(shared_strings):
    package = _replace_shared_strings(
        _build_synthetic_xlsx(), shared_strings.encode("utf-8"))
    assert openpyxl_compatible_bytes(package) is None


@pytest.mark.parametrize(
    "styles",
    [
        # Internal DTD + entity; the stylesheet family quirk is present so a
        # successful parse would otherwise produce a compatibility copy.
        (
            '<!DOCTYPE styleSheet [<!ENTITY x "Calibri">]>'
            f'<styleSheet xmlns="{SPREADSHEETML_NAMESPACE}">'
            '<fonts><font><family val="34"/><name val="&x;"/></font></fonts>'
            "</styleSheet>"
        ),
        # External DTD must be refused before any fetch.
        (
            '<!DOCTYPE styleSheet SYSTEM "file:///etc/passwd">'
            f'<styleSheet xmlns="{SPREADSHEETML_NAMESPACE}">'
            '<fonts><font><family val="34"/></font></fonts></styleSheet>'
        ),
    ],
)
def test_stylesheet_dtd_and_entities_are_rejected(styles):
    package = _replace_styles(
        _build_synthetic_xlsx(shared_string_family=2), styles.encode("utf-8"))
    assert openpyxl_compatible_bytes(package) is None


def _deny_defusedxml_import(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _deny_defusedxml(name, *args, **kwargs):
        if name == "defusedxml" or name.startswith("defusedxml."):
            raise ImportError("defusedxml intentionally unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _deny_defusedxml)


def test_missing_defusedxml_declines_without_stdlib_fallback(
    monkeypatch, synthetic_xlsx,
):
    _deny_defusedxml_import(monkeypatch)
    assert openpyxl_compatible_bytes(synthetic_xlsx) is None


def test_missing_defusedxml_declines_stylesheet_only(monkeypatch):
    _deny_defusedxml_import(monkeypatch)
    package = _build_synthetic_xlsx(
        shared_string_family=2, style_families=(34, 35, 36))
    assert openpyxl_compatible_bytes(package) is None


def test_compatibility_only_accepts_exact_ooxml_part_and_namespace():
    defect = (
        f'<sst xmlns="{SPREADSHEETML_NAMESPACE}"><si><r><rPr>'
        '<family val="34"/></rPr><t>U-22</t></r></si></sst>'
    )
    baseline = _build_synthetic_xlsx()

    # Case-variant part path is not the OOXML sharedStrings part.
    wrong_path = _replace_shared_strings(
        baseline, defect.encode("utf-8"), part_name="xl/sharedstrings.xml")
    assert openpyxl_compatible_bytes(wrong_path) is None

    # Same-named root in another namespace is not the shared-string table.
    wrong_root_ns = (
        '<sst xmlns="urn:not-ooxml"><si><r><rPr>'
        '<family val="34"/></rPr><t>U-22</t></r></si></sst>'
    )
    assert openpyxl_compatible_bytes(_replace_shared_strings(
        baseline, wrong_root_ns.encode("utf-8"))) is None

    # rPr/family in a foreign namespace inside the real sst is untouched.
    foreign_rpr = (
        f'<sst xmlns="{SPREADSHEETML_NAMESPACE}" xmlns:x="urn:not-ooxml">'
        '<si><r><x:rPr><x:family val="34"/></x:rPr><t>U-22</t></r>'
        "</si></sst>"
    )
    assert openpyxl_compatible_bytes(_replace_shared_strings(
        baseline, foreign_rpr.encode("utf-8"))) is None


def test_shared_reader_answers_with_original_provider_digest(synthetic_xlsx):
    digest = SHA256(synthetic_xlsx).hexdigest()
    artifact = inspect_workbook_bytes(
        synthetic_xlsx,
        FILE_NAME,
        query="price for U-22",
        requested_fields=["price"],
        provider="zoho_workdrive",
        resource_id=RESOURCE_ID,
        source_metadata={"team_id": "synthetic-team", "version": "v7"},
        ingested_at="2026-11-12T00:00:00+00:00",
    )

    assert SHA256(synthetic_xlsx).hexdigest() == digest
    assert artifact["all_sheets_searched"] is True
    assert artifact["sheet_count"] == 1
    assert artifact["truncated"] is False
    # Identity/lineage stay bound to the downloaded provider bytes, not the
    # private compatibility copy handed to openpyxl.
    assert artifact["sha256"] == digest
    assert artifact["content_hash"] == digest
    assert artifact["content_hash_algorithm"] == "sha256"
    assert artifact["byte_length"] == len(synthetic_xlsx)
    assert artifact["provider"] == "zoho_workdrive"
    assert artifact["resource_id"] == RESOURCE_ID
    assert artifact["file_name"] == FILE_NAME
    assert artifact["source_metadata"]["team_id"] == "synthetic-team"

    outcome = artifact["coverage"]["outcomes"][0]
    assert outcome["status"] == "found"
    evidence = outcome["evidence"][0]
    assert (evidence["sheet"], evidence["cell"], evidence["value"]) == (
        "Price List", "A2", "U-22")
    assert evidence["formula"] is None  # the matched identity cell is literal

    price = evidence["values"][0]
    assert price["cell"] == "B2"
    assert price["value"] == "110"
    assert price["price_basis"] == "List Price"
    assert price["formula_state"] == "cached"
    assert artifact["formula_status"] == "cached"

    observation = workbook_artifact_observations(artifact)[0]
    assert observation["source"]["content_hash"] == digest
    assert observation["source"]["resource_id"] == RESOURCE_ID


def test_shared_reader_digest_survives_both_font_defects():
    package = _build_synthetic_xlsx(
        shared_string_family=34, style_families=(34, 35, 36))
    digest = SHA256(package).hexdigest()
    artifact = inspect_workbook_bytes(
        package,
        FILE_NAME,
        query="price for U-22",
        requested_fields=["price"],
        provider="zoho_workdrive",
        resource_id=RESOURCE_ID,
        source_metadata={"team_id": "synthetic-team", "version": "v7"},
        ingested_at="2026-11-12T00:00:00+00:00",
    )

    assert SHA256(package).hexdigest() == digest
    assert artifact["all_sheets_searched"] is True
    assert artifact["sheet_count"] == 1
    assert artifact["truncated"] is False
    # Evidence stays bound to the downloaded provider bytes, not the private
    # copy with both font families clamped.
    assert artifact["sha256"] == digest
    assert artifact["content_hash"] == digest
    assert artifact["content_hash_algorithm"] == "sha256"
    assert artifact["byte_length"] == len(package)
    assert artifact["provider"] == "zoho_workdrive"
    assert artifact["resource_id"] == RESOURCE_ID

    outcome = artifact["coverage"]["outcomes"][0]
    assert outcome["status"] == "found"
    evidence = outcome["evidence"][0]
    assert (evidence["sheet"], evidence["cell"], evidence["value"]) == (
        "Price List", "A2", "U-22")
    price = evidence["values"][0]
    assert price["cell"] == "B2"
    assert price["value"] == "110"
    assert price["price_basis"] == "List Price"
    assert price["formula_state"] == "cached"
    assert artifact["formula_status"] == "cached"

    observation = workbook_artifact_observations(artifact)[0]
    assert observation["source"]["content_hash"] == digest
    assert observation["source"]["resource_id"] == RESOURCE_ID


def test_workdrive_direct_proof_stays_bound_to_downloaded_digest(synthetic_xlsx):
    """The compatibility copy must not become the proof's source bytes."""
    from core.workdrive_direct_proof import proof_from_storage_read_result

    artifact = inspect_workbook_bytes(
        synthetic_xlsx, FILE_NAME, query="price for U-22",
        requested_fields=["price"], provider="zoho_workdrive",
        resource_id=RESOURCE_ID,
    )
    digest = SHA256(synthetic_xlsx).hexdigest()
    execution_id = "synthetic-execution-1"
    read_result = {
        "served": True,
        "read_completed": True,
        "evidence_kind": "downloaded_bytes",
        "content_sha256": digest,
        "resource_id": RESOURCE_ID,
        "file_name": FILE_NAME,
        "workbook_read": artifact,
        "strict_read_receipt": {
            "schema": "workdrive-direct-receipt-1",
            "provider": "zoho_workdrive",
            "operation": "read_storage_file",
            "resource_id": RESOURCE_ID,
            "sha256": digest,
            "bytes": len(synthetic_xlsx),
            "execution_id": execution_id,
            "evidence_kind": "downloaded_bytes",
            "materialized": False,
        },
    }
    proof = proof_from_storage_read_result(
        read_result,
        execution_id=execution_id,
        expected_resource_id=RESOURCE_ID,
    )
    assert proof["status"] == "verified"
    assert proof["downloaded_sha256"] == digest
    assert proof["downloaded_bytes"] == len(synthetic_xlsx)
    assert proof["answer_source"] == "downloaded_bytes"
    assert proof["materialized"] is False


def test_bounded_checks_decline_without_touching_openpyxl(synthetic_xlsx):
    with zipfile.ZipFile(io.BytesIO(synthetic_xlsx)) as archive:
        sst_size = archive.getinfo(SHARED_STRINGS_PART).file_size
    assert openpyxl_compatible_bytes(
        synthetic_xlsx, max_shared_strings_bytes=sst_size - 1) is None
    assert openpyxl_compatible_bytes(
        synthetic_xlsx,
        max_package_uncompressed_bytes=len(synthetic_xlsx) - 1,
    ) is None


def test_stylesheet_bound_declines_stylesheet_only_recovery():
    package = _build_synthetic_xlsx(
        shared_string_family=2, style_families=(34, 35, 36))
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        styles_size = archive.getinfo(STYLES_PART).file_size
    assert styles_size > 0
    assert openpyxl_compatible_bytes(
        package, max_stylesheet_bytes=styles_size - 1) is None


def test_normal_package_needs_no_compatibility_copy():
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.active.append(["Model", "List Price"])
    workbook.active.append(["U-22", 110])
    buffer = io.BytesIO()
    workbook.save(buffer)
    assert openpyxl_compatible_bytes(buffer.getvalue()) is None
