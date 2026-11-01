#!/usr/bin/env python3
"""Part A — current-candidate Microsoft read-only qualification.

Uses the normal product token resolver and sheet-materialization service, then
the ordinary assignment API. It never logs or stores the access token, never
writes to the source, and stops on identity/hash/result mismatch.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import sqlite3
import time
import urllib.request
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import httpx
import openpyxl

from integrations.onedrive_service import OneDriveService


GRAPH = "https://graph.microsoft.com/v1.0"
ACCOUNT = "rish@brennan.ca"
TENANT = "8899c7a5-b671-4f16-bb48-15d5e78158af"
EXPECTED_SHA1 = "e0a7fb8a1b4757b7f6bef882b19cc4588d66246e"
EXPECTED_SHA256 = "5cd746af2c46dfe3979b1881cb8623dff149958b4cadd97bd69da1e489c9dcb4"
EXPECTED_ROWS = 8
EXPECTED_SUM = Decimal("216700")
SHEET = "库存产品"


def api_call(base: str, path: str, token: str | None = None, body=None, method="GET"):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{base}{path}", data=data,
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode() or "{}")


def login(base: str, password: str) -> str:
    return api_call(base, "/api/auth/login",
                    body={"username": "admin@example.com", "password": password},
                    method="POST")["access_token"]


def graph_get(client: httpx.Client, token: str, path: str) -> httpx.Response:
    response = client.get(f"{GRAPH}{path}",
                          headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    return response


def parse_workbook(content: bytes) -> dict:
    wb = openpyxl.load_workbook(BytesIO(content), data_only=True)
    if SHEET not in wb.sheetnames:
        raise SystemExit(f"REFUSED: sheet {SHEET!r} not found; sheets={wb.sheetnames}")
    ws = wb[SHEET]
    header = None
    for row in ws.iter_rows():
        for cell in row:
            if str(cell.value or "").strip().casefold() == "price":
                header = cell
                break
        if header:
            break
    if header is None:
        raise SystemExit("REFUSED: Price header not found")
    values = []
    for row in ws.iter_rows(min_row=header.row + 1, min_col=header.column,
                            max_col=header.column):
        value = row[0].value
        if value is None or str(value).strip() == "":
            continue
        try:
            values.append(Decimal(str(value).replace(",", "")))
        except Exception:
            continue
    return {
        "sheet": SHEET,
        "sheets": wb.sheetnames,
        "header_cell": header.coordinate,
        "price_values": [str(v) for v in values],
        "rows_with_price": len(values),
        "sum": str(sum(values)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-base", default="http://127.0.0.1:8071")
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--db", required=True)
    args = ap.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    password = Path(args.password_file).read_text().strip()
    checks = []

    def record(name, ok, detail=None):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name, detail or "")

    user_id = "b83eb105-d9e7-41a5-83e3-a632b15b9ee3"
    service = OneDriveService()
    token, resolution = asyncio.run(service.get_access_token_resolution(user_id))
    record("normal token resolver returned a usable grant", bool(token)
           and resolution.get("token_available") is True, resolution)
    if not token:
        (out / "result.json").write_text(json.dumps({
            "schema": "atom-live-qualification-a-1",
            "checks": checks, "passed": False,
        }, indent=2) + "\n")
        return 1

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "select id,source,external_id,file_name,content_hash,dataset_name,entity_name,"
        "row_count,column_count,parquet_path,status from dataset_entries "
        "where file_name like '%HARSLE%' and status='active'").fetchone()
    if not row:
        record("catalog source exists", False)
        return 1
    source = dict(row)
    message_id, attachment_id = source["external_id"].split(":", 1)
    record("catalog source resolved without seeding", True,
           {"entry": source["id"], "dataset": source["dataset_name"]})

    # The copied qualification world initially inherited a catalog pointer to
    # the live world's dataset store. It is a stale pointer, not an ingest.
    # Mark only that copied row superseded so the genuine bytes below are
    # re-materialized by the product into THIS world's store.
    store_root = Path(os.environ["ATOM_DATA_DIR"]).resolve()
    old_parquet = Path(source["parquet_path"] or "").resolve()
    if not str(old_parquet).startswith(str(store_root) + os.sep):
        con.execute(
            "update dataset_entries set status='superseded' where id=?",
            (source["id"],))
        con.commit()
        (out / "superseded-catalog-pointer.json").write_text(json.dumps({
            "entry": source["id"],
            "old_parquet": str(old_parquet),
            "reason": "copied catalog pointer outside this world's dataset store; "
                      "genuine bytes re-materialized through the product",
        }, indent=2) + "\n")
        record("stale copied catalog pointer marked superseded", True,
               {"entry": source["id"]})

    with httpx.Client(timeout=120, follow_redirects=True) as client:
        me = graph_get(client, token, "/me?$select=id,userPrincipalName,mail,displayName").json()
        record("mailbox identity is the authorized account",
               me.get("userPrincipalName") == ACCOUNT and me.get("mail") == ACCOUNT, me)
        (out / "identity.json").write_text(json.dumps(me, indent=2) + "\n")
        if me.get("userPrincipalName") != ACCOUNT:
            return 1

        mid = quote(message_id, safe="")
        message = graph_get(
            client, token,
            f"/me/messages/{mid}?$select=id,subject,receivedDateTime,hasAttachments",
        ).json()
        attachments = graph_get(
            client, token,
            f"/me/messages/{mid}/attachments?$select=id,name,contentType,size",
        ).json().get("value") or []
        chosen = next(
            (item for item in attachments
             if str(item.get("name") or "") == source["file_name"]), None)
        record("declared attachment is present", chosen is not None,
               {"message": message.get("subject"), "attachments": [
                   {"name": a.get("name"), "size": a.get("size")} for a in attachments]})
        if not chosen:
            return 1
        aid = quote(str(chosen["id"]), safe="")
        response = client.get(
            f"{GRAPH}/me/messages/{mid}/attachments/{aid}/$value",
            headers={"Authorization": f"Bearer {token}"})
        response.raise_for_status()
        content = response.content

    sha1 = hashlib.sha1(content).hexdigest()
    sha256 = hashlib.sha256(content).hexdigest()
    record("source bytes match the frozen version",
           sha1 == EXPECTED_SHA1 and sha256 == EXPECTED_SHA256,
           {"sha1": sha1, "sha256": sha256, "bytes": len(content)})
    if sha1 != EXPECTED_SHA1:
        return 1

    independent = parse_workbook(content)
    record("independent workbook read matches the declared population",
           independent["rows_with_price"] == EXPECTED_ROWS
           and Decimal(independent["sum"]) == EXPECTED_SUM, independent)
    if Decimal(independent["sum"]) != EXPECTED_SUM:
        return 1
    (out / "independent-read.json").write_text(json.dumps({
        "file_name": source["file_name"],
        "message_id": message_id,
        "attachment_id": attachment_id,
        "bytes": len(content),
        "sha1": sha1,
        "sha256": sha256,
        "last_modified": message.get("receivedDateTime"),
        "workbook": independent,
    }, indent=2) + "\n")

    # Product materialization (the same service the ingestion path uses).
    from core.sheet_dataset_service import materialize_sheet_bytes_sync

    materialized = materialize_sheet_bytes_sync(
        content,
        source["file_name"],
        "outlook",
        user_id=user_id,
        workspace_id="default",
        external_id=source["external_id"],
        source_modified_at=datetime.fromisoformat(
            message.get("receivedDateTime", "").replace("Z", "+00:00"))
        if message.get("receivedDateTime") else None,
    )
    datasets = materialized.get("datasets") or []
    sheet_row = next((item for item in datasets
                      if item.get("entity_name") == SHEET), None)
    record("product materialization covers the declared sheet",
           materialized.get("status") in ("current", "materialized")
           and sheet_row is not None
           and int(sheet_row.get("row_count") or 0) == EXPECTED_ROWS
           and int((sheet_row.get("coverage") or {}).get("materialized_row_count") or 0)
           == EXPECTED_ROWS
           and (sheet_row.get("coverage") or {}).get("truncated") is False,
           {"status": materialized.get("status"),
            "datasets": [{"sheet": d.get("entity_name"), "rows": d.get("row_count"),
                          "coverage": d.get("coverage")} for d in datasets]})
    (out / "materialization.json").write_text(json.dumps(materialized, indent=2) + "\n")
    if not sheet_row:
        return 1

    token_api = login(args.api_base, password)
    sources = api_call(args.api_base, "/api/assignments/sources", token_api)
    source_row = next((item for item in sources
                       if item.get("file_name") == source["file_name"]
                       and item.get("sheet") == SHEET), None)
    record("product source picker exposes the materialized sheet", source_row is not None,
           {"dataset_name": source_row.get("dataset_name") if source_row else None,
            "row_count": source_row.get("row_count") if source_row else None})
    if not source_row:
        return 1

    body = {
        "objective": "Read the current HARSLE attachment and sum Price for the complete sheet",
        "agent_id": args.agent_id,
        "sources": [{
            "kind": "workbook",
            "dataset_name": source_row["dataset_name"],
            "source": source_row["source"],
            "external_id": source_row["external_id"],
            "source_version": source_row["source_version"],
            "sheet": source_row["sheet"],
        }],
        "deliverables": [{
            "kind": "document",
            "description": "HARSLE read-only qualification",
            "content": (
                "## Summary\n\nTotal ${source-1.value}\n\n"
                "## Sources\n\n- HARSLE press brake stock price list.xlsx / 库存产品"
            ),
        }],
        "calculation": {"aggregate": {"operation": "sum", "value_column": "Price"}},
    }
    created = api_call(args.api_base, "/api/assignments", token_api, body, "POST")
    run_id = created["run_id"]
    record("assignment created from the product source", True, run_id)
    deadline = time.time() + 180
    detail = None
    while time.time() < deadline:
        detail = api_call(args.api_base, f"/api/assignments/{run_id}", token_api)
        status = (detail.get("assignment") or {}).get("status")
        if status in ("completed", "achieved", "failed", "cancelled", "waiting"):
            break
        time.sleep(2)
    assignment = (detail or {}).get("assignment") or {}
    steps = assignment.get("steps") or []
    source_step = next((step for step in steps if step.get("step_id") == "source-1"), {})
    record("assignment completed the read/calculate", assignment.get("status") in
           ("completed", "achieved"), assignment.get("status"))
    record("assignment result equals the independent sum",
           Decimal(str(source_step.get("result_value") or "0")) == EXPECTED_SUM,
           source_step.get("result_value"))
    record("source receipt binds file, sheet, rows and version",
           "HARSLE" in str(source_step.get("result_summary") or "")
           and SHEET in str(source_step.get("result_summary") or "")
           and "8 row" in str(source_step.get("result_summary") or ""),
           source_step.get("result_summary"))
    (out / "assignment.json").write_text(json.dumps(detail, indent=2) + "\n")
    (out / "result.json").write_text(json.dumps({
        "schema": "atom-live-qualification-a-1",
        "checks": checks,
        "passed": all(item["ok"] for item in checks),
        "run_id": run_id,
        "agent_id": args.agent_id,
        "source": {"dataset_name": source_row["dataset_name"],
                   "sheet": source_row["sheet"],
                   "row_count": source_row["row_count"],
                   "source_version": source_row["source_version"]},
        "independent": independent,
        "materialization_status": materialized.get("status"),
        "serving_identity": api_call(args.api_base, "/health"),
    }, indent=2) + "\n")
    print(json.dumps({"passed": all(item["ok"] for item in checks),
                      "run_id": run_id, "checks": len(checks)}, indent=2))
    return 0 if all(item["ok"] for item in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
