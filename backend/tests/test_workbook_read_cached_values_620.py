# -*- coding: utf-8 -*-
"""Focused tests for the issue-#620 one-load structured workbook inspection.

The exact-file read used to parse the whole workbook TWICE (formulas, then
``data_only=True`` for cached formula results). The optimized reader loads the
formula workbook once and decodes cached results from the OOXML package.

These tests are synthetic by design: no live WorkDrive workbook, credentials,
network or database. They require three things of the optimization:

* **Golden equivalence** — on fixtures that carry typed cached values,
  formulas, merged ranges and incomplete caches, the optimized artifact is
  byte-for-byte equal (as a structure) to the legacy two-load artifact, and
  the original digest/coverage/formula metadata are unchanged.
* **One full openpyxl load** — the legacy fallback remains available and
  produces the same artifact when the OOXML scan cannot run.
* **Hardened OOXML scan** (2026-11-12) — the scan parses with defusedxml
  only (DTDs, entities and external references forbidden), streams every
  part under per-part and total byte caps, refuses external sheet
  relationships and out-of-range shared-string indices, and on EVERY
  violation declines (raises) so the caller restores the legacy two-load
  behavior instead of silently reporting missing cached values.
"""
from __future__ import annotations

import builtins
import hashlib
import io
import os
import re
import socket
import sys
import time
import zipfile
from datetime import datetime

import openpyxl
import pytest
from openpyxl import Workbook
from openpyxl.utils.datetime import to_excel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import core.workbook_read_artifact as artifact_module
from core.workbook_read_artifact import (
    _decode_ooxml_cached_value,
    _ooxml_cached_value_map,
    inspect_workbook_bytes,
)

FILE_NAME = "Synthetic Price List 2026.xlsx"
QUERY = "prices for U-22, 622 and SLE24-16"
REQUESTED_FIELDS = ["price", "date"]


def _inject_cached_values(
    package: bytes,
    spec: dict[int, dict[str, tuple[str, str]]],
) -> bytes:
    """Add cached ``<v>`` elements to formula cells (test-only rewrite).

    openpyxl never writes cached values for formulas it saves, so the fixture
    injects them exactly where a real producer would: beside the ``<f>``
    element, with the OOXML cell type that carries the value's typing.
    ``spec`` maps a 1-based worksheet part index to ``{ref: (type, value)}``.
    """
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(package)) as source, zipfile.ZipFile(
        output, "w", zipfile.ZIP_DEFLATED,
    ) as target:
        touched: set = set()
        for info in source.infolist():
            payload = source.read(info)
            match = re.fullmatch(
                r"xl/worksheets/sheet(\d+)\.xml", info.filename)
            if match and int(match.group(1)) in spec:
                index = int(match.group(1))
                text = payload.decode("utf-8")
                for ref, (cell_type, value) in spec[index].items():
                    pattern = re.compile(
                        r'(<c\b(?=[^>]*\br="' + re.escape(ref) + r'")'
                        r'[^>]*?)(>)(<f\b[^>]*/>|<f\b[^>]*>.*?</f>)'
                        r'(?:<v\s*/>|<v></v>)?</c>',
                        re.DOTALL,
                    )

                    def _replace(cell_match: re.Match, _type=cell_type,
                                 _value=value) -> str:
                        attrs = cell_match.group(1)
                        if _type != "n":
                            attrs = f'{attrs} t="{_type}"'
                        return (
                            f"{attrs}>{cell_match.group(3)}"
                            f"<v>{_value}</v></c>"
                        )

                    text, count = pattern.subn(_replace, text)
                    assert count == 1, (
                        f"{ref} formula cell not found in {info.filename}")
                touched.add(index)
                payload = text.encode("utf-8")
            target.writestr(info, payload)
        assert touched == set(spec), (touched, set(spec))
    return output.getvalue()


def _golden_fixture() -> bytes:
    """Typed cached values + formulas + merged ranges + one empty cache."""
    workbook = Workbook()
    prices = workbook.active
    prices.title = "Prices"
    prices.append([
        "Model", "Description", "List Price", "Dealer Price",
        "Effective Date", "In Stock", "Status",
    ])
    prices.append(["U-22", "Rotary machine", 220, None, None, None, None])
    prices.append(["622", "Press brake", 5000, None, None, None, None])
    prices.append(["SLE24-16", "Slitter", 8880, None, None, None, None])
    for row in (2, 3, 4):
        prices[f"D{row}"] = f"=C{row}*1.2"
        prices[f"D{row}"].number_format = "0.00"
    prices["E2"] = "=DATE(2026,11,12)"
    prices["E2"].number_format = "yyyy-mm-dd"
    prices["F2"] = "=C2>100"
    prices["G2"] = '=IF(C2>0,"OK","NO")'
    prices["F3"] = "=1/0"
    # Deliberately NO cached value: the artifact must report the gap.
    prices["F4"] = "=C4*9"
    prices.merge_cells("A6:B6")
    prices["A6"] = "Merged note"
    prices.merge_cells("C6:D6")
    prices["C6"] = "=SUM(C2:C4)"
    prices["C6"].number_format = "0.00"

    second = workbook.create_sheet("Second")
    second.append(["Model", "List Price"])
    second.append(["GSL48-16", 14166])
    second["C2"] = "=B2*2"

    third = workbook.create_sheet("No formulas")
    third.append(["Model", "List Price"])
    third.append(["U-38", 999])

    buffer = io.BytesIO()
    workbook.save(buffer)
    package = buffer.getvalue()

    date_serial = str(int(to_excel(datetime(2026, 11, 12))))
    package = _inject_cached_values(package, {
        1: {
            "D2": ("n", "264.0"),      # float
            "D3": ("n", "6000"),       # int
            "D4": ("n", "10656"),      # int
            "E2": ("n", date_serial),  # date-formatted serial
            "F2": ("b", "1"),          # boolean
            "G2": ("str", "OK"),       # string result
            "F3": ("e", "#DIV/0!"),    # error literal
            "C6": ("n", "14100"),      # merged anchor
        },
        2: {"C2": ("n", "28332")},
    })
    return package


GOLDEN = _golden_fixture()


def _inspect(package: bytes) -> dict:
    return inspect_workbook_bytes(
        package,
        FILE_NAME,
        query=QUERY,
        requested_fields=REQUESTED_FIELDS,
        provider="zoho_workdrive",
        resource_id="synthetic-620",
        source_metadata={"team_id": "synthetic", "version": "v620"},
        ingested_at="2026-11-12T00:00:00+00:00",
    )


@pytest.fixture()
def legacy_inspection(monkeypatch):
    """Force the legacy two-load behavior through the production fallback."""

    def _no_ooxml_scan(_content: bytes):
        raise RuntimeError("synthetic: OOXML scan unavailable")

    monkeypatch.setattr(
        artifact_module, "_ooxml_cached_value_map", _no_ooxml_scan)
    return _inspect(GOLDEN)


def test_optimized_artifact_is_golden_equal_to_legacy_two_load(
    legacy_inspection,
):
    optimized = _inspect(GOLDEN)

    assert optimized == legacy_inspection

    # The properties the equality could hide behind a shared wrong answer.
    digest = hashlib.sha256(GOLDEN).hexdigest()
    assert optimized["sha256"] == digest
    assert optimized["content_hash"] == digest
    assert optimized["byte_length"] == len(GOLDEN)
    assert optimized["sheet_count"] == 3
    assert optimized["all_sheets_searched"] is True
    assert optimized["truncated"] is False
    assert optimized["coverage"]["complete"] is True
    assert all(sheet["searched"] for sheet in optimized["sheets"])
    merged = {
        sheet["name"]: sheet["merged_ranges"] for sheet in optimized["sheets"]
    }
    assert "A6:B6" in merged["Prices"]
    assert "C6:D6" in merged["Prices"]

    # Cached values survive with their typing-driven rendering, and the
    # formula that has no cached value is still reported as a gap.
    by_target = {
        outcome["target"]: outcome
        for outcome in optimized["coverage"]["outcomes"]
    }
    assert set(by_target) == {"U-22", "622", "SLE24-16"}
    assert all(
        outcome["status"] == "found"
        for outcome in by_target.values()
    )
    u22_values = {
        value["cell"]: value
        for value in by_target["U-22"]["evidence"][0]["values"]
    }
    assert u22_values["D2"]["value"] == "264.0"
    assert u22_values["D2"]["formula_state"] == "cached"
    assert u22_values["E2"]["value"] == "2026-11-12 00:00:00"
    assert u22_values["E2"]["formula_state"] == "cached"
    assert optimized["formula_status"] == "mixed"


def test_cached_value_decoding_matches_openpyxl_data_only():
    cached = _ooxml_cached_value_map(GOLDEN)
    formulas = openpyxl.load_workbook(io.BytesIO(GOLDEN), data_only=False)
    values = openpyxl.load_workbook(io.BytesIO(GOLDEN), data_only=True)
    try:
        compared = 0
        for worksheet in formulas.worksheets:
            for row in worksheet.iter_rows():
                for cell in row:
                    if not (
                        isinstance(cell.value, str)
                        and cell.value.startswith("=")
                    ):
                        continue
                    entry = cached.get(worksheet.title, {}).get(
                        cell.coordinate)
                    ours = (
                        None if entry is None
                        else _decode_ooxml_cached_value(
                            entry, cell.number_format, formulas.epoch)
                    )
                    expected = values[worksheet.title][cell.coordinate].value
                    assert ours == expected, (
                        worksheet.title, cell.coordinate, ours, expected)
                    if expected is not None:
                        assert type(ours) is type(expected), (
                            worksheet.title, cell.coordinate,
                            type(ours), type(expected))
                    compared += 1
        # Every formula cell in the fixture is accounted for, including the
        # deliberately uncached one.
        assert compared == 10
    finally:
        formulas.close()
        values.close()


def test_targeted_inspection_uses_no_full_openpyxl_load(monkeypatch):
    """A targeted read answers from the OOXML stream: zero full parses.

    Issue #620's follow-up: the one-load reader still materialised the whole
    workbook — and then a row list per sheet on top of it — so a 46-sheet,
    eight-target lookup exceeded 3 GiB. The targeted lane streams instead;
    the legacy fallback is the only path that reaches openpyxl, and only when
    the stream declines (see the decline tests below).
    """
    calls: list = []
    real_loader = openpyxl.load_workbook

    def _spy(*args, **kwargs):
        calls.append(kwargs.get("data_only"))
        return real_loader(*args, **kwargs)

    monkeypatch.setattr(openpyxl, "load_workbook", _spy)
    artifact = _inspect(GOLDEN)

    assert artifact["coverage"]["complete"] is True
    # No full parse at all on the targeted lane.
    assert calls == []
    assert artifact["sha256"] == hashlib.sha256(GOLDEN).hexdigest()
    assert artifact["sheet_count"] == 3


def test_legacy_fallback_still_restores_the_second_load(
    monkeypatch, legacy_inspection,
):
    calls: list = []
    real_loader = openpyxl.load_workbook

    def _spy(*args, **kwargs):
        calls.append(kwargs.get("data_only"))
        return real_loader(*args, **kwargs)

    monkeypatch.setattr(openpyxl, "load_workbook", _spy)
    artifact = _inspect(GOLDEN)

    assert calls == [False, True]
    assert artifact == legacy_inspection


def _benchmark_fixture(sheets: int = 24, rows: int = 120) -> bytes:
    workbook = Workbook()
    for index in range(sheets):
        sheet = workbook.active if index == 0 else workbook.create_sheet()
        sheet.title = f"Sheet {index + 1}"
        sheet.append([
            "Model", "Description", "List Price", "Dealer Price", "Quantity",
        ])
        for row in range(2, rows + 2):
            sheet.append([
                f"M-{index + 1}-{row}", "Machine", 1000 + row, None, row,
            ])
            sheet[f"D{row}"] = f"=C{row}*1.15"
            sheet[f"D{row}"].number_format = "0.00"
            sheet[f"E{row}"] = f"=C{row}*2"
    buffer = io.BytesIO()
    workbook.save(buffer)
    package = buffer.getvalue()
    package = _inject_cached_values(package, {
        index: {
            f"D{row}": ("n", f"{1000 + row}.0")
            for row in range(2, rows + 2)
        } | {
            f"E{row}": ("n", str((1000 + row) * 2))
            for row in range(2, rows + 2)
        }
        for index in range(1, sheets + 1)
    })
    return package


def test_benchmark_one_load_replaces_the_second_full_parse(capsys):
    """Record component + end-to-end timing; assert only the structural win.

    Wall-clock assertions are intentionally absent (CI hosts share CPU); the
    numbers are printed for the issue-#620 report. The structural assertion —
    one full parse instead of two — is deterministic.
    """
    package = _benchmark_fixture()
    # Warm the reader on a small package so import/first-call costs do not
    # dominate the measurement.
    _inspect(GOLDEN)

    real_scanner = artifact_module._ooxml_cached_value_map

    def _unavailable(_content: bytes):
        raise RuntimeError("synthetic: legacy two-load measurement")

    def _measure(fn, repeats: int = 2) -> float:
        best = None
        for _ in range(repeats):
            started = time.perf_counter()
            fn()
            elapsed = time.perf_counter() - started
            best = elapsed if best is None else min(best, elapsed)
        return best

    optimized_seconds = _measure(lambda: _inspect(package))
    try:
        artifact_module._ooxml_cached_value_map = _unavailable
        legacy_seconds = _measure(lambda: _inspect(package))
    finally:
        artifact_module._ooxml_cached_value_map = real_scanner

    second_load_seconds = _measure(
        lambda: openpyxl.load_workbook(
            io.BytesIO(package), data_only=True, read_only=False,
            keep_links=False,
        ).close()
    )
    ooxml_scan_seconds = _measure(lambda: _ooxml_cached_value_map(package))

    report = (
        "\nBENCHMARK #620 (synthetic "
        f"{len(package)} bytes, 24 sheets x 120 rows, 5,760 formula cells)\n"
        f"  legacy inspect (two full loads): {legacy_seconds:.3f}s\n"
        f"  optimized inspect (one load):    {optimized_seconds:.3f}s\n"
        f"  saved second full load:         "
        f"{second_load_seconds:.3f}s\n"
        f"  OOXML cached-value scan:        {ooxml_scan_seconds:.3f}s\n"
        f"  measured inspect speedup:       "
        f"{legacy_seconds / optimized_seconds:.2f}x"
    )
    with capsys.disabled():
        print(report)
    assert report.startswith("\nBENCHMARK #620")
    assert ooxml_scan_seconds < second_load_seconds
    assert optimized_seconds < legacy_seconds * 1.10


# ---------------------------------------------------------------------------
# HARDENING (2026-11-12): defusedxml-only streaming scan with bounded
# resources; every violation DECLINES the scan so the legacy two-load
# fallback preserves artifact parity. All fixtures below are synthetic.
# ---------------------------------------------------------------------------

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_OFF_REL_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)


def _rebuild_package(source: bytes, part: str, transform) -> bytes:
    """Rebuild the package with one member's text transformed (test-only)."""
    output = io.BytesIO()
    touched = False
    with zipfile.ZipFile(io.BytesIO(source)) as src, zipfile.ZipFile(
        output, "w", zipfile.ZIP_DEFLATED,
    ) as dst:
        for info in src.infolist():
            data = src.read(info)
            if info.filename == part:
                touched = True
                data = transform(data.decode("utf-8")).encode("utf-8")
            dst.writestr(info, data)
    assert touched, f"{part} not found in the fixture package"
    return output.getvalue()


def _forced_legacy_inspect(monkeypatch, package: bytes) -> dict:
    """The artifact under the legacy two-load path (scan forced to decline)."""
    with monkeypatch.context() as ctx:
        def _decline(_content: bytes):
            raise RuntimeError("synthetic: legacy two-load")

        ctx.setattr(artifact_module, "_ooxml_cached_value_map", _decline)
        return _inspect(package)


def _load_spy(monkeypatch) -> list:
    """Record the ``data_only`` flag of every openpyxl load."""
    calls: list = []
    real_loader = openpyxl.load_workbook

    def _spy(*args, **kwargs):
        calls.append(kwargs.get("data_only"))
        return real_loader(*args, **kwargs)

    monkeypatch.setattr(openpyxl, "load_workbook", _spy)
    return calls


def test_scan_declines_without_defusedxml_and_never_uses_stdlib_parse(
    monkeypatch, legacy_inspection,
):
    """defusedxml is a hard dependency of the scan.

    Without it the scan DECLINES (raises) — it must never fall back to the
    stdlib parser, which would reopen the DTD/entity path. End to end the
    read still produces exactly the legacy artifact through the documented
    legacy second openpyxl load.
    """
    real_import = builtins.__import__

    def _deny_defusedxml(name, *args, **kwargs):
        if name == "defusedxml" or name.startswith("defusedxml."):
            raise ImportError("defusedxml intentionally unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _deny_defusedxml)
    with pytest.raises(RuntimeError, match="defusedxml unavailable"):
        _ooxml_cached_value_map(GOLDEN)

    calls = _load_spy(monkeypatch)
    assert _inspect(GOLDEN) == legacy_inspection
    assert calls == [False, True]


def test_scan_rejects_dtd_and_entity_expansion(monkeypatch):
    """A DOCTYPE or entity in a worksheet part kills the scan — loudly.

    The scan must raise (never resolve the entity), and the end-to-end
    artifact must equal the legacy two-load artifact for the same hostile
    bytes: parity is preserved through the safe fallback, never through a
    silently weakened read.
    """
    entity = _rebuild_package(
        GOLDEN, "xl/worksheets/sheet1.xml",
        lambda text: text
        .replace(
            "<worksheet",
            '<!DOCTYPE worksheet [<!ENTITY x620 "ENTITYWAS">]><worksheet', 1)
        .replace("<t>Rotary machine</t>", "<t>Rotary &x620; machine</t>", 1),
    )
    with pytest.raises((RuntimeError, ValueError)):
        _ooxml_cached_value_map(entity)

    legacy = _forced_legacy_inspect(monkeypatch, entity)
    optimized = _inspect(entity)
    assert optimized == legacy
    # The hostile package fails the read honestly: no sheets, incomplete
    # coverage, and the original bytes' digest untouched.
    assert optimized["sheets"] == []
    assert optimized["coverage"]["complete"] is False
    assert optimized["sha256"] == hashlib.sha256(entity).hexdigest()
    assert optimized["byte_length"] == len(entity)


def test_scan_rejects_external_sheet_relationship(monkeypatch):
    """A sheet whose relationship is TargetMode="External" is refused.

    Silently skipping the sheet would report its formula cache as
    "unavailable" — a silent parity break — so the scan declines instead
    and the caller restores the legacy behavior for the whole workbook.
    """
    external = _rebuild_package(
        GOLDEN, "xl/_rels/workbook.xml.rels",
        lambda text: text.replace(
            'Target="/xl/worksheets/sheet1.xml"',
            'Target="/xl/worksheets/sheet1.xml" TargetMode="External"', 1),
    )
    with pytest.raises(RuntimeError, match="external references"):
        _ooxml_cached_value_map(external)

    legacy = _forced_legacy_inspect(monkeypatch, external)
    assert _inspect(external) == legacy


def test_scan_ignores_unreferenced_external_relationships(monkeypatch):
    """An external relationship no sheet references cannot change the map.

    Real producers keep hyperlink-style entries in workbook-level rels; the
    scan maps parts only through internal sheet relationships, so benign
    parity holds and no fetch is even possible.
    """
    patched = _rebuild_package(
        GOLDEN, "xl/_rels/workbook.xml.rels",
        lambda text: text.replace(
            "</Relationships>",
            '<Relationship Id="rIdAttack" '
            f'Type="{_OFF_REL_NS}/hyperlink" '
            'Target="http://attacker.example/evil.xml" '
            'TargetMode="External"/></Relationships>', 1),
    )

    def _no_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", _no_network)
    assert _ooxml_cached_value_map(patched) == _ooxml_cached_value_map(GOLDEN)
    artifact = _inspect(patched)
    assert artifact["coverage"]["complete"] is True
    by_target = {
        outcome["target"]: outcome["status"]
        for outcome in artifact["coverage"]["outcomes"]
    }
    assert by_target == {"U-22": "found", "622": "found", "SLE24-16": "found"}


def test_scan_streams_parts_without_tree_materialisation(monkeypatch):
    """Every part is consumed through streaming iterparse.

    Both ``fromstring`` entry points (defused and stdlib) are wired to
    fail: the scan must still produce the identical map, proving no part
    is materialised as a tree and no stdlib parse path exists.
    """
    expected = _ooxml_cached_value_map(GOLDEN)

    def _refuse_fromstring(*args, **kwargs):
        raise AssertionError("tree-materialising parse used")

    monkeypatch.setattr(
        "defusedxml.ElementTree.fromstring", _refuse_fromstring)
    monkeypatch.setattr(
        "xml.etree.ElementTree.fromstring", _refuse_fromstring)
    assert _ooxml_cached_value_map(GOLDEN) == expected


def test_scan_declines_when_part_cap_exceeded(monkeypatch, legacy_inspection):
    """A worksheet part over its byte cap declines the scan — it never
    returns truncated results. The caller then restores the legacy
    two-load behavior, so the artifact stays parity-equal."""
    monkeypatch.setattr(artifact_module, "MAX_OOXML_WORKSHEET_BYTES", 1)
    with pytest.raises(RuntimeError, match="cap"):
        _ooxml_cached_value_map(GOLDEN)

    calls = _load_spy(monkeypatch)
    assert _inspect(GOLDEN) == legacy_inspection
    assert calls == [False, True]


def test_scan_declines_when_total_budget_exceeded(monkeypatch):
    """The scan-wide byte budget is checked before any part is read."""
    monkeypatch.setattr(artifact_module, "MAX_OOXML_SCAN_TOTAL_BYTES", 1)
    with pytest.raises(RuntimeError, match="budget"):
        _ooxml_cached_value_map(GOLDEN)


def _shared_strings_package(index_for_c2: int = 3) -> bytes:
    """A handcrafted package whose cached formula results use shared strings.

    The golden fixture (openpyxl-saved) carries literal ``str``/``n`` cached
    types only; this fixture exercises the ``t="s"`` index path, rich-text
    shared strings, and a cached string formula result.
    """
    parts = {
        "[Content_Types].xml":
 '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
 '<Default Extension="rels" ContentType='
 '"application/vnd.openxmlformats-package.relationships+xml"/>'
 '<Default Extension="xml" ContentType="application/xml"/>'
 '<Override PartName="/xl/workbook.xml" ContentType='
 '"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
 '<Override PartName="/xl/worksheets/sheet1.xml" ContentType='
 '"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
 '<Override PartName="/xl/sharedStrings.xml" ContentType='
 '"application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
 '</Types>',
        "_rels/.rels":
 '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
 f'<Relationships xmlns="{_PKG_REL_NS}">'
 f'<Relationship Id="rId1" Type="{_OFF_REL_NS}/officeDocument" '
 'Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml":
 '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
 f'<workbook xmlns="{_MAIN_NS}" xmlns:r="{_OFF_REL_NS}">'
 '<sheets><sheet name="Shared" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels":
 '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
 f'<Relationships xmlns="{_PKG_REL_NS}">'
 f'<Relationship Id="rId1" Type="{_OFF_REL_NS}/worksheet" '
 'Target="worksheets/sheet1.xml"/>'
 f'<Relationship Id="rId2" Type="{_OFF_REL_NS}/sharedStrings" '
 'Target="sharedStrings.xml"/></Relationships>',
        "xl/sharedStrings.xml":
 '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
 f'<sst xmlns="{_MAIN_NS}" count="4" uniqueCount="4">'
 '<si><t>Model</t></si>'
 '<si><t>U-22</t></si>'
 '<si><r><t>Rich </t></r><r><t>Tail</t></r></si>'
 '<si><t>OK</t></si>'
 '</sst>',
        "xl/worksheets/sheet1.xml":
 '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
 f'<worksheet xmlns="{_MAIN_NS}"><sheetData>'
 '<row r="1"><c r="A1" t="s"><v>0</v></c>'
 '<c r="B1" t="s"><v>2</v></c></row>'
 '<row r="2"><c r="A2" t="s"><v>1</v></c>'
 '<c r="B2"><f>B2*2</f><v>444</v></c>'
 f'<c r="C2" t="s"><f>CONCAT(A2," tail")</f><v>{index_for_c2}</v></c>'
 '</row></sheetData></worksheet>',
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_shared_string_cached_results_match_openpyxl_data_only():
    """``t="s"`` cached results decode through the shared-string table
    exactly as openpyxl's ``data_only=True`` load does."""
    package = _shared_strings_package()
    cached = _ooxml_cached_value_map(package)
    assert cached == {"Shared": {"B2": ("n", 444), "C2": ("s", "OK")}}

    formulas = openpyxl.load_workbook(io.BytesIO(package), data_only=False)
    values = openpyxl.load_workbook(io.BytesIO(package), data_only=True)
    try:
        for coordinate in ("B2", "C2"):
            expected = values["Shared"][coordinate].value
            ours = _decode_ooxml_cached_value(
                cached["Shared"][coordinate],
                formulas["Shared"][coordinate].number_format,
                formulas.epoch,
            )
            assert ours == expected, (coordinate, ours, expected)
        assert formulas["Shared"]["B2"].value == "=B2*2"
    finally:
        formulas.close()
        values.close()

    # End to end the read binds the target and cites the cached value.
    artifact = _inspect(package)
    assert artifact["coverage"]["complete"] is True
    outcome = next(
        item for item in artifact["coverage"]["outcomes"]
        if item["target"] == "U-22")
    assert outcome["status"] == "found"
    cached_cells = {
        value["cell"]: value
        for evidence in outcome["evidence"]
        for value in evidence["values"]
    }
    assert cached_cells["B2"]["value"] == "444"
    assert cached_cells["B2"]["formula_state"] == "cached"


def test_scan_declines_out_of_range_shared_string_index(monkeypatch):
    """A shared-string index outside the table declines the scan.

    A negative index would silently wrap to a wrong string; openpyxl's own
    loader errors on the out-of-range case. Either way the scan must not
    fabricate a value — it declines and the legacy path decides.
    """
    for bad_index in (99, -1):
        package = _shared_strings_package(index_for_c2=bad_index)
        with pytest.raises(RuntimeError, match="out of range"):
            _ooxml_cached_value_map(package)

        legacy = _forced_legacy_inspect(monkeypatch, package)
        optimized = _inspect(package)
        assert optimized == legacy
        # The workbook itself is readable; only the fabricated cache is gone.
        assert optimized["coverage"]["complete"] is True
