"""Phase 1 -- independent per-item evidence checklist.

Reads the MATERIALIZED COPY of the workbook (the per-sheet parquet datasets the
index actually serves) and, for each requested label, records every identity
candidate it finds, with identity cell coordinates, value cell coordinates, the
original column/basis label, the raw typed value, the displayed value and any
explicitly recorded currency/unit.

This is deliberately NOT the application's answer and NOT any older report: the
expected values below are derived only from these files, so the app's later
answer can be checked against them.

Nothing here is wired into production routing. The eight labels are test data.

Usage:
  backend/venv314/bin/python phase1_evidence.py --dataset-dir <path> --out <dir>
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import pandas as pd

#: The authoritative ordered request (fixture data, never production routing).
REQUESTED = [
    "No. 381",
    "U-22",
    "No. 622",
    "TK Manual Flanger",
    "SLE24-16",
    "TK 1624",
    "TK Multi Wheel Gang Slitter",
    "GSL48-16",
]

#: Historical distractors. These are NOT substitutes for the eight above; they
#: are searched here only to prove the distinction and to show what an alias
#: probe would wrongly pull in.
DISTRACTORS = ["GSL24-16", "SLE16-8", "U-38", "Manual Flanger", "1624",
               "Multi Wheel Gang Slitter"]

#: Column headers that carry a money/cost meaning. Used only to decide which
#: numeric cells are worth quoting; the header is ALWAYS reported verbatim.
PRICE_HEADER = re.compile(
    r"price|cost|list|amount|value|freight|landed|net|mult|exchange|profit|"
    r"margin|factor|qps|dollar|usd|cad|cdn",
    re.I,
)

#: Only the injected sheet-row column is structural. Unnamed source columns
#: (c1, c3, ...) are NOT skipped: on several sheets the model number lives in
#: one of them, so dropping them would hide the real identity cell.
STRUCTURAL = re.compile(r"^__sheet_row$", re.I)


def col_letter(index: int) -> str:
    """0-based column index -> Excel column letter."""
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def norm(text) -> str:
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return ""
    s = str(text).lower().replace("–", "-").replace("—", "-")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(text) -> list[str]:
    n = norm(text)
    return n.split(" ") if n else []


def cell_ref(row: int, col: str) -> str:
    return f"{col}{row}"


def as_display(value):
    """Raw typed value -> what a spreadsheet would show.

    Blank, zero, NaN and 'not a number' are four different things and are kept
    apart on purpose.
    """
    if value is None:
        return {"raw": None, "state": "blank"}
    if isinstance(value, float):
        if math.isnan(value):
            return {"raw": "nan", "state": "nan"}
        if value == 0:
            return {"raw": value, "state": "zero"}
        return {"raw": value, "state": "number",
                "displayed": f"{value:,.2f}".rstrip("0").rstrip(".") if abs(value) < 1e15 else str(value)}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"raw": value, "state": "number", "displayed": f"{value:,}"}
    text = str(value).strip()
    if text == "":
        return {"raw": "", "state": "blank"}
    return {"raw": text, "state": "text", "displayed": text}


def probe_keys(label: str) -> list[tuple[str, str]]:
    """(probe, kind) pairs for one requested label.

    exact  -- the probe equals a cell, compared on normalized text
    subseq -- the probe's tokens appear as a contiguous run inside a cell
    loose  -- every probe token appears in the cell in any order (only used to
              ENUMERATE unresolved candidates; never to pick a value)

    "No. 381" is a request for model NUMBER 381: "No." is the request's own
    syntax, so the bare number is probed too. That is parsing the ask, not a
    product-name rule.

    Alias probes (a fragment such as 'Gang Slitter') are deliberately NOT
    generated: they are how a historical answer pulled an unrelated row in.
    """
    t = tokens(label)
    out = [(label, "exact")]
    if len(t) > 1:
        out.append((" ".join(t), "subseq"))
    if t and t[0] in ("no", "number") and len(t) > 1:
        out.append((" ".join(t[1:]), "exact"))
        if len(t) > 2:
            out.append((" ".join(t[1:]), "subseq"))
    return out


def loose_hits(label: str, row: dict) -> list[dict]:
    """Rows that share tokens with the label without containing it in order.

    Reported separately: these are UNRESOLVED candidates, and a name like
    "TK Multi Wheel Gang Slitter" has to be settled by a human, not by picking
    the first row that looks similar.
    """
    t = [x for x in tokens(label) if x not in ("no", "number")]
    if len(t) < 2:
        return []
    out = []
    for letter, name, value in row["cells"]:
        if STRUCTURAL.match(str(name)):
            continue
        ctoks = set(tokens(value))
        shared = [x for x in t if x in ctoks]
        if shared and shared != t:
            out.append({"shared_tokens": shared, "cell": cell_ref(row["sheet_row"], letter),
                        "column": str(name), "cell_text": str(value)[:80]})
    return out


def scan(dataset_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(dataset_dir.glob("*.parquet")):
        sheet = path.stem.split("__")[-1]
        frame = pd.read_parquet(path)
        cols = [c for c in frame.columns if c != "__sheet_row"]
        for _, row in frame.iterrows():
            sheet_row = row.get("__sheet_row")
            cells = []
            for idx, name in enumerate(cols):
                cells.append((col_letter(idx), name, row.get(name)))
            rows.append({"sheet": sheet, "sheet_row": int(sheet_row), "cells": cells})
    return rows


def match_row(label: str, row: dict) -> list[dict]:
    """Identity cells in this row that match the label (identity != value)."""
    hits = []
    for probe, kind in probe_keys(label):
        ptoks = tokens(probe)
        if not ptoks:
            continue
        for letter, name, value in row["cells"]:
            if STRUCTURAL.match(str(name)):
                continue
            ctoks = tokens(value)
            if not ctoks:
                continue
            if kind == "exact" and norm(value) == norm(probe):
                hits.append({"probe": probe, "match": "exact", "cell": cell_ref(row["sheet_row"], letter),
                             "column": name, "cell_text": str(value)})
            elif kind == "subseq" and len(ptoks) <= len(ctoks):
                for i in range(len(ctoks) - len(ptoks) + 1):
                    if ctoks[i:i + len(ptoks)] == ptoks:
                        hits.append({"probe": probe, "match": "token_subsequence",
                                     "cell": cell_ref(row["sheet_row"], letter),
                                     "column": name, "cell_text": str(value)})
                        break
    return hits


def alias_hits(label: str, row: dict) -> list[dict]:
    """What a FRAGMENT probe would match -- the distractor-union mechanism."""
    t = [x for x in tokens(label) if x not in ("tk", "no")]
    if len(t) < 2:
        return []
    probe = " ".join(t)
    out = []
    for letter, name, value in row["cells"]:
        if STRUCTURAL.match(str(name)):
            continue
        if probe in norm(value):
            out.append({"probe": probe, "cell": cell_ref(row["sheet_row"], letter),
                        "column": name, "cell_text": str(value)})
    return out


def value_cells(row: dict) -> list[dict]:
    out = []
    for letter, name, value in row["cells"]:
        if STRUCTURAL.match(str(name)):
            continue
        info = as_display(value)
        if info["state"] in ("blank", "text"):
            continue
        out.append({"cell": cell_ref(row["sheet_row"], letter), "column": name,
                    "basis_verbatim": str(name), "is_money_header": bool(PRICE_HEADER.search(str(name))),
                    **info})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    dataset_dir = Path(args.dataset_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = scan(dataset_dir)
    print(f"scanned {len(rows)} rows across {len(list(dataset_dir.glob('*.parquet')))} sheets")

    report = {"dataset_dir": str(dataset_dir), "rows_scanned": len(rows),
              "sheets": sorted({r["sheet"] for r in rows}), "items": []}

    for label in REQUESTED:
        exact, alias, loose = [], [], []
        for row in rows:
            for hit in match_row(label, row):
                exact.append({**hit, "sheet": row["sheet"], "sheet_row": row["sheet_row"],
                              "values": value_cells(row)})
            for hit in alias_hits(label, row):
                alias.append({**hit, "sheet": row["sheet"], "sheet_row": row["sheet_row"]})
            if not any(match_row(label, row)):
                for hit in loose_hits(label, row):
                    loose.append({**hit, "sheet": row["sheet"], "sheet_row": row["sheet_row"]})
        rows_matched = {(c["sheet"], c["sheet_row"]) for c in exact}
        item = {"requested_label": label,
                "identity_candidates": exact,
                "distinct_rows": sorted([f"{s}!{r}" for s, r in rows_matched]),
                "ambiguity": len(rows_matched) > 1,
                "identity_resolved": len(rows_matched) == 1,
                "unresolved_candidates": loose[:20],
                "fragment_probe_would_also_match": [
                    {"probe": a["probe"], "sheet": a["sheet"], "cell": a["cell"],
                     "column": a["column"], "cell_text": a["cell_text"]}
                    for a in alias if (a["sheet"], a["sheet_row"]) not in rows_matched
                ]}
        report["items"].append(item)
        print(f"  {label:32s} rows={len(rows_matched):2d} {sorted(rows_matched)} "
              f"unresolved={len(loose)}")

    distractor = []
    for label in DISTRACTORS:
        found = [(row["sheet"], row["sheet_row"], h["cell"], h["cell_text"])
                 for row in rows for h in match_row(label, row)]
        distractor.append({"label": label, "matches": found[:12], "match_count": len(found)})
        print(f"  [distractor] {label:28s} matches={len(found)}")
    report["distractors"] = distractor

    (out_dir / "evidence_checklist.json").write_text(json.dumps(report, indent=2))
    print(f"wrote {out_dir / 'evidence_checklist.json'}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
