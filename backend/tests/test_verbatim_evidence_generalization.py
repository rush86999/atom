# -*- coding: utf-8 -*-
"""The mailbox evidence choke point grips more than figures.

Live 2026-09-14 (canvas a1a13834, third wave — same root-cause family,
different surface): "find the email that said: put 25 percent only" got
closest-match noise instead of the row that VERBATIM contains the phrase,
and "check the email thread chandrakant forwarded to me about how list
price was calculated for the foot shear" found nothing because the
planner's query dropped the only deterministic handle ("chandrakant")
and no lane grips a participant NAME: grep needs verbatim strings, the
address lane needs x@y.z, figure lanes need amounts.

`_verbatim_mail_evidence` (the orchestrator-level evidence that LEADS the
tool block regardless of what the planner chose) now resolves, in order:
distinctive figures → quoted phrases (verbatim containment) → participant
names (matched against the store's OWN sender/recipient strings — no
name-entity guessing). All mocked — zero network, zero live DB.
"""
import asyncio
from unittest.mock import patch

import pytest

import core.chat_tool_planner as ctp
import integrations.chat_orchestrator as co


def _rows(*specs):
    out = []
    for i, (sender, recipient, subject, content, ts) in enumerate(specs):
        out.append({
            "id": f"m{i}", "sender": sender, "recipient": recipient,
            "subject": subject, "content": content, "timestamp": ts,
            "metadata": "",
        })
    return out


STORE = _rows(
    # The turn-7 thread: participant-named, conceptually worded, code-filed.
    ("chandrakant@brennan.ca", "rish@brennan.ca",
     "Re: Brake, Shear and Lock Former",
     "52T 81020 Tennsmith list derived from cost $8,880 plus freight.",
     "2026-08-20T14:00:00"),
    # The turn-6 phrase row: verbatim "put 25 percent only" inside a thread.
    ("chandrakant@brennan.ca", "rish@brennan.ca",
     "Fw: RFQ - Foot shear",
     "Vipul wrote: put 25 percent only on the Seguin machine.",
     "2026-09-11T09:00:00"),
    # Same participant, unrelated traffic (must NOT outrank the foot-shear
    # rows for the turn-7 ask despite being newer).
    ("chandrakant@brennan.ca", "rish@brennan.ca",
     "Kitchen renovation photos",
     "check out these tiles",
     "2026-09-13T10:00:00"),
    # Different participant entirely.
    ("joelseguin@seguinmach.com", "rish@brennan.ca",
     "FW: RFQ - Foot shear",
     "$ 5,350.00 - 10 % in stock",
     "2026-08-26T14:06:00"),
)


@pytest.fixture(autouse=True)
def _fake_store(monkeypatch):
    import core.chat_tool_planner as ctp

    monkeypatch.setattr(ctp, "_comms_store_records", lambda: STORE)


class TestParticipantLeg:
    def test_participant_rows_ranked_by_topic_overlap_then_newest(self):
        rows = co._participant_mail_rows(
            "check the email thread chandrakant forwarded to me about how "
            "list price was calculated for the foot shear")
        assert rows, "expected the participant lane to fire"
        senders = {r["sender"] for r in rows}
        assert senders == {"chandrakant@brennan.ca"}
        # Both foot-shear-adjacent threads surface (the model reads both and
        # picks the list-price one); the NEWER UNRELATED thread does not.
        subjects = {r["subject"] for r in rows}
        assert "Re: Brake, Shear and Lock Former" in subjects
        assert "Fw: RFQ - Foot shear" in subjects
        assert "Kitchen renovation photos" not in subjects

    def test_role_addresses_never_become_participants(self):
        rows = co._participant_mail_rows(
            "show me what sales sent about the shear")
        assert rows == []

    def test_unknown_name_fires_nothing(self):
        assert co._participant_mail_rows(
            "check the thread bernhard forwarded about shears") == []


@pytest.fixture
def _no_figures(monkeypatch):
    monkeypatch.setattr(ctp, "_distinctive_figure_phrases", lambda *a, **k: [])
    monkeypatch.setattr(ctp, "_latest_user_figure_phrases", lambda *a, **k: [])


class TestVerbatimEvidenceLegs:
    @pytest.mark.asyncio
    async def test_quoted_phrase_leads_the_evidence(self, _no_figures):
        lines = await co._verbatim_mail_evidence(
            "find the email that said: put 25 percent only", "u1", None)
        assert any("Fw: RFQ - Foot shear" in l for l in lines), lines
        # The verbatim phrase row leads.
        assert "Fw: RFQ - Foot shear" in lines[0]

    @pytest.mark.asyncio
    async def test_participant_ask_surfaces_the_thread(self, _no_figures):
        lines = await co._verbatim_mail_evidence(
            "check the email thread chandrakant forwarded to me about how "
            "list price was calculated for the foot shear and reverse "
            "engineer the calculation and show it to me", "u1", None)
        assert lines, "expected participant evidence"
        assert any("Brake, Shear and Lock Former" in l for l in lines), lines

    @pytest.mark.asyncio
    async def test_no_handles_returns_empty(self, _no_figures):
        lines = await co._verbatim_mail_evidence(
            "what is the capital of France", "u1", None)
        assert lines == []

class TestComposerMailLed:
    def test_participant_referent_ask_is_mail_led(self):
        # "check the email thread chandrakant forwarded …" has no quoted
        # span, but it points at a MESSAGE. The composer must lead with the
        # mailbox bodies (live 2026-09-15: demoting them to caveat-wrapped
        # "HISTORICAL CORRESPONDENCE" produced "I found 0 results" from the
        # pinned fallback, which read only the empty live block).
        mail = ["- [ingested mailbox] From: chandrakant@brennan.ca | Re: "
                "Brake, Shear and Lock Former. | FULL BODY:\ncost $8,880 "
                "plus freight and margin = list"]
        live = "LIVE TOOL RESULTS (documents.search): returned nothing usable"
        out = co._compose_lookup_evidence(
            "check the email thread chandrakant forwarded to me about how "
            "list price was calculated for the foot shear and reverse "
            "engineer the calculation and show it to me",
            None, live, mail)
        assert out.startswith("LIVE TOOL RESULTS (ingested mailbox")
        assert "FULL MESSAGE BODIES" in out
        assert mail[0] in out
        # the live block is retained as the trailing note, not the lead
        assert out.index(mail[0]) < out.index(live)

    def test_quote_lookup_still_mail_led(self):
        mail = ["- [ingested mailbox] line"]
        out = co._compose_lookup_evidence(
            "search for this one: $ 5,350.00 - 10 % in stock",
            None, "LIVEBLOCK", mail)
        assert out.startswith("LIVE TOOL RESULTS (ingested mailbox")
        assert "LIVEBLOCK" in out

class TestStatedDateWindow:
    def test_slash_date_with_weekday_parses(self):
        import datetime
        today = datetime.date(2026, 9, 14)  # Monday
        assert ctp._stated_date_window(
            "find the email thread for f-5216. it was sent to me on 9/11 friday",
            today=today,
        ) == ("2026-09-11 00:00:00", "2026-09-12 00:00:00")

    def test_month_name_and_weekday_forms(self):
        import datetime
        today = datetime.date(2026, 9, 14)
        assert ctp._stated_date_window(
            "the email from september 11", today=today
        ) == ("2026-09-11 00:00:00", "2026-09-12 00:00:00")
        assert ctp._stated_date_window("sent friday", today=today) == (
            "2026-09-11 00:00:00", "2026-09-12 00:00:00")

    def test_dimension_fractions_are_not_dates(self):
        # '7/8-inch' without any day-word context must not become July 8.
        import datetime
        today = datetime.date(2026, 9, 14)
        assert ctp._stated_date_window(
            "check the 7/8-inch port spec", today=today) is None

    def test_date_window_tiers_matches(self):
        # Live shape: 'F-5216' matches 17 stored rows; the Sep 11 pair the
        # user pointed at lost the newest-3 cap to Sep 14 traffic. The
        # stated-date tier must lead with them.
        rows = [
            {"id": "m1", "sender": "a@x.ca", "recipient": "r@brennan.ca",
             "subject": "old thread", "content": "F-5216 mentioned",
             "timestamp": "2026-08-26 15:50:00", "metadata": ""},
            {"id": "m2", "sender": "chandrakant@brennan.ca",
             "recipient": "r@brennan.ca",
             "subject": "Re: 52 Inch 16 Gauge Foot Shear",
             "content": "F-5216 alternative, 2-3 weeks",
             "timestamp": "2026-09-11 19:21:00", "metadata": ""},
            {"id": "m3", "sender": "kurt@neimanmachinery.com",
             "recipient": "r@brennan.ca",
             "subject": "RE: 52 Inch 16 Gauge Foot Shear",
             "content": "F-5216 hydraulic?",
             "timestamp": "2026-09-11 20:36:00", "metadata": ""},
            {"id": "m4", "sender": "chandrakant@brennan.ca",
             "recipient": "r@brennan.ca",
             "subject": "Re: Brake, Shear and Lock Former.",
             "content": "F-5216 at 7519", "timestamp": "2026-09-14 15:38:00",
             "metadata": ""},
        ]
        out = ctp._match_rows_by_figure_tokens(
            rows, ["F-5216"], limit=3,
            date_window=("2026-09-11 00:00:00", "2026-09-12 00:00:00"))
        ids = [r["id"] for r in out]
        # In-window rows lead (newest first); the cap then keeps the newer
        # out-of-window thread — the Aug 26 row is correctly dropped.
        assert ids == ["m3", "m2", "m4"], ids

    def test_feb29_future_rollover_never_raises(self):
        # '2/29' stated before this year's Feb 29: last year had no Feb 29,
        # so the M/D branch must yield nothing (like Feb 30) — the year-
        # decrement used to raise ValueError and kill the whole evidence
        # leg. The weekday branch still takes over when present.
        import datetime
        today = datetime.date(2028, 1, 4)  # Tuesday
        got = ctp._stated_date_window("sent 2/29 friday", today=today)
        assert got == ("2027-12-31 00:00:00", "2028-01-01 00:00:00")
        # Month form with no day word anywhere: nothing usable -> None.
        assert ctp._stated_date_window(
            "the quote from february 29", today=today) is None
        # A real Feb 29 that has already happened parses normally.
        assert ctp._stated_date_window(
            "sent 2/29 friday", today=datetime.date(2028, 3, 6)) == (
            "2028-02-29 00:00:00", "2028-03-01 00:00:00")

class TestMentionedDatePiggyback:
    """The planner reads the same message the regex parser does — the
    mentioned_date field (resolved in the SAME structured call, zero extra
    LLM cost) covers the messy relative expressions the parser cannot
    ('end of last month', 'two Tuesdays ago'). Regex stays the fast path;
    the plan field is the fallback; recency the last resort."""

    def test_validator_shapes(self):
        import datetime
        assert ctp.ToolPlan(
            query="x", mentioned_date="2026-09-11"
        ).mentioned_date == "2026-09-11"
        assert ctp.ToolPlan(
            query="x", mentioned_date="9/11/2026"
        ).mentioned_date == "2026-09-11"
        # bare M/D resolves to the current year, last year if future
        today = datetime.date.today()
        got = ctp.ToolPlan(query="x", mentioned_date="9/11").mentioned_date
        assert got == "2026-09-11"  # Sep 11 is past as of Sep 2026
        assert ctp.ToolPlan(
            query="x", mentioned_date="september 11"
        ).mentioned_date is None
        assert ctp.ToolPlan(query="x", mentioned_date=None).mentioned_date is None

    def test_window_from_iso_date(self):
        assert ctp._window_from_iso_date("2026-09-11") == (
            "2026-09-11 00:00:00", "2026-09-12 00:00:00")
        assert ctp._window_from_iso_date(None) is None
        assert ctp._window_from_iso_date("not-a-date") is None

    @pytest.mark.asyncio
    async def test_plan_date_used_when_regex_parses_nothing(self, monkeypatch):
        # 'end of last month' — no regex match; the pinned planner date
        # must tier the figure matches anyway.
        captured = {}

        def fake_search(user_id, tokens, limit=4, date_window=None):
            captured["window"] = date_window
            return ["- [ingested mailbox] From: a@b.ca | thread | body"]

        monkeypatch.setattr(ctp, "_distinctive_figure_phrases",
                            lambda *a, **k: ["5,350.00"])
        monkeypatch.setattr(ctp, "_search_ingested_by_tokens", fake_search)
        lines = await co._verbatim_mail_evidence(
            "find the thread from end of last month", "u1", None,
            plan_date="2026-08-31")
        assert lines
        assert captured["window"] == ("2026-08-31 00:00:00",
                                      "2026-09-01 00:00:00")

    @pytest.mark.asyncio
    async def test_regex_window_wins_over_plan_date(self, monkeypatch):
        # When both exist, the message's own parseable date is the truth.
        captured = {}

        def fake_search(user_id, tokens, limit=4, date_window=None):
            captured["window"] = date_window
            return ["- [ingested mailbox] line"]

        monkeypatch.setattr(ctp, "_distinctive_figure_phrases",
                            lambda *a, **k: ["5,350.00"])
        monkeypatch.setattr(ctp, "_search_ingested_by_tokens", fake_search)
        await co._verbatim_mail_evidence(
            "find the thread sent 9/11 friday", "u1", None,
            plan_date="2026-08-31")
        assert captured["window"] == ("2026-09-11 00:00:00",
                                      "2026-09-12 00:00:00")

class TestDirectionalParticipantAsks:
    """Live 2026-09-15: "find the email that was sent to me on that day by
    chandrakant" — the planner DECLINED (previous turn had answered), the
    overlay never ran, and the reply attributed a supplier-bound email
    (To: edwin@schulermachinery.com) to the user. The participant lane now
    tiers directionally (by-<name> sender, to-me recipient) and by the
    stated-day window; the window itself inherits 'that day' from the
    previous user turn."""

    DIR_ROWS = _rows(
        ("chandrakant@brennan.ca", "rish@brennan.ca",
         "Fw: RFQ - Foot shear", "the forwarded thread", "2026-09-11T20:07:00"),
        ("chandrakant@brennan.ca", "doug@liquidsystems.net",
         "Quote for TB80 Bender", "bender pricing", "2026-09-11T20:02:00"),
        ("edwin@schulermachinery.com", "chandrakant@brennan.ca",
         "Re: Enquiry about Lathe machine",
         "hey, i did not find the attachment", "2026-09-11T12:50:00"),
    )

    def test_by_name_sender_and_window_tier(self):
        import core.chat_tool_planner as ctp

        with patch.object(ctp, "_comms_store_records",
                          return_value=self.DIR_ROWS):
            rows = co._participant_mail_rows(
                "find the email that was sent to me on that day by chandrakant",
                4, ("2026-09-11 00:00:00", "2026-09-12 00:00:00"),
                "rish@brennan.ca")
        assert rows, "participant lane must fire"
        # chandrakant-SENT, in-window, addressed to the acting user.
        assert rows[0]["recipient"] == "rish@brennan.ca"
        assert rows[0]["subject"] == "Fw: RFQ - Foot shear"
        # The supplier-bound thread (chandrakant as RECIPIENT, "by" mismatch)
        # must NOT lead.
        leaders = [r["subject"] for r in rows[:2]]
        assert "Re: Enquiry about Lathe machine" not in leaders

    def test_to_me_penalty_for_other_recipients(self):
        import core.chat_tool_planner as ctp

        with patch.object(ctp, "_comms_store_records",
                          return_value=self.DIR_ROWS):
            rows = co._participant_mail_rows(
                "the email sent to me by chandrakant about the bender",
                4, None, "rish@brennan.ca")
        # Both rows are chandrakant-sent; the to-me row outranks doug's.
        assert rows[0]["recipient"] == "rish@brennan.ca"

    @pytest.mark.asyncio
    async def test_anaphoric_that_day_inherits_prior_turn_date(self, monkeypatch):
        captured = {}

        def fake_search(user_id, tokens, limit=4, date_window=None):
            captured["window"] = date_window
            return ["- [ingested mailbox] From: a@b.ca | line"]

        monkeypatch.setattr(ctp, "_distinctive_figure_phrases",
                            lambda *a, **k: ["5,350.00"])
        monkeypatch.setattr(ctp, "_search_ingested_by_tokens", fake_search)
        await co._verbatim_mail_evidence(
            "find the email sent to me on that day by chandrakant",
            "u1",
            {"history": [{"role": "user", "content":
                          "the thread sent 9/11 friday"}]},
        )
        assert captured["window"] == ("2026-09-11 00:00:00",
                                      "2026-09-12 00:00:00")

    def test_declined_plan_still_gets_the_overlay(self):
        """Wiring pin (source-shape, per the blackboard-test precedent):
        the DECLINED-plan branch must run the verbatim overlay — follow-up
        turns decline precisely because the previous turn answered, and
        without the overlay the reply narrates from ambient memory."""
        import inspect

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        assert "declined-plan mailbox overlay" in src
        assert '_declined_mail = await asyncio.wait_for(' in src
        assert "_tool_block = _compose_lookup_evidence(" in src

class TestDerivationAsks:
    """Live 2026-09-15: "figure out how the listed price was derived.
    Chandrakant might've added a few hundred on top for requesting google
    reviews." — the true chain sat in PRICE VIPUL (6).xlsx row 235 (an
    INGESTED DATASET), but no lane reached it (the ask names no code; the
    reuse overlay ran mail lines only, without the canvas), and the model
    curve-fit a fabricated path (+10% add-back, ÷0.70, +$473 review
    markup) exactly onto the user's hinted target."""

    def test_derivation_shape_detected(self):
        assert co._derivation_ask(
            "given this info, figure out how the listed price was derived. "
            "Chandrakant might've added a few hundred on top")
        # shape word alone ('calculation') is not a value — needs a
        # concrete figure in context (see TestDomainIndependence)
        assert not co._derivation_ask(
            "reverse engineer the calculation and show it to me")
        assert co._derivation_ask("how was the $8,880 price calculated?")
        assert not co._derivation_ask("is WG-350DSAV in stock?")
        assert not co._derivation_ask("find the email from chandrakant")

    def test_unsourced_derivation_guard(self):
        fabricated = (
            "Most likely calculation path:\n"
            "| +10% add-back | $5,885.00 |\n"
            "| ÷ 0.70 margin | $8,407.14 |\n"
            "| + ~$473 markup | $8,880.00 |\n")
        msg = "figure out how the listed price was derived"
        assert co._reply_is_unsourced_derivation(fabricated, msg)
        # Cited derivation (dataset row convention) never trips.
        cited = (
            "Per PRICE VIPUL (6).xlsx R235: 5,350 × 0.9 = 4,815.00; "
            "+700 = 5,515.00; ×1.02 = 5,625.30; ÷0.87 = 6,465.86")
        assert not co._reply_is_unsourced_derivation(cited, msg)
        # Not a derivation ask → never trips.
        assert not co._reply_is_unsourced_derivation(fabricated, "find the thread")

    @pytest.mark.asyncio
    async def test_derivation_supplement_leads_with_dataset(self, monkeypatch):
        async def fake_ds(message, user_id, context, llm_service=None):
            if not co._derivation_ask(message):
                return None
            return ("SQL RESULT from 'PRICE VIPUL (6).xlsx' — "
                    "R235 | Factory Price=5350 | Price=7519")

        async def fake_mail(message, user_id, context, plan_date=None):
            return ["- [ingested mailbox] From: chandrakant@brennan.ca | line"]

        monkeypatch.setattr(co, "_derivation_dataset_block", fake_ds)
        monkeypatch.setattr(co, "_verbatim_mail_evidence", fake_mail)
        msg = "figure out how the listed price was derived"
        block = await co._derivation_supplement(msg, "u1", [], None, "MAILBLOCK")
        assert block and block.startswith("SQL RESULT from 'PRICE VIPUL")
        assert "MAILBLOCK" in block
        # Non-derivation asks: untouched.
        block2 = await co._derivation_supplement(
            "find the thread", "u1", [], None, "MAILBLOCK")
        assert block2 == "MAILBLOCK"

class TestDomainIndependence:
    """The derivation machinery must not encode one business's vocabulary
    or filenames (2026-09-15 review): trigger on derivation-verb shape +
    concrete value words OR figures in context — any domain."""

    def test_trigger_shapes(self):
        assert co._derivation_ask("figure out how the listed price was derived")
        assert co._derivation_ask("how was the reliability score computed")
        assert co._derivation_ask(
            "figure out how that was derived",
            {"canvas": {"body": "model X-100 at $7,519"}})
        # 'figure' inside 'figure out' is not a value word
        assert not co._derivation_ask("figure out how that was derived")
        assert not co._derivation_ask("is WG-350DSAV in stock?")
        assert not co._derivation_ask("find the email from chandrakant")

    def test_cite_regex_has_no_business_literals(self):
        import inspect
        src = inspect.getsource(co)
        assert "PRICE VIPUL" not in src.split("_DERIVATION_CITE_RE")[1].split(")")[0]


class TestImmutableDatasetFreshness:
    def test_attachment_copy_is_fresh_past_ttl(self):
        from datetime import datetime, timezone, timedelta
        from core.sheet_dataset_service import _copy_is_fresh
        stale = datetime.now(timezone.utc) - timedelta(hours=30)
        att = [{"source": "outlook", "ingested_at": stale.isoformat(),
                "source_modified_at": None}]
        live = [{"source": "zoho_workdrive", "ingested_at": stale.isoformat(),
                 "source_modified_at": None}]
        assert _copy_is_fresh(att) is True   # immutable: ingest stamp enough
        assert _copy_is_fresh(live) is False  # synced: TTL applies


class TestNLSQLLayerWiring:
    @pytest.mark.asyncio
    async def test_structured_section_leads(self, monkeypatch):
        async def fake_answer(source, ext, query, llm_service=None,
                              context_texts=None, **kw):
            assert source == "outlook", "catalog source resolved, not source_kind"
            return {"file_name": "W.xlsx", "entity_name": "S",
                    "sql": "SELECT 1", "columns": ["A", "Price"],
                    "rows": [{"A": "x", "Price": 7519, "__sheet_row": 5}],
                    "row_count": 1}
        import core.sheet_dataset_service as sds
        monkeypatch.setattr(sds, "answer_from_datasets", fake_answer)

        def fake_search(query, user_id=None, ws=None, limit=None,
                        max_files=None, ctx=None, *args, **kwargs):
            # The production call grew extra trailing arguments (named-file
            # context, derived deadline). Pin the behaviour, not the arity —
            # an arity-pinned fake silently turns every new argument into a
            # TypeError that reads as "the lane returned nothing".
            return {"token": "7519", "files_searched": 1, "hits": [
                {"file_name": "W.xlsx", "external_id": "E1",
                 "source_kind": "file", "entity_name": "S",
                 "columns": ["A", "Price"],
                 "rows": [{"A": "x", "Price": 7519, "__sheet_row": 5}],
                 "row_count": 1}]}

        def fake_find(q, u=None, w=None, l=None, *args, **kwargs):
            return [{"source": "outlook", "external_id": "E1",
                     "file_name": "W.xlsx"}]
        monkeypatch.setattr(sds, "search_all_datasets_sync", fake_search)
        monkeypatch.setattr(sds, "find_entries_sync", fake_find)

        class _LLM:  # truthy marker only
            pass

        out = await co._derivation_dataset_block(
            "figure out how the listed price was derived", "u1",
            {"canvas": {"body": "F-5216 $7,519.00"},
             "history": [{"role": "user", "content": "quoted $5,350.00"}]},
            llm_service=_LLM())
        assert out and "STRUCTURED QUERY" in out
        # header first, STRUCTURED QUERY ahead of every probe-row render
        assert out.startswith("DATASET CATALOG")
        assert out.index("STRUCTURED QUERY") < out.index("SQL RESULT")

class TestEvidenceBudgetAndAutoOpen:
    def test_budget_trims_bodies_keeps_headers(self, monkeypatch):
        monkeypatch.setattr(co, "_EVIDENCE_BUDGET_CHARS", 2000)
        lines = ["HEADER: evidence"] + [
            f"- [ingested mailbox] body line {i} " + "x" * 400 +
            " | full: knowledge/conversations/m" + str(i)
            for i in range(12)
        ]
        out = co._enforce_evidence_budget("\n".join(lines))
        assert out.startswith("HEADER: evidence")
        assert "elided" in out
        assert len(out) < 4000

    def test_budget_passthrough_short(self):
        assert co._enforce_evidence_budget("short") == "short"
        assert co._enforce_evidence_budget(None) is None

    @pytest.mark.asyncio
    async def test_auto_open_opens_top_citation(self, monkeypatch):
        class _Res:
            content = "L1 the decisive line\nL2\n" + "filler\n" * 900
        class _Prov:
            async def cat(self, path, ctx=None):
                assert path.startswith("knowledge/conversations/")
                return _Res()
        import integrations.vfs.knowledge_vfs as vfs
        monkeypatch.setattr(vfs, "KnowledgeVFSProvider", _Prov)
        block = ("- [ingested mailbox] From: a@b.ca | subj | full: "
                 "knowledge/conversations/msg-1")
        out = await co._auto_open_top_citation(block)
        assert out and out.startswith("OPENED (top cited artifact")
        assert "the decisive line" in out

    @pytest.mark.asyncio
    async def test_auto_open_skips_full_body_blocks(self):
        block = ("- [ingested mailbox] FULL BODY:\nstuff\n | full: "
                 "knowledge/conversations/m1")
        assert await co._auto_open_top_citation(block) is None
        assert await co._auto_open_top_citation(None) is None

class TestBudgetPreservesDecisiveLines:
    """Audit item 6: a surviving citation alone does not establish a
    derivation — the budget trim must drop PROSE before rows, formulas,
    and figure-bearing lines."""

    def test_decisive_row_and_formulas_survive_small_budget(self, monkeypatch):
        monkeypatch.setattr(co, "_EVIDENCE_BUDGET_CHARS", 1500)
        lines = ["HEADER: evidence"]
        lines += [f"- [ingested mailbox] prose body line {i} " + "y" * 220
                  for i in range(8)]
        lines.append("R235 | Product Name=F-52x16G | LIST Price=7519.0 | "
                     "Factory Price=5350 | $7,519.00")
        lines.append("FORMULAS FOR THE MATCHED ROW(S): G235==F235*0.9 | "
                     "I235==H235+700 | K235==J235*1.02 | 7519")
        out = co._enforce_evidence_budget("\n".join(lines))
        assert "R235" in out, "decisive row must survive"
        assert "FORMULAS" in out and "G235==F235*0.9" in out
        assert "elided" in out  # prose was dropped instead


class TestEvidenceBudgetIsAHardBound:
    """Review item 7: the budget function exempted decisive lines AND every
    line that did not start with ``-``/``R``/``SQL RESULT``/``FORMULAS``, so
    (a) protected rows alone could push the result past the stated cap and
    (b) an oversized document of ordinary unprefixed prose was returned
    untrimmed. It reported neither. Both are pinned here."""

    def test_protected_rows_alone_cannot_exceed_the_budget(self, monkeypatch):
        monkeypatch.setattr(co, "_EVIDENCE_BUDGET_CHARS", 1200)
        lines = ["HEADER: evidence"]
        # Every line is decisive (citations + figures) — nothing may be
        # dropped "politely", so the cap has to be enforced by DROPPING
        # decisive lines and saying so.
        lines += [
            f"R{i} | Product Name=F-52x16G | LIST Price={7000 + i}.0 | "
            f"Factory Price={5000 + i} | ${7000 + i}.00 | full: knowledge/"
            f"workbooks/price.xlsx"
            for i in range(40)
        ]
        out = co._enforce_evidence_budget("\n".join(lines))
        assert out is not None
        assert len(out) <= 1200, (
            f"protected rows alone overflowed the stated cap: {len(out)} chars")
        assert "elided" in out
        assert "decisive line(s)" in out, (
            "the omissions must name the decisive lines that were dropped")

    def test_oversized_unprefixed_prose_is_trimmed(self, monkeypatch):
        monkeypatch.setattr(co, "_EVIDENCE_BUDGET_CHARS", 2000)
        # No '-', 'R', 'SQL RESULT' or 'FORMULAS' prefixes anywhere: the old
        # classifier called every one of these lines "not a body" and kept
        # them all.
        prose = [
            "The forwarded thread continues with ordinary sentences that "
            "carry no prefix at all and no figure, sentence number " + str(i)
            for i in range(120)
        ]
        out = co._enforce_evidence_budget("\n".join(prose))
        assert out is not None
        assert len(out) <= 2000
        assert "elided" in out

    def test_single_pathological_line_still_respects_the_cap(self, monkeypatch):
        monkeypatch.setattr(co, "_EVIDENCE_BUDGET_CHARS", 800)
        out = co._enforce_evidence_budget("x" * 50_000)
        assert out is not None and len(out) <= 800

    def test_kept_decisive_line_keeps_its_attribution(self, monkeypatch):
        """A surviving row must not lose the full:/open: path that makes it
        checkable, and its neighbour stays with it."""
        monkeypatch.setattr(co, "_EVIDENCE_BUDGET_CHARS", 900)
        lines = [f"filler line {i} " + "z" * 120 for i in range(10)]
        lines.append("- [ingested workbook] matched row | full: "
                     "knowledge/workbooks/price.xlsx")
        lines.append("R235 | LIST Price=7519.0 | $7,519.00")
        lines.append("CONTEXT: this row is the quoted line item")
        out = co._enforce_evidence_budget("\n".join(lines))
        assert "R235" in out
        assert "knowledge/workbooks/price.xlsx" in out, (
            "the attribution path was dropped while its row survived")
        assert "CONTEXT: this row" in out, (
            "the row's own unit was dropped while the row survived")

    def test_within_budget_blocks_are_untouched(self):
        block = "HEADER: evidence\n- line | full: knowledge/a"
        assert co._enforce_evidence_budget(block) == block


class TestCompletePromptAccounting:
    """The evidence budget is a PER-SECTION budget: it says nothing about what
    the model receives once instructions, history, canvas and the turn are
    added. The turn now measures all of it against the selected model's
    context window minus its output reservation."""

    def test_accounting_covers_every_message(self):
        messages = [
            {"role": "system", "content": "S" * 4000},
            {"role": "assistant", "content": "A" * 2000},
            {"role": "user", "content": "U" * 1000},
        ]
        acct = co._account_turn_prompt(messages, provider_id="openrouter")
        assert acct is not None
        assert set(acct.sections) == {"system", "assistant", "user"}
        assert acct.total_input_tokens >= 1500  # ~7000 chars is not ~0 tokens

    def test_output_reservation_is_honoured(self):
        acct = co._account_turn_prompt(
            [{"role": "user", "content": "hello"}],
            provider_id="openrouter", output_reservation=32_000)
        assert acct is not None
        assert acct.output_reservation == 32_000
        assert acct.available_input_tokens == max(
            0, acct.context_window - 32_000)

    def test_unknown_provider_falls_back_to_a_conservative_window(self):
        acct = co._account_turn_prompt(
            [{"role": "user", "content": "x"}], provider_id="no-such-provider")
        assert acct is not None
        assert acct.context_window > 0
        assert acct.fits is True

    def test_accounting_never_raises_on_junk(self):
        assert co._account_turn_prompt(None) is not None
        assert co._account_turn_prompt([{"role": "user", "content": None}]) is not None
