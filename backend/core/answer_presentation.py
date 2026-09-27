"""Answer presentation — slice 1 (review rounds 27-28 work order).

PURPOSE. The workbook answer collapsed three concerns into one text blob:
what the evidence establishes, how it is presented, and what a follow-up
asks for. This module separates presentation from evidence: a PURE
renderer consumes a structured presentation contract plus presentation
preferences and returns a readable answer. No retrieval, no database
writes, no evidence mutation. Detailed evidence stays out of the main
answer (the evidence block / evidence UI remains its home).

CONTRACT (pres-v2). Input is the scan layer's per-target outcome -
identity status, field-selection status, typed values with their original
column labels and bases, source references - plus the ordered requested
items and a source block (workbook identity, saved-copy date, live-vs-
saved, coverage). Evidence revision and presentation version are stamped
on the result so stored answers are traceable to both.

MEANING RULES (work order section 4): aliases aid matching without
becoming extra items; multiple cells in one matched row are one
candidate, but genuinely different rows stay distinct candidates; price
bases (PRICE / U.S. LIST / Factory Price / FULL COST CDN) never collapse;
no field is silently chosen - labeled alternatives or one focused
clarification; zero stays zero; blank is stated plainly; non-finite is
unavailable, never nan; uncertainty is stated once; missing items never
imply absence from the live workbook.

COMPAT PATH. present_from_rendered_text rebuilds the contract from a
legacy rendered answer (text parsing). It is explicitly COMPATIBILITY
COVERAGE for records that stored only text - it cannot validate the
artifact-native path and is not evidence reconstruction.
"""
from __future__ import annotations

import math
import copy
import re
from typing import Any, Dict, List, Optional

PRESENTATION_VERSION = "pres-v2"

_CITE_RE = re.compile(r"([A-Za-z][A-Za-z0-9 .&'-]*?)\s*!\s*([A-Z]{1,3}\d{1,7})")
_PAIR_RE = re.compile(
    r"([A-Z]{1,3}\d{1,7})\s*=\s*(-?\$?[\d,]+(?:\.\d+)?|)\s*\[basis=([^\];]+)")


def typed_value(raw: Any) -> Dict[str, Any]:
    """Classify a raw cell value: zero stays zero, blank is blank,
    non-finite/invalid is unavailable (never nan)."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return {"kind": "blank", "display": "blank"}
    if isinstance(raw, str):
        cleaned = raw.replace("$", "").replace(",", "").strip()
        try:
            num = float(cleaned)
        except ValueError:
            return {"kind": "text", "display": raw.strip()}
    else:
        num = float(raw)
    if math.isnan(num) or math.isinf(num):
        return {"kind": "unavailable", "display": "unavailable"}
    if num == 0:
        return {"kind": "zero", "display": "0"}
    display = f"{num:,.2f}".rstrip("0").rstrip(".")
    return {"kind": "number", "value": num, "display": display}


def _concise_result(t: Dict[str, Any]) -> str:
    """One short result clause for table cells: primary display plus its
    basis and row reference, never silent about what was chosen."""
    ident = t.get("identity") or {}
    candidates = ident.get("candidates") or []
    pooled = (t.get("field") or {}).get("values") or []
    if (ident.get("status") == "multiple" or not pooled) and candidates:
        first = candidates[0]
        cvals = first.get("values") or []
        if cvals:
            return (f"several rows match; {first.get('ref', '?')}: "
                    f"{cvals[0].get('basis', '')} "
                    f"{cvals[0].get('display', '')}".strip())
        return "several rows match; confirmation needed"
    if not pooled:
        return "no readable value"
    primary = pooled[0]
    return (f"{primary.get('display', '?')} "
            f"({primary.get('basis', '')})".strip())


def present(*, requested_items: List[str], requested_fields: List[str],
            source: Dict[str, Any], targets: List[Dict[str, Any]],
            evidence_revision: str = "", style: str = "default",
            field: Optional[str] = None) -> Dict[str, Any]:
    """The pure renderer: structured contract in, readable answer out.
    No retrieval, no database writes, no evidence mutation. ``style`` is
    one of default (full entries), compact (one line per item), or table
    (one markdown row per item); ``field`` prefers one basis by name."""
    lines: List[str] = []
    name = source.get("file_name") or "the workbook"
    saved = source.get("saved_copy_date")
    live_vs_saved = source.get("live_vs_saved") or "saved copy"
    opening = f"Results from the {live_vs_saved} of {name}"
    if saved:
        opening += f" (copy saved {saved})"
    lines.append(opening + ":")
    lines.append("")
    if style == "table":
        lines.append("| item | result |")
        lines.append("|---|---|")
        for item in requested_items:
            t = _find_target(targets, item)
            if t is None:
                lines.append(
                    f"| {item} | no result in the indexed copy searched |")
                continue
            lines.append(f"| {item} | {_concise_result(t)} |")
    else:
        for item in requested_items:
            t = _find_target(targets, item)
            if t is None:
                lines.append(f"- **{item}** - no result in the indexed copy searched")
                continue
            lines.append(_render_target(
                t, item, style=style, field=field,
                requested_fields=requested_fields))
    coverage_raw = source.get("coverage") or "unknown"
    if isinstance(coverage_raw, dict):
        parts = []
        if coverage_raw.get("indexed_sheets") is not None:
            parts.append(f"indexed sheets={coverage_raw.get('indexed_sheets')}")
        scanned = coverage_raw.get("scanned_entries")
        if scanned is None:
            scanned = coverage_raw.get("scanned_sheets")
        if scanned is not None:
            parts.append(f"scanned entries={scanned}")
        if coverage_raw.get("catalog_truncated"):
            parts.append("catalog truncated")
        coverage = "; ".join(parts) if parts else "partial"
    else:
        coverage = str(coverage_raw)
    note = (f"Source: {name} - {live_vs_saved}"
            + (f", copy saved {saved}" if saved else "")
            + f". Coverage: {coverage}. Unlisted sheets or newer versions may "
              f"contain more; this is not an absence claim about the live workbook.")
    lines.append("")
    lines.append(note)
    return {"answer": "\n".join(lines),
            "presentation_version": PRESENTATION_VERSION,
            "evidence_revision": evidence_revision,
            "requested_fields": list(requested_fields),
            "style": style}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def _find_target(targets: List[Dict[str, Any]], item: str) -> Optional[Dict[str, Any]]:
    """Exact normalized correspondence only. Unresolved stays unresolved:
    no substring fallback (a bare '381' must never claim a '381mm' row)."""
    key = _norm(item)
    for t in targets:
        labels = [t.get("item", "")] + list(t.get("aliases") or [])
        for lab in labels:
            if _norm(lab) == key:
                return t
    return None


def _field_match_terms(field: Optional[str]) -> List[List[str]]:
    """Alias-expanded match terms for a requested field, reusing the
    scan layer's field vocabulary (generic - no per-product rules).
    Each term is a token list; a basis matches when it contains EVERY
    token ("factory price" selects Factory Price, not every PRICE)."""
    if not field:
        return []
    try:
        from core.workbook_read_artifact import _FIELD_ALIASES
        key = str(field).strip().lower()
        if key in _FIELD_ALIASES:
            return [[t for t in _norm(a).split(" ") if t]
                    for a in _FIELD_ALIASES[key]]
    except Exception:
        pass
    return [[t for t in _norm(field).split(" ") if t]]


def _value_matches(value: Dict[str, Any], terms: List[List[str]]) -> bool:
    if not terms:
        return True
    basis = [t for t in _norm(value.get("basis") or "").split(" ") if t]
    for term in terms:
        if term and all(tok in basis for tok in term):
            return True
    return False


def _select_values(values: List[Dict[str, Any]],
                   requested_fields: List[str],
                   field: Optional[str]) -> List[Dict[str, Any]]:
    """Apply requested fields: an explicit field preference wins; else the
    requested-field families filter. Never silently choose: filtering only
    narrows to what was asked for."""
    terms: List[List[str]] = []
    if field:
        terms = _field_match_terms(field)
    else:
        for req in requested_fields or []:
            terms.extend(_field_match_terms(req))
    if not terms:
        return list(values)
    return [v for v in values if _value_matches(v, terms)]


def _identity_cells(cand: Dict[str, Any]) -> List[str]:
    """The exact identity CELL coordinates bound to one candidate.

    `build_targets_from_scan` records the cells whose text actually matched
    under `candidate.identity.references[].cell` (e.g. "A26"). The compact
    `ref` is a row locator ("LINMAC!R26"), which is a position and NOT proof of
    which cell held the identity. Both are carried, because the contract
    (AGENT_SEARCH_WORK_ORDER_2026_09_26 line 79) allows a row citation to be
    DISPLAYED compactly while requiring the exact identity and value
    references to stay separately exposed. A row locator is never presented
    as if it were a cell.
    """
    ident = cand.get("identity") or {}
    out: List[str] = []
    for ref in ident.get("references") or []:
        cell = str((ref or {}).get("cell") or "").strip().upper()
        if re.match(r"^[A-Z]{1,3}\d{1,7}$", cell) and cell not in out:
            out.append(cell)
    return out


def _value_clause(v: Dict[str, Any]) -> str:
    """One value as `<cell> '<basis>' <display>`.

    Every clause names the CELL it came from and quotes the BASIS, so a reader
    -- and an evidence parser -- can tell which cell is blank and on what
    basis. The ambiguous branch used to render a bare `PRICE blank` with no
    cell at all, which made "this row's price cell is blank"
    indistinguishable from "no price column exists here", and left an
    evaluator nothing to bind a value to.
    """
    cell = str(v.get("col") or "").strip()
    basis = str(v.get("basis") or "").strip()
    display = str(v.get("display") or "").strip()
    if not cell:
        return f"{basis} {display}".strip()
    return f"{cell} '{basis}' {display}".strip()


def _render_target(t: Dict[str, Any], item: str, *,
                   style: str = "default",
                   field: Optional[str] = None,
                   requested_fields: Optional[List[str]] = None) -> str:
    ident = t.get("identity") or {}
    status = ident.get("status")
    alias = t.get("aliases") or []
    alias_note = f" (matched via '{alias[0]}')" if alias else ""
    requested_fields = list(requested_fields or [])
    if status == "none":
        return f"- **{item}**{alias_note} - no matching row in the indexed content searched"
    candidates = ident.get("candidates") or []
    pooled = (t.get("field") or {}).get("values") or []
    selected = _select_values(pooled, requested_fields, field)
    if status == "multiple":
        parts = []
        for c in candidates[:3]:
            cvals = _select_values(c.get("values") or [], requested_fields, field)
            # Name the identity cell alongside the row locator, so an
            # ambiguous row is still identified down to a cell.
            idcells = _identity_cells(c)
            idnote = f" at {', '.join(idcells)}" if idcells else ""
            if cvals:
                shown = "; ".join(_value_clause(v) for v in cvals[:3])
                parts.append(f"{c.get('ref', '?')}{idnote} ({shown})")
            else:
                parts.append(f"{c.get('ref', '?')}{idnote}")
        line = (f"- **{item}**{alias_note} - several rows match "
                f"({'; '.join(parts)}); "
                f"which one is yours needs your confirmation")
        return line
    cand = candidates[0] if candidates else {}
    ref = cand.get("ref", "")
    idcells = _identity_cells(cand)
    idnote = f" matched at {', '.join(idcells)}" if idcells else ""
    fstatus = (t.get("field") or {}).get("status")
    if fstatus == "absent" or not pooled:
        return (f"- **{item}**{alias_note} - matched at {ref}{idnote}, but no "
                f"price column was identified")
    if field and not selected:
        bases = sorted({str(v.get("basis") or "") for v in pooled if v.get("basis")})
        return (f"- **{item}**{alias_note} - matched at {ref}{idnote}; "
                f"requested '{field}' is not among the available bases "
                f"({', '.join(bases)}). Which basis should answer?")
    if not selected:
        bases = sorted({str(v.get("basis") or "") for v in pooled if v.get("basis")})
        return (f"- **{item}**{alias_note} - matched at {ref}{idnote}; "
                f"none of the requested fields match the available bases "
                f"({', '.join(bases)}). Which basis should answer?")
    primary = selected[0]
    if style == "compact":
        return (f"- **{item}**{alias_note} - {primary.get('display', '?')} "
                f"({ref}{idnote}, '{primary.get('basis', '')}')")
    seg = (f"{primary.get('display', '?')} ({ref}{idnote}, column "
           f"{primary.get('col', '')} '{primary.get('basis', '')}'")
    # Keep distinct (col, basis) even when displays are equal: same value
    # in two bases (e.g. List Price vs List Price_2, or PRICE blank vs
    # U.S. LIST blank) is still two labeled facts, not one. Dedup only
    # exact (col, basis, display) repeats (the compat path repeats the
    # same pair once per citation).
    seen_pairs, alts = set(), []
    seen_pairs.add((primary.get("col"), primary.get("basis"),
                    primary.get("display")))
    for v in selected[1:]:
        key = (v.get("col"), v.get("basis"), v.get("display"))
        if key not in seen_pairs:
            seen_pairs.add(key)
            alts.append(v)
    if alts:
        seg += "; also " + ", ".join(
            f"{v['col']} '{v['basis']}' {v['display']}" for v in alts)
    seg += ")"
    return f"- **{item}**{alias_note} - {seg}"


# ---------------------------------------------------------------------------
# Compatibility adapter (labeled): legacy rendered text -> contract.
# Validates presentation behavior over records that stored only text; it
# CANNOT validate the artifact-native path and is not evidence reconstruction.
# LIMITATION: it merges citations by row ref — valid ONLY where the artifact
# establishes one product identity per row; the artifact-native path carries
# distinct variants explicitly and never merges them here.
# ---------------------------------------------------------------------------

def _row_key(sheet: str, cell: str) -> str:
    """Row identity for the compat adapter: same sheet + same row number
    is one candidate. Multiple matching CELLS in one row must not become
    multiple candidates (the 381/622 failure: A88/B88/L88 are one row)."""
    m = re.search(r"(\d+)", cell or "")
    row = m.group(1) if m else (cell or "?")
    return f"{(sheet or '?').strip()}!R{row}"


def present_from_rendered_text(reply: str, *, ask: str, source: Dict[str, Any],
                               requested_items: Optional[List[str]] = None,
                               evidence_revision: str = "legacy-text") -> Dict[str, Any]:
    rows = parse_item_table(reply)
    if not rows:
        raise ValueError("no per-item table found in legacy text")
    items = requested_items or extract_requested_order(ask)
    targets: List[Dict[str, Any]] = []
    for r in rows:
        # Per-segment parsing: each " ; "-separated evidence segment cites
        # one match cell with ITS OWN values, so per-row values stay
        # attributed to their row instead of flattening across candidates.
        row_values: Dict[str, List[Dict[str, Any]]] = {}
        row_seen: Dict[str, set] = {}
        for seg in str(r.get("evidence", "")).split(" ; "):
            cites = [(m.group(1).strip(), m.group(2))
                     for m in _CITE_RE.finditer(seg)]
            if not cites:
                continue
            pairs = [{"col": m.group(1), "raw": m.group(2),
                      "basis": m.group(3).strip()}
                     for m in _PAIR_RE.finditer(seg)]
            seg_values = []
            for p in pairs:
                tv = typed_value(p["raw"])
                seg_values.append(
                    {"col": p["col"], "basis": p["basis"], **tv})
            for sheet, cell in cites:
                rk = _row_key(sheet, cell)
                grp = row_values.setdefault(rk, [])
                seen = row_seen.setdefault(rk, set())
                for v in seg_values:
                    vk = (v.get("col"), v.get("basis"), v.get("display"))
                    if vk not in seen:
                        seen.add(vk)
                        grp.append(v)
        candidates = [{"ref": rk, "values": vals}
                      for rk, vals in row_values.items()]
        values, seen_vals = [], set()
        for vals in row_values.values():
            for v in vals:
                vk = (v.get("col"), v.get("basis"), v.get("display"))
                if vk not in seen_vals:
                    seen_vals.add(vk)
                    values.append(v)
        status = (r.get("status") or "").upper()
        # Identity from ROWS, not cells: several cells in one row = one
        # candidate. AMBIG status with a single row means the field (not
        # the product) is unresolved — keep single identity so the
        # renderer shows competing bases instead of a false multi-row
        # ambiguity.
        identity_status = (
            "none" if ("NOT FOUND" in status or "ABSENT" in status)
            else "multiple" if len(candidates) > 1
            else "single")
        targets.append({
            "item": r.get("target", ""),
            "aliases": [],
            "identity": {"status": identity_status,
                         "candidates": candidates},
            "field": {"status": ("competing" if len({v.get("basis") for v in values}) > 1
                                 else "single" if values else "absent"),
                      "values": values},
        })
    # One entry per REQUESTED item: merge every legacy row matching the
    # same requested item (alias duplicates like 1624 / TK 1624) into one
    # target with combined row-candidates. Matching is strict subsumption
    # (never substring): unresolved correspondence stays unresolved, and
    # legacy rows matching NO requested item (e.g. contamination from
    # earlier email prices) are excluded — they must not become extra
    # top-level entries.
    matched: List[Dict[str, Any]] = []
    for item in items:
        hits = [t for t in targets
                if _subsumes(item, str(t.get("item") or ""))
                or _norm(t.get("item", "")) == _norm(item)]
        if not hits:
            continue  # present() renders the no-result line from items
        cand_seen, cand_all, v_seen, v_all = set(), [], set(), []
        for h in hits:
            for c in (h.get("identity") or {}).get("candidates") or []:
                if c.get("ref") in cand_seen:
                    continue
                cand_seen.add(c.get("ref"))
                # Carry IDENTITY through the alias merge. This rebuild used
                # to copy only ref+values, which is where the matched cell
                # disappeared: the per-target build bound it correctly, the
                # consolidation step then dropped it on the floor, and every
                # target came back identity-unbound with no error anywhere.
                _merged_identity = copy.deepcopy(
                    c.get("identity") or _identity_block([]))
                # Two alias spellings of one item can each contribute a
                # reference; keep every distinct cell rather than first-wins.
                for _other in (h.get("identity") or {}).get(
                        "candidates") or []:
                    if _other.get("ref") != c.get("ref"):
                        continue
                    for _ref in ((_other.get("identity") or {}).get(
                            "references") or []):
                        _cell = str((_ref or {}).get("cell") or "").upper()
                        if not _cell:
                            continue
                        if _cell not in {r.get("cell") for r in
                                         _merged_identity["references"]}:
                            _merged_identity["references"].append(
                                copy.deepcopy(_ref))
                if _merged_identity["references"]:
                    _merged_identity["status"] = IDENTITY_BOUND
                cand_all.append(
                    {"ref": c.get("ref"),
                     "values": list(c.get("values") or []),
                     "identity": _merged_identity})
            for v in (h.get("field") or {}).get("values") or []:
                vk = (v.get("col"), v.get("basis"), v.get("display"))
                if vk not in v_seen:
                    v_seen.add(vk)
                    v_all.append(v)
        bases = {v.get("basis") for v in v_all}
        exact = next((h for h in hits if _norm(h.get("item", "")) == _norm(item)), None)
        best_label = (exact or hits[0]).get("item", "")
        alias_note = [] if _norm(best_label) == _norm(item) else [best_label]
        matched.append({
            "item": item,
            "aliases": alias_note,
            "identity": {"status": ("none" if not cand_all
                                    else "multiple" if len(cand_all) > 1
                                    else "single"),
                         "candidates": cand_all},
            "field": {"status": ("competing" if len(bases) > 1
                                 else "single" if v_all else "absent"),
                      "values": v_all},
        })
    return present(requested_items=items, requested_fields=["price"],
                   source=source, targets=matched,
                   evidence_revision=evidence_revision)


def parse_item_table(reply: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for line in (reply or "").splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.count("|") >= 3):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or not cells[0] or set(cells[0]) <= {"-", ":", " "}:
            continue
        if _norm(cells[0]) in ("item", "machine", "target"):
            continue
        rows.append({"target": cells[0], "status": cells[1],
                     "evidence": "|".join(cells[2:])})
    return rows


def extract_requested_order(ask: str) -> List[str]:
    t = ask or ""
    seg = t.rsplit(":", 1)[-1] if ":" in t else t
    parts = re.split(r",|\band\b", seg)
    items = [p.strip(" .") for p in parts if len(p.strip(" .")) >= 2]
    return items[:12]


# ---------------------------------------------------------------------------
# Requested-item authority: the extractor fans one request out into raw
# tokens (regex numerics like "1624" plus list-phrase items like
# "TK 1624"; right-tail variants like "Manual Flanger" alongside
# "TK Manual Flanger"). The PRESENTED list must be the resolved machines,
# not the raw probe tokens. Consolidation keeps the longer (more specific)
# form and preserves first-appearance order.
# ---------------------------------------------------------------------------

def _item_tokens(text: str) -> List[str]:
    return [t for t in _norm(text).split(" ") if t]


def _subsumes(keeper: str, other: str) -> bool:
    """Does resolved item `keeper` cover raw token `other` (keep keeper)?"""
    kn, on = _norm(keeper), _norm(other)
    if not kn or not on:
        return False
    if kn == on:
        return True
    kt, ot = _item_tokens(keeper), _item_tokens(other)
    if len(ot) < len(kt) and kt[-len(ot):] == ot:
        # Right-tail alias: "Manual Flanger" rides "TK Manual Flanger".
        # Pure-numeric tails never alias on their own ("381" stays exact)
        # unless the keeper carries them as a standalone token.
        if len(ot) >= 2 or not re.fullmatch(r"[0-9]+", ot[0] if ot else ""):
            return True
        return ot[0] in kt
    if re.fullmatch(r"[0-9]+", on.replace(" ", "")) and len(kt) > len(ot):
        # Bare number inside a longer model code: "1624" in "TK 1624".
        # The digits must appear as a standalone token of the keeper so
        # "381" never swallows "381mm".
        compact_other = on.replace(" ", "")
        return compact_other in kt
    return False


def resolve_requested_items(tokens: List[str],
                              order_hint: Optional[str] = None) -> List[str]:
    """Consolidate raw probe tokens into the resolved ordered request list.

    Survivors keep first-appearance order; when ``order_hint`` (the asking
    turn's text) is given, survivors sort by first occurrence there, so
    presentation follows the REQUESTED order rather than lane-assembly
    order (regex hits otherwise precede multi-word names found later).
    Distinct models never merge; replacement keeps the earliest slot.
    """
    resolved: List[str] = []
    for token in tokens or []:
        text = str(token or "").strip()
        if not text:
            continue
        if any(_subsumes(kept, text) for kept in resolved):
            continue
        drop = [kept for kept in resolved if _subsumes(text, kept)]
        if drop:
            idx = resolved.index(drop[0])
            for d in drop:
                resolved.remove(d)
            resolved.insert(idx, text)
        else:
            resolved.append(text)
    if order_hint:
        hay = _norm(order_hint)
        positions = []
        for i, item in enumerate(resolved):
            key = _norm(item)
            at = hay.find(key) if key else -1
            positions.append((at if at >= 0 else 10 ** 9, i, item))
        resolved = [item for _, _, item in sorted(positions)]
    return resolved


def build_targets_from_scan(
    resolved_items: List[str],
    artifact_outcomes: Dict[str, Any],
    per_item: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Artifact-native targets for the presentation contract.

    Row grouping assumes ONE product identity per (sheet, row): several
    matching cells in the same row are one candidate; distinct rows stay
    distinct candidates and are never merged. That assumption is valid
    for price-list sheets where each row is one model; it is stated here
    (and in the compat adapter) rather than hidden in grouping code.
    """
    per_item = per_item or {}
    raw_tokens = list((artifact_outcomes or {}).keys()) + [
        k for k in per_item.keys() if k not in (artifact_outcomes or {})]
    targets: List[Dict[str, Any]] = []
    for item in resolved_items or []:
        owned = [t for t in raw_tokens if _subsumes(item, str(t))]
        row_groups: Dict[str, Dict[str, Any]] = {}
        aliases: List[str] = []
        for raw in owned:
            outcome = (artifact_outcomes or {}).get(raw)
            if isinstance(outcome, dict):
                for ev in outcome.get("evidence") or []:
                    if not isinstance(ev, dict):
                        continue
                    sheet = str(ev.get("sheet") or "?").strip()
                    row = ev.get("row")
                    key = f"{sheet}!R{row}"
                    grp = row_groups.get(key)
                    if grp is None:
                        grp = {"ref": key, "values": [], "seen": set(),
                               "identity": _identity_block([])}
                        row_groups[key] = grp
                    _idref = _identity_reference(ev, sheet, row)
                    if _idref is not None:
                        grp["identity"]["references"].append(_idref)
                        grp["identity"]["status"] = IDENTITY_BOUND
                    for v in ev.get("values") or ev.get("prices") or []:
                        if not isinstance(v, dict):
                            continue
                        basis = str(v.get("price_basis") or v.get("field")
                                    or v.get("column") or "value")
                        col = str(v.get("cell") or "")
                        tv = typed_value(v.get("value"))
                        vk = (col, basis, tv.get("display"))
                        if vk not in grp["seen"]:
                            grp["seen"].add(vk)
                            grp["values"].append(
                                {"col": col, "basis": basis, **tv})
                    alias = ev.get("matched_alias")
                    if alias and str(alias) not in aliases:
                        aliases.append(str(alias))
                continue
            record = per_item.get(raw)
            if isinstance(record, dict):
                columns = list(record.get("columns") or [])
                letters = record.get("column_letters") or {}
                rows = record.get("rows") or []
                if rows:
                    row0 = rows[0]
                    rn = (row0.get("__sheet_row") or row0.get("__row__")
                          or "?")
                    sheet = str(record.get("entity_name") or "?").strip()
                    key = f"{sheet}!R{rn}"
                    grp = row_groups.get(key)
                    if grp is None:
                        grp = {"ref": key, "values": [], "seen": set(),
                               "identity": _identity_block([])}
                        row_groups[key] = grp
                    # The content probe records the exact cells whose text
                    # matched, so identity is bound to a real coordinate
                    # rather than left unverified. A record WITHOUT them
                    # keeps the explicit unverified status.
                    for _m in (record.get("matched_cells") or []):
                        if not isinstance(_m, dict):
                            continue
                        _coord = str(_m.get("cell") or "").strip().upper()
                        if not re.match(r"^[A-Z]{1,3}\d{1,7}$", _coord):
                            continue
                        if _coord not in {r["cell"] for r in
                                          grp["identity"]["references"]}:
                            grp["identity"]["references"].append({
                                "sheet": sheet,
                                "cell": _coord,
                                "row": rn,
                                "value": str(_m.get("value") or "") or None,
                                "role": "matched_target",
                            })
                            grp["identity"]["status"] = IDENTITY_BOUND
                    for column in columns:
                        if not re.search(
                                r"price|cost|amount|rate|value|list|total|dealer",
                                str(column), re.IGNORECASE):
                            continue
                        letter = letters.get(column)
                        if not letter:
                            continue
                        col = f"{letter}{rn}"
                        tv = typed_value(row0.get(column))
                        vk = (col, str(column), tv.get("display"))
                        if vk not in grp["seen"]:
                            grp["seen"].add(vk)
                            grp["values"].append(
                                {"col": col, "basis": str(column), **tv})
        candidates = [{"ref": g["ref"], "values": list(g["values"]),
                       "identity": copy.deepcopy(
                           g.get("identity") or _identity_block([]))}
                      for g in row_groups.values()]
        values: List[Dict[str, Any]] = []
        for g in row_groups.values():
            values.extend(g["values"])
        bases = {v.get("basis") for v in values}
        # Normalise identity references after the consolidation: several
        # alias spellings can each contribute the same coordinate, so they
        # are deduplicated by cell at ONE point here rather than at each
        # append — correct regardless of how many spellings merged.
        for _c in candidates:
            _idn = _c.get("identity") or _identity_block([])
            _seen_cells, _uniq = set(), []
            for _r in _idn.get("references") or []:
                _cell = str((_r or {}).get("cell") or "").upper()
                if not _cell or _cell in _seen_cells:
                    continue
                _seen_cells.add(_cell)
                _uniq.append(_r)
            _idn["references"] = _uniq
            _idn["status"] = IDENTITY_BOUND if _uniq else IDENTITY_UNVERIFIED
            _c["identity"] = _idn
        targets.append({
            "item": item,
            "aliases": [a for a in aliases
                        if _norm(a) != _norm(item)][:3],
            "identity": {"status": ("none" if not candidates
                                    else "multiple" if len(candidates) > 1
                                    else "single"),
                         "candidates": candidates},
            "field": {"status": ("competing" if len(bases) > 1
                                 else "single" if values else "absent"),
                      "values": values},
        })
    return targets


# ---------------------------------------------------------------------------
# Slice 2: versioned structured-result persistence + attempt identities +
# explicit presentation intent carried through the existing continuation
# mechanism (pending-task metadata) — consumed by ALL presentation sites,
# never re-inferred independently at each one.
# ---------------------------------------------------------------------------

STRUCTURED_RESULT_SCHEMA = "structured-result-2"
STRUCTURED_RESULT_SCHEMA_PREVIOUS = ("structured-result-1",)


# ---------------------------------------------------------------------------
# IDENTITY EVIDENCE (contract v2)
#
# A candidate's ``ref`` is a ROW LOCATOR ("LINMAC!R26"). That is useful for
# display and completely insufficient for proof: a row can hold several
# prices, and nothing in "R26" says which cell the requested identity was
# matched in, nor what was read there. Equally, the label cell alone does
# not prove a price. Identity and value are SEPARATE bindings and are now
# carried separately.
#
# The scan already knows the exact matched coordinate — it is
# ``evidence[hit]["cell"]`` — and it was being dropped when candidates were
# grouped by row. It is preserved here instead.
#
# Nothing is inferred. Where the source does not establish an identity
# coordinate (the legacy row record, the rendered-text compat adapter),
# the binding is reported UNVERIFIED with no references rather than
# reconstructed from a row number or assumed to be column A: models,
# descriptions, aliases and merged labels all live in different cells.
# ---------------------------------------------------------------------------

IDENTITY_BOUND = "bound"
IDENTITY_UNVERIFIED = "unverified"


def _identity_reference(ev: Dict[str, Any], sheet: str, row: Any,
                        role: str = "matched_target") -> Optional[Dict[str, Any]]:
    """One exact identity reference from a scan evidence record, or None
    when the record carries no matched coordinate."""
    cell = str(ev.get("cell") or "").strip()
    if not cell or not re.match(r"^[A-Z]{1,3}\d{1,7}$", cell.upper()):
        return None
    return {
        "sheet": sheet,
        "cell": cell.upper(),
        "row": row,
        "value": str(ev.get("value") or "").strip() or None,
        "role": role,
    }


def _identity_block(refs: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "status": IDENTITY_BOUND if refs else IDENTITY_UNVERIFIED,
        "references": list(refs),
    }


def new_attempt_id() -> str:
    """A NEW search attempt gets a NEW attempt identity, even when its
    evidence revision is unchanged (same copy re-read)."""
    import uuid
    return f"attempt-{uuid.uuid4()}"


EVIDENCE_ACTIONS = ("new_read", "read_failed", "reused", "unverified")


def build_structured_record(*, source_identity: Dict[str, Any],
                            evidence_revision: str,
                            attempt_id: str,
                            evidence_action: str,
                            requested_items: List[str],
                            requested_fields: List[str],
                            targets: List[Dict[str, Any]],
                            coverage: Any,
                            retrieved_at: Optional[float] = None) -> Dict[str, Any]:
    """The versioned structured artifact to persist beside (not instead of)
    the rendered text. evidence_action is EVIDENCE-BASED: the caller stamps
    what actually happened (retrieval completed / failed / reused cache) —
    creating a record or minting an attempt id establishes nothing."""
    import time as _t
    if evidence_action not in EVIDENCE_ACTIONS:
        raise ValueError(f"evidence_action must be one of {EVIDENCE_ACTIONS}")
    return {
        "schema_version": STRUCTURED_RESULT_SCHEMA,
        "source_identity": dict(source_identity or {}),
        "evidence_revision": evidence_revision,
        "attempt_id": attempt_id,
        "evidence_action": evidence_action,
        "retrieved_at": retrieved_at if retrieved_at is not None else _t.time(),
        "requested_items": list(requested_items),
        "requested_fields": list(requested_fields),
        "targets": targets,
        "coverage": coverage,
    }


def set_presentation_intent(record: Dict[str, Any],
                            resolved_intent: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """A SEPARATE presentation-action record referencing the original
    retrieval. The intent comes from the EXISTING request/continuation
    mechanism (resolved upstream) — this function classifies nothing and
    NEVER rewrites the original record's evidence history. The original's
    evidence_action and attempt remain the historical facts."""
    if record is None:
        raise ValueError("presentation action requires the original record")
    import time as _t
    intent = dict(resolved_intent or {})
    return {
        "schema_version": "presentation-action-1",
        "action_type": "presentation",
        "action": intent.get("action", "present"),
        "created_at": _t.time(),
        "references_attempt_id": record.get("attempt_id"),
        "references_evidence_revision": record.get("evidence_revision"),
        "referenced_evidence_action": record.get("evidence_action"),
        "intent": intent,
    }


def mark_delivered(record: Dict[str, Any], delivered_answer: str) -> Dict[str, Any]:
    """Pin the DELIVERED answer to the record. Transport retries serve this
    pinned original verbatim — a renderer upgrade must never alter an
    already-delivered answer.

    PIN-AFTER-FINALIZATION (review round 31): the caller MUST pass the
    message as actually DELIVERED — i.e. AFTER the finalization seam
    (failure correction, claim reconciliation) — never the renderer's
    intermediate output. Pinning an intermediate would make transport
    retries disagree with the response the user originally received."""
    import hashlib as _h
    import time as _t
    out = dict(record)
    out["delivery_pin"] = {
        "delivered_at": _t.time(),
        "delivered_answer_sha256": _h.sha256(delivered_answer.encode()).hexdigest(),
        "delivered_text": delivered_answer,
    }
    return out


def serve_on_transport_retry(record: Dict[str, Any]) -> Optional[str]:
    """Transport retry: return the PINNED delivered answer verbatim, or None
    when nothing was delivered (the caller then follows its normal path)."""
    pin = (record or {}).get("delivery_pin")
    return pin.get("delivered_text") if pin else None


def present_from_record(record: Dict[str, Any],
                        presentation_intent: Optional[Dict[str, Any]] = None,
                        presentation_action: Optional[Dict[str, Any]] = None,
                        style: Optional[str] = None,
                        field: Optional[str] = None
                        ) -> Dict[str, Any]:
    """The artifact-native path: render from a PERSISTED structured record.
    Retries and reloads use the SAME renderer via this entry point.
    presentation_action (from set_presentation_intent) supplies the carried
    intent and keeps the ORIGINAL attempt/revision as references. Style and
    field preferences ride the intent (explicit params win, then the
    action's intent, then the bare intent): preferences visibly change the
    rendering — an action record alone never counts as honoring them. A
    read_failed record is delivered as an honest failed-retrieval outcome —
    never rendered as if it were evidence."""
    if record.get("evidence_action") == "read_failed":
        return {"answer": ("The search attempt did not complete, so no fresh "
                           "evidence is available from it. The earlier saved "
                           "results remain unchanged."),
                "presentation_version": PRESENTATION_VERSION,
                "evidence_revision": record.get("evidence_revision"),
                "attempt_id": record.get("attempt_id"),
                "evidence_action": "read_failed"}
    if record.get("evidence_action") == "unverified":
        return {"answer": ("The search status could not be verified — no "
                           "retrieval was observed for this attempt — so no "
                           "values are reported from it."),
                "presentation_version": PRESENTATION_VERSION,
                "evidence_revision": record.get("evidence_revision"),
                "attempt_id": record.get("attempt_id"),
                "evidence_action": "unverified"}
    if presentation_action is not None:
        presentation_intent = presentation_action.get("intent") or presentation_intent
    intent = presentation_intent or {}
    resolved_style = style or intent.get("style") or "default"
    if resolved_style not in ("default", "compact", "table"):
        resolved_style = "default"
    resolved_field = field or intent.get("field")
    src_id = record.get("source_identity") or {}
    saved = src_id.get("ingested_at") or src_id.get("saved_copy_date")
    result = present(
        requested_items=record.get("requested_items") or [],
        requested_fields=record.get("requested_fields") or ["price"],
        source={"file_name": src_id.get("file_name"),
                "saved_copy_date": saved,
                "live_vs_saved": src_id.get("live_vs_saved") or "saved copy",
                "coverage": record.get("coverage")},
        targets=record.get("targets") or [],
        evidence_revision=str(record.get("evidence_revision") or ""),
        style=resolved_style, field=resolved_field)
    result["attempt_id"] = record.get("attempt_id")
    result["evidence_action"] = record.get("evidence_action")
    result["presentation_intent"] = presentation_intent or record.get("presentation_intent")
    result["presentation_style"] = resolved_style
    result["presentation_field"] = resolved_field
    if presentation_action is not None:
        result["presentation_action"] = {
            "action_type": "presentation",
            "references_attempt_id": presentation_action.get("references_attempt_id"),
            "references_evidence_revision": presentation_action.get("references_evidence_revision"),
        }
        # the referenced originals are the historical facts
        result["attempt_id"] = presentation_action.get("references_attempt_id")
        result["evidence_revision"] = presentation_action.get("references_evidence_revision")
    return result
