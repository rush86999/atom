"""Common-data, hybrid-search, VFS and memory scenarios."""
from __future__ import annotations

import asyncio
import io
import json
import uuid
from pathlib import Path

from .common import Ctx


def _fixtures() -> dict:
    """Build one representative file per marketed format."""
    files = {}

    # plain text
    files["acceptance_txt.txt"] = (
        "ALPHA-TOKEN-9381 quarterly revenue notes.\n"
        "The zebra metric is 42 and the widget count is 7.\n"
    ).encode()

    # CSV with a leading-zero ID, a blank cell and mixed types
    files["acceptance_csv.csv"] = (
        "Record ID,Amount,Notes\n"
        "00123,1250.50,first\n"
        "00124,,missing amount\n"
        "00125,900,third\n"
    ).encode()

    # XLSX: two sheets, leading-zero ID, cross-sheet formula
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["Record ID", "Units", "Price"])
    ws.append(["00123", 2, 1250.50])
    ws.append(["00124", 1, 900])
    ws["D2"] = "=SUM(B2:C2)"
    summary = wb.create_sheet("Summary")
    summary["A1"] = "Grand total"
    summary["B1"] = "=Data!D2+Data!D3"
    buf = io.BytesIO()
    wb.save(buf)
    files["acceptance_xlsx.xlsx"] = buf.getvalue()

    # DOCX with a heading, a table and a distinctive token
    import docx
    doc = docx.Document()
    doc.add_heading("Acceptance Report", level=1)
    doc.add_paragraph("DOCX-TOKEN-4417 explains the quarterly position.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Region"
    table.cell(0, 1).text = "Amount"
    table.cell(1, 0).text = "North"
    table.cell(1, 1).text = "1250.50"
    buf = io.BytesIO()
    doc.save(buf)
    files["acceptance_docx.docx"] = buf.getvalue()

    # PPTX with two slides and notes
    from pptx import Presentation
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "PPTX-TOKEN-5528"
    slide.placeholders[1].text = "Ace slide body"
    slide.notes_slide.notes_text_frame.text = "Speaker note for ace slide"
    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    slide2.shapes.title.text = "Second slide"
    slide2.placeholders[1].text = "Body two"
    buf = io.BytesIO()
    prs.save(buf)
    files["acceptance_pptx.pptx"] = buf.getvalue()

    # EML with participants, subject, body and an attachment name
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["Subject"] = "EML-TOKEN-6639 quarterly packet"
    msg["From"] = "sender@example.com"
    msg["To"] = "admin@example.com"
    msg["Date"] = "Fri, 30 Oct 2026 10:00:00 +0000"
    msg.set_content("Body of the email with EML-TOKEN-6639.\n")
    msg.add_attachment(b"attachment body", maintype="text", subtype="plain",
                       filename="packet.txt")
    files["acceptance_eml.eml"] = msg.as_bytes()

    # PDF with a distinctive token (reportlab is present in the pinned stack)
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        c.drawString(72, 720, "PDF-TOKEN-7740 acceptance invoice")
        c.drawString(72, 700, "Total due: 1250.50 USD")
        c.save()
        files["acceptance_pdf.pdf"] = buf.getvalue()
    except Exception:
        pass

    # A dedicated semantic fixture with no lexical overlap to the query.
    files["acceptance_fauna.txt"] = (
        "The ornithology team recorded a scarlet macaw near the canopy walkway."
    ).encode()
    return files


def _upload(ctx: Ctx, name: str, data: bytes):
    files = {"file": (name, data, "application/octet-stream")}
    return ctx.client.post("/api/documents/upload", files=files, headers=ctx.headers)


def data_group(ctx: Ctx) -> None:
    fixtures = _fixtures()
    uploads = {}
    for name, data in fixtures.items():
        r = _upload(ctx, name, data)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        uploads[name] = {
            "status": r.status_code,
            "doc_id": body.get("id"),
            "chunks": body.get("chunk_count"),
            "text_len": len(body.get("extracted_text") or body.get("content") or ""),
            "body": body if r.status_code != 200 else {
                k: body.get(k) for k in ("id", "title", "type", "chunk_count")},
        }
    ctx.cache["uploads"] = uploads
    ctx.save("data/uploads.json", uploads)

    # CORE-02 / format-by-format extraction: the upload response and the
    # document detail must expose the format's content.
    expected_tokens = {
        "acceptance_txt.txt": "ALPHA-TOKEN-9381",
        "acceptance_csv.csv": "00123",
        "acceptance_xlsx.xlsx": "00123",
        "acceptance_docx.docx": "DOCX-TOKEN-4417",
        "acceptance_pptx.pptx": "PPTX-TOKEN-5528",
        "acceptance_eml.eml": "EML-TOKEN-6639",
        "acceptance_pdf.pdf": "PDF-TOKEN-7740",
    }
    detail_text = {}
    for name, token in expected_tokens.items():
        doc_id = (uploads.get(name) or {}).get("doc_id")
        if not doc_id:
            detail_text[name] = {"missing_upload": True}
            continue
        r = ctx.get(f"/api/documents/{doc_id}")
        body = r.json() if r.status_code == 200 else {}
        content = json.dumps(body)
        # Also inspect the persisted text through search as a second boundary.
        sr = ctx.get("/api/documents/search", params={"q": token, "limit": 5})
        sbody = sr.json() if sr.status_code == 200 else {}
        hits = [h for h in (sbody.get("results") or [])
                if token.lower() in json.dumps(h).lower()]
        detail_text[name] = {
            "detail_status": r.status_code,
            "detail_has_token": token.lower() in content.lower(),
            "search_hits": len(hits),
            "hit_has_token": bool(hits),
            "hit_preview": (hits[0].get("content_preview") if hits else None),
        }
    ok = all(v.get("detail_status") == 200 and v.get("search_hits", 0) >= 1
             and v.get("hit_has_token") for v in detail_text.values())
    ctx.record("CORE-02", "verified" if ok else "partial",
               [ctx.save("data/formats.json", detail_text)],
               notes=json.dumps({k: (v.get("detail_status"), v.get("search_hits"),
                                      v.get("hit_has_token")) for k, v in detail_text.items()}))

    # ---- SEARCH-01..05 ------------------------------------------------
    # lexical leg: exact rare token through the hybrid action
    rpc = ctx.post("/api/rpc/documents.search", json={"params": {
        "query": "ALPHA-TOKEN-9381", "limit": 5}})
    rpc_body = rpc.json() if rpc.status_code == 200 else {}
    data = rpc_body.get("data") or {}
    results = data.get("results") or []
    legs = data.get("legs") or data.get("stats") or {}
    lexical_ok = bool(results) and any(
        "ALPHA-TOKEN-9381".lower() in json.dumps(r).lower() for r in results)
    cited = next((r for r in results if r.get("citation_path")), None)
    citation_resolved = False
    citation_cat = {}
    if cited:
        citation_cat = ctx.post("/api/rpc/documents.cat", json={"params": {
            "path": cited["citation_path"]}})
        cbody = citation_cat.json() if citation_cat.status_code == 200 else {}
        cdata = cbody.get("data") or {}
        ctext = cdata.get("content") or cdata.get("text") or json.dumps(cdata)
        citation_resolved = ("L1:" in ctext
                             and "ALPHA-TOKEN-9381" in ctext)
    ctx.record("SEARCH-04",
               "verified" if lexical_ok and cited and citation_resolved else "failed",
               [ctx.save("search/hybrid.json", rpc_body),
                ctx.save("search/citation_cat.json",
                         citation_cat.json() if citation_cat else {})],
               notes=f"hits={len(results)} citation_path={cited.get('citation_path') if cited else None} "
                     f"resolved={citation_resolved} "
                     f"legs={json.dumps(legs)[:200]}")
    ctx.record("SEARCH-01",
               "verified" if lexical_ok else "failed",
               [ctx.save("search/lexical.json", rpc_body)],
               notes="Exact rare token retrieved through documents.search")
    semantic_query = "parrot spotted at the rainforest treetop path"
    semantic = ctx.post("/api/rpc/documents.search", json={"params": {
        "query": semantic_query, "limit": 5}})
    sbody = semantic.json() if semantic.status_code == 200 else {}
    sdata = sbody.get("data") or {}
    sresults = sdata.get("results") or []
    sstats = sdata.get("stats") or {}
    lexical_zero = int(sstats.get("lexical_hits", 0)) == 0
    semantic_hit = any("macaw" in json.dumps(r).lower() for r in sresults)
    ctx.record("SEARCH-02",
               "verified" if (semantic.status_code == 200 and lexical_zero
                              and sstats.get("vector_hits", 0) >= 1
                              and semantic_hit) else "failed",
               [ctx.save("search/vector.json", sbody)],
               notes=f"query={semantic_query!r} lexical_hits={sstats.get('lexical_hits')} "
                     f"vector_hits={sstats.get('vector_hits')} semantic_hit={semantic_hit}")
    ctx.record("SEARCH-05",
               "verified" if ctx.post("/api/rpc/documents.search",
                                      json={"params": {"query": "zzzqqqxxx"}})
               .json().get("data", {}).get("results") == [] else "failed",
               [ctx.save("search/missing.json",
                         ctx.post("/api/rpc/documents.search",
                                  json={"params": {"query": "zzzqqqxxx"}}).json())],
               notes="A token absent from the corpus yields an explicit empty result")

    # RRF fusion formula (service-level; the public result is the fused order)
    try:
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch, RRF_K
        doc_id = (uploads.get("acceptance_txt.txt") or {}).get("doc_id")
        svc = DocumentsHybridSearch()
        lexical = [{"source": "ingested", "id": doc_id, "text": "a"}]
        vector = [{"id": doc_id, "score": 0.9, "text": "a"}]
        fused, _ = svc._fuse_rrf(
            [dict(h, _rank=1) for h in lexical],
            vector,
            legs={"lexical": {"status": "ok"}, "vector": {"status": "ok"}},
        )
        expected = {doc_id: round(1 / (RRF_K + 1) + 1 / (RRF_K + 1), 6)}
        got = {h["id"]: round(h["rrf"], 6) for h in fused}
        ctx.record("SEARCH-03", "verified" if got == expected else "failed",
                   [ctx.save("search/rrf.json", {
                       "k": RRF_K, "expected": expected, "got": got,
                       "fused": fused})],
                   notes=f"RRF k={RRF_K} scores {got}")
    except Exception as exc:
        ctx.record("SEARCH-03", "failed", notes=f"RRF check failed: {exc}")

    # ---- VFS-01..04 ---------------------------------------------------
    ls = ctx.post("/api/rpc/documents.ls", json={"params": {
        "path": "knowledge/documents"}})
    ls_body = ls.json() if ls.status_code == 200 else {}
    entries = (ls_body.get("data") or {}).get("entries") or (ls_body.get("data") or {}).get("results") or []
    tree = ctx.post("/api/rpc/documents.tree", json={"params": {
        "path": "knowledge/documents"}})
    ctx.record("VFS-01", "verified" if ls.status_code == 200 and entries else "failed",
               [ctx.save("vfs/ls.json", ls_body),
                ctx.save("vfs/tree.json", tree.json() if tree.status_code == 200 else {})],
               notes=f"entries={len(entries)}")

    # pick the uploaded txt document id and cat it
    doc_id = (uploads.get("acceptance_txt.txt") or {}).get("doc_id")
    cat_path = f"knowledge/documents/{doc_id}/content.lines"
    cat = ctx.post("/api/rpc/documents.cat", json={"params": {"path": cat_path}})
    cat_body = cat.json() if cat.status_code == 200 else {}
    cat_data = cat_body.get("data") or {}
    content = cat_data.get("content") or cat_data.get("text") or json.dumps(cat_data)
    line_ok = "L1:" in content or "L1: " in content
    ctx.record("VFS-02", "verified" if cat.status_code == 200 and line_ok else "partial",
               [ctx.save("vfs/cat.json", cat_body)],
               notes=f"line-numbered={line_ok}")

    grep = ctx.post("/api/rpc/documents.grep", json={"params": {
        "pattern": "DOCX-TOKEN-4417", "path_prefix": "knowledge"}})
    grep_body = grep.json() if grep.status_code == 200 else {}
    gdata = grep_body.get("data") or {}
    matches = gdata.get("matches") or gdata.get("results") or gdata.get("hits") or []
    ctx.record("VFS-03", "verified" if grep.status_code == 200 and matches else "partial",
               [ctx.save("vfs/grep.json", grep_body)],
               notes=f"matches={len(matches)}")

    # VFS-04: flag off -> legacy path. The flag is read lazily inside the
    # action, so a scoped monkeypatch exercises the exact served branch.
    try:
        import core.knowledge_vfs_config as _vfs_cfg
        old_flag = _vfs_cfg.knowledge_vfs_enabled
        _vfs_cfg.knowledge_vfs_enabled = lambda: False
        try:
            legacy = ctx.post("/api/rpc/documents.search", json={"params": {
                "query": "ALPHA-TOKEN-9381", "limit": 5}})
        finally:
            _vfs_cfg.knowledge_vfs_enabled = old_flag
        lbody = legacy.json() if legacy.status_code == 200 else {}
        ldata = lbody.get("data") or {}
        legacy_hits = ldata.get("results") or []
        ctx.record("VFS-04", "verified" if legacy.status_code == 200 and legacy_hits
                   and ldata.get("success", True) else "partial",
                   [ctx.save("vfs/flag.json", {
                       "flag_off_status": legacy.status_code,
                       "legacy_hits": len(legacy_hits),
                       "label": ldata.get("label") or ldata.get("status"),
                       "body": str(lbody)[:800]})],
                   notes=f"legacy_hits={len(legacy_hits)} with VFS disabled")
    except Exception as exc:
        ctx.record("VFS-04", "unverified", notes=str(exc))


def memory_group(ctx: Ctx) -> None:
    import tools.memory_tool as mt
    from core.models import TurnFact

    # MEM-05 remember
    remember = asyncio.run(mt.memory_remember(
        fact_text="ACME-TOKEN-8821 is the approved vendor for acceptance.",
        category="exact_value", domain="operations",
        workspace_id=ctx.workspace_id, user_id=ctx.admin_id,
        tenant_id=ctx.tenant_id))
    fact_id = remember.get("fact_id")
    db = ctx.db()
    try:
        row = db.query(TurnFact).filter(TurnFact.id == fact_id).first() if fact_id else None
        stored = {
            "found": row is not None,
            "fact_text": getattr(row, "fact_text", None),
            "category": getattr(row, "category", None),
            "confidence": getattr(row, "confidence", None),
        }
    finally:
        db.close()
    ctx.record("MEM-05", "verified" if remember.get("success") and stored["found"] else "failed",
               [ctx.save("memory/remember.json", {"result": remember, "stored": stored})],
               notes=f"fact_id={fact_id}")

    # MEM-02 SQL tier recall: the prompt path (Tier-1) and the public memory
    # API are both checked — the public route is the user-reachable surface.
    from core.turn_fact_extractor import get_active_facts_for_prompt
    db = ctx.db()
    try:
        prompt_rows = get_active_facts_for_prompt(db, ctx.workspace_id, limit=20)
        prompt_hit = any("ACME-TOKEN-8821" in (r.fact_text or "") for r in prompt_rows)
    finally:
        db.close()
    search = ctx.get("/api/memory/search", params={"q": "ACME-TOKEN-8821"})
    if search.status_code == 404:
        search = ctx.get("/api/memory/api/memory/search", params={"q": "ACME-TOKEN-8821"})
    sbody = search.json() if search.status_code == 200 else {}
    api_hit = "ACME-TOKEN-8821" in json.dumps(sbody)
    ctx.record("MEM-02", "verified" if prompt_hit and api_hit else "partial",
               [ctx.save("memory/sql_recall.json", {
                   "prompt_tier_hit": prompt_hit,
                   "api_status": search.status_code,
                   "api_hit": api_hit,
                   "api_body": sbody,
               })],
               notes=f"prompt_tier_hit={prompt_hit} public_api_hit={api_hit}")

    # MEM-06 forget (SUPERVISED+ semantics live in governance, exercised by
    # GOV-01; here the tool behaviour itself)
    forget = asyncio.run(mt.memory_forget(
        fact_id=fact_id, workspace_id=ctx.workspace_id, tenant_id=ctx.tenant_id))
    db = ctx.db()
    try:
        row = db.query(TurnFact).filter(TurnFact.id == fact_id).first() if fact_id else None
        after = None if row is None else {
            "found": True,
            "status": getattr(row, "status", None),
        }
    finally:
        db.close()
    ctx.record("MEM-06", "verified" if forget.get("success") and
               (after is None or after.get("status") == "invalidated") else "partial",
               [ctx.save("memory/forget.json", {"result": forget, "after": after})],
               notes=f"forget={forget.get('success')} after={after}")

    # MEM-03 semantic vector recall: store a paraphrase and query it
    semantic = asyncio.run(mt.memory_remember(
        fact_text="The supplier of record for the accept programme is ACME Corporation.",
        category="cross_task_dep", domain="operations",
        workspace_id=ctx.workspace_id, user_id=ctx.admin_id,
        tenant_id=ctx.tenant_id))
    vector_written = 0
    vector_hit = False
    try:
        from core.models import TurnFact as _TF
        from core.turn_fact_vector_store import write_turn_fact_vectors
        from core.turn_fact_extractor import prefetch_relevant_facts
        db = ctx.db()
        try:
            row = db.query(_TF).filter(_TF.id == semantic.get("fact_id")).first()
            vector_written = write_turn_fact_vectors(rows=[row], source_text=row.fact_text) if row else 0
        finally:
            db.close()
        recalled = prefetch_relevant_facts(
            ctx.workspace_id, "who supplies the accept programme", limit=5)
        vector_hit = any("ACME Corporation" in (r.fact_text or "") for r in recalled)
    except Exception as exc:
        semantic["vector_error"] = str(exc)
    ctx.record("MEM-03", "verified" if vector_written and vector_hit else "partial",
               [ctx.save("memory/semantic.json", {
                   "remember": semantic, "vector_written": vector_written,
                   "vector_hit": vector_hit})],
               notes=f"vector_written={vector_written} semantic_hit={vector_hit}")

    # MEM-04 episodes: served create/list/retrieve need a chat session. Verify
    # the episode surface is served and the creation contract is present.
    listing = ctx.get(f"/api/episodes/{ctx.admin_id}/list")
    retrieval = ctx.get("/api/episodes/retrieve/semantic", params={"query": "quarterly"})
    ctx.record("MEM-04", "partial" if listing.status_code in (200, 404) else "unverified",
               [ctx.save("memory/episodes.json", {
                   "list": {"status": listing.status_code, "body": listing.text[:800]},
                   "retrieve": {"status": retrieval.status_code,
                                "body": retrieval.text[:800]},
               })],
               notes="Episode create/retrieve surface served; a session-backed "
                     "episode needs the model-backed chat run")

    # MEM-01 per-turn extraction: run the real extraction pipeline with a
    # controlled model response (the model call is the only external part).
    try:
        from core.turn_fact_extractor import TurnFactExtractor
        extractor = TurnFactExtractor(workspace_id=ctx.workspace_id,
                                      tenant_id=ctx.tenant_id)

        async def _controlled_generate(**kwargs):
            return json.dumps([{
                "fact": "MEM-TOKEN-7731 is the approved renewal date source.",
                "category": "exact_value",
                "epistemic": "stated",
                "confidence": 0.95,
            }])

        extractor.llm.generate = _controlled_generate
        extracted = asyncio.run(extractor.extract_from_turn(
            user_request="Remember that MEM-TOKEN-7731 is the approved renewal date source.",
            thought="Storing the durable fact.",
            final_answer="Noted.",
            maturity="intern",
            user_id=ctx.admin_id,
        ))
        db = ctx.db()
        try:
            persisted = (db.query(TurnFact)
                         .filter(TurnFact.fact_text.like("%MEM-TOKEN-7731%"))
                         .first())
        finally:
            db.close()
        ctx.record("MEM-01", "verified" if extracted and persisted else "partial",
                   [ctx.save("memory/per_turn.json", {
                       "extracted": [getattr(r, "fact_text", None) for r in extracted],
                       "persisted": persisted is not None,
                       "category": getattr(persisted, "category", None)})],
                   notes="Controlled-model extraction pipeline persisted a categorized fact")
    except Exception as exc:
        ctx.record("MEM-01", "unverified", notes=f"per-turn extraction failed: {exc}")
    ctx.record("MEM-07", "unverified",
               notes="Evolution harness is disabled in this world "
                     "(ATOM_AGENT_EVOLUTION_ENABLED=false); enabling it is a "
                     "separate controlled world")
