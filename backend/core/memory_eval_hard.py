"""Hard-suite memory eval — the DISCRIMINATING A/B apparatus for R83 #4.

The stock golden set (core.memory_eval) ceilings at recall 1.0: 8 entities
means everything relevant fits the top-15 context regardless of ranking, so
the fusion arms (ATOM_RETRIEVAL_FUSION ∈ off/rrf/linear) cannot be told
apart there. This module adds what that gate lacks:

- a DISTRACTOR CORPUS: ~20 confusable entities in the same families as the
  brennan seed (press brakes, fiber lasers, cutters, tooling, vendors,
  leads) with overlapping vocabulary but unique attribute tokens;
- a HARD SET of questions whose expected snippets are unique tokens
  (SKUs, prices, controller models) among near-duplicates, split into:
    * attribute   — disambiguates within a family ("the 100-ton AccurPress
                    controller?" → DA-66T; keyword leg alone returns every
                    press brake, so the RIGHT entity must rank);
    * paraphrase  — zero lexical overlap with the target's name/description
                    (vector-leg dependent);
    * distractor  — the question's strongest keyword matches the WRONG
                    sibling first; only ranking puts the right one in the
                    top-15 context window.

get_context_for_ai truncates to entities[:15], so with ~28 entities the
snippet test is ranking-sensitive: an arm wins only if its fusion order
puts the right entity inside the window.

Usage (the A/B):
    for mode in off rrf linear; do
        ATOM_RETRIEVAL_FUSION=$mode ./venv/bin/python -m core.memory_eval_hard
    done

Not a CI gate — experiment apparatus (see R83_RELIABILITY_PLAN.md #4).
"""

import asyncio
import logging
from typing import Any, Dict, List

from core.memory_eval import EvalQuestion, EvalReport, EvalResult, _seed_eval_workspace

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Distractor corpus (same ingest shape as demo/brennan/seed_data.py, plus a
# top-level `description` because ingest_structured_data reads it for the
# keyword-leg description column).
# --------------------------------------------------------------------------- #

def _prod(pid: str, name: str, description: str, **props: Any) -> Dict[str, Any]:
    return {
        "id": pid,
        "type": "product",
        "name": name,
        "description": description,
        "properties": props,
    }


HARD_CORPUS: List[Dict[str, Any]] = [
    # -- Press-brake family (5 total incl. brennan's 50T) --
    _prod("prod:press-brake-100t", "AccurPress 100-Ton CNC Press Brake",
          "100-ton CNC press brake with 3200mm bed, Delem DA-66T control.",
          sku="BP-100T", tonnage="100 ton", bed_length="3200mm",
          list_price=152000.00, stock_on_hand=1, source="zoho_inventory"),
    _prod("prod:press-brake-mfp60", "MetalForm Pro 60 Press Brake",
          "60-ton press brake, 2600mm bed, Cybelec DNC 60 CNC, hydraulic crowning.",
          sku="MF-60", tonnage="60 ton", bed_length="2600mm",
          list_price=72900.00, stock_on_hand=2, source="zoho_inventory"),
    _prod("prod:press-brake-bm220", "BendMaster 220 Press Brake",
          "125-ton press brake, 4000mm bed, ESA S640 controller, servo backgauge.",
          sku="BM-220", tonnage="125 ton", bed_length="4000mm",
          list_price=198500.00, stock_on_hand=1, source="zoho_inventory"),
    _prod("prod:press-brake-sf40", "ShopFold Entry 40 Press Brake",
          "Entry 40-ton bench press brake, 1600mm bed, manual backgauge.",
          sku="SF-40", tonnage="40 ton", bed_length="1600mm",
          list_price=34800.00, stock_on_hand=6, source="zoho_inventory"),
    # -- Fiber-laser family (4 more incl. brennan's 2kW) --
    _prod("prod:fiber-laser-3kw", "SigmaMax 3kW Fiber Laser Cutter",
          "3kW fiber laser, cuts up to 25mm mild steel, 16mm stainless, 3000x1500mm bed.",
          sku="FL-3KW", list_price=186000.00, stock_on_hand=1, source="zoho_inventory"),
    _prod("prod:fiber-laser-6kw", "SigmaMax 6kW Fiber Laser",
          "6kW high-power fiber laser, 30mm mild steel, 20mm stainless, exchange table.",
          sku="FL-6KW", list_price=265000.00, stock_on_hand=1, source="zoho_inventory"),
    _prod("prod:fiber-laser-lt4kw", "LaserTech Pro 4kW Fiber Laser",
          "4kW fiber laser platform, 22mm mild steel, 4000x2000mm bed, Swiss scanning head.",
          sku="LT-4KW", list_price=205000.00, stock_on_hand=1, source="zoho_inventory"),
    _prod("prod:fiber-laser-vc15", "ValueCut 1.5kW Compact Fiber Laser",
          "Budget 1.5kW compact fiber laser for thin sheet, 12mm mild steel.",
          sku="VC-1.5KW", list_price=89000.00, stock_on_hand=3, source="zoho_inventory"),
    # -- Other cutting processes (confusable capacities) --
    _prod("prod:plasma-65a", "HyperCut 65A Plasma Cutter",
          "65A plasma cutting system, 20mm clean cut capacity, CNC torch height control.",
          sku="PC-65A", list_price=11400.00, stock_on_hand=4, source="zoho_inventory"),
    _prod("prod:waterjet-wj4015", "WaterJet Dynamics WJ-4015",
          "Abrasive garnet waterjet, 150mm plate capacity, non-thermal cutting, no heat-affected zone.",
          sku="WJ-4015", list_price=240000.00, stock_on_hand=1, source="zoho_inventory"),
    _prod("prod:oxyfuel-ot3", "OxyFuel Track Cutter OT-3",
          "Track-mounted oxy-fuel torch, 100mm plate, manual operation.",
          sku="OT-3", list_price=8200.00, stock_on_hand=7, source="zoho_inventory"),
    # -- Tooling / consumables (compatible_with confusables) --
    _prod("prod:brake-punch-holder", "Press Brake Quick-Clamp Punch Holder",
          "Quick-clamp punch holder for press brake tooling, reduces setup time.",
          sku="SP-PCH-QC", compatible_with="prod:press-brake-50t",
          list_price=420.00, stock_on_hand=18, source="zoho_inventory"),
    _prod("prod:laser-window-pack", "Fiber Laser Protective Window 10-pack",
          "10-pack of protective windows for SigmaMax fiber lasers, 25.4mm dia.",
          sku="SP-WIN-10", compatible_with="prod:fiber-laser-2kw",
          list_price=190.00, stock_on_hand=60, source="zoho_inventory"),
    _prod("prod:plasma-electrodes", "HyperCut Plasma Electrode 10-pack",
          "10-pack of electrodes for HyperCut plasma systems, 105A and 65A.",
          sku="SP-ELEC-10", list_price=95.00, stock_on_hand=80, source="zoho_inventory"),
    # -- Vendors (overlapping supply lists) --
    {
        "id": "contact:hypercut-systems", "type": "contact",
        "name": "HyperCut Systems Ltd.",
        "description": "Vendor supplying HyperCut plasma cutters and plasma consumables.",
        "properties": {"type": "vendor", "supplies": "prod:plasma-cutter-105a, prod:plasma-65a, prod:plasma-electrodes", "source": "zoho_books"},
    },
    {
        "id": "contact:laser-tech-global", "type": "contact",
        "name": "LaserTech Global GmbH",
        "description": "German vendor supplying the LaserTech Pro fiber laser platform.",
        "properties": {"type": "vendor", "supplies": "prod:fiber-laser-lt4kw", "source": "zoho_books"},
    },
    {
        "id": "contact:metal-form-group", "type": "contact",
        "name": "MetalForm Machinery Group",
        "description": "Vendor supplying MetalForm and BendMaster press brakes plus brake tooling.",
        "properties": {"type": "vendor", "supplies": "prod:press-brake-mfp60, prod:press-brake-bm220, prod:brake-punch-holder", "source": "zoho_books"},
    },
    # -- Customers + paraphrased leads --
    {
        "id": "contact:northline-steel", "type": "contact",
        "name": "Northline Steel Works",
        "description": "Structural steel fabricator, Mississauga.",
        "properties": {"type": "customer", "contact_person": "Dana White", "source": "zoho_books"},
    },
    {
        "id": "lead:harbor-folding-inquiry", "type": "lead",
        "name": "Harbor Machine Shop — folding machine inquiry",
        "description": "Harbor Machine Shop asked about a sheet-metal folding machine with a 90K budget.",
        "properties": {"product": "prod:press-brake-100t", "budget": "around $90K USD", "status": "new", "source": "outlook"},
    },
    {
        "id": "lead:vertex-rail-garnet", "type": "lead",
        "name": "Vertex Rail — thick plate cutting inquiry",
        "description": "Vertex Rail Components needs non-thermal cutting of 120mm rail plate without heat distortion.",
        "properties": {"product": "prod:waterjet-wj4015", "budget": "around $250K USD", "status": "new", "source": "outlook"},
    },
    {
        "id": "lead:precision-ag-thin-sheet", "type": "lead",
        "name": "Precision Ag Parts — thin sheet laser inquiry",
        "description": "Precision Ag Parts wants a budget laser under $90K for thin agricultural sheet parts.",
        "properties": {"product": "prod:fiber-laser-vc15", "budget": "under $90K USD", "status": "new", "source": "outlook"},
    },
]

HARD_RELATIONSHIPS: List[Dict[str, str]] = [
    {"from": "HyperCut Systems Ltd.", "to": "HyperCut 105A Plasma Cutter", "type": "supplies"},
    {"from": "HyperCut Systems Ltd.", "to": "HyperCut 65A Plasma Cutter", "type": "supplies"},
    {"from": "LaserTech Global GmbH", "to": "LaserTech Pro 4kW Fiber Laser", "type": "supplies"},
    {"from": "MetalForm Machinery Group", "to": "MetalForm Pro 60 Press Brake", "type": "supplies"},
    {"from": "MetalForm Machinery Group", "to": "BendMaster 220 Press Brake", "type": "supplies"},
    {"from": "Northline Steel Works", "to": "Harbor Machine Shop — folding machine inquiry", "type": "raised"},
    {"from": "Vertex Rail — thick plate cutting inquiry", "to": "WaterJet Dynamics WJ-4015", "type": "inquires_about"},
]


# --------------------------------------------------------------------------- #
# Hard question set — snippets are UNIQUE tokens among the distractors.
# --------------------------------------------------------------------------- #

HARD_SET: List[EvalQuestion] = [
    # -- attribute: disambiguate within a confusable family --
    EvalQuestion("What CNC controller does the 100-ton AccurPress press brake use?", ["DA-66T"], category="attribute"),
    EvalQuestion("What controller comes on the BendMaster 220?", ["ESA S640", "S640"], category="attribute"),
    EvalQuestion("List price of the SigmaMax 6kW fiber laser?", ["265,000", "265000"], category="attribute"),
    EvalQuestion("How much is the ValueCut 1.5kW compact laser?", ["89,000", "89000"], category="attribute"),
    EvalQuestion("Which press brake has a 4000mm bed?", ["BM-220", "BendMaster"], category="attribute"),
    EvalQuestion("How thick can the SigmaMax 3kW laser cut mild steel?", ["25mm"], category="attribute"),
    EvalQuestion("What is the cut capacity of the HyperCut 65A plasma?", ["PC-65A"], category="attribute"),
    EvalQuestion("Which CNC does the MetalForm Pro 60 use?", ["Cybelec", "DNC 60"], category="attribute"),
    EvalQuestion("Who supplies the LaserTech Pro 4kW fiber laser?", ["LaserTech Global"], category="attribute"),
    EvalQuestion("Which vendor supplies BendMaster press brakes?", ["MetalForm Machinery"], category="attribute"),
    EvalQuestion("How many ShopFold Entry 40 brakes are in stock?", ["SF-40"], category="attribute"),
    EvalQuestion("What diameter are the fiber laser protective windows?", ["25.4mm"], category="attribute"),
    # -- paraphrase: zero lexical overlap with the target name/description --
    EvalQuestion("machine for slicing sheet stock with a focused beam of light on a budget under ninety thousand", ["VC-1.5KW", "ValueCut", "89,000", "89000"], category="paraphrase"),
    EvalQuestion("non-thermal cutting process using high-pressure abrasive slurry for thick rail plate", ["WJ-4015", "WaterJet", "garnet"], category="paraphrase"),
    EvalQuestion("which machine forms bends in sheet metal along a straight line with a ninety thousand dollar budget", ["100-Ton", "BP-100T", "152,000", "152000"], category="paraphrase"),
    EvalQuestion("entry level bench machine for small workshop bending work", ["SF-40", "ShopFold", "34,800", "34800"], category="paraphrase"),
    EvalQuestion("consumable electrodes for arc-based cutting torches", ["SP-ELEC-10", "Electrode"], category="paraphrase"),
    EvalQuestion("spare optics that protect the cutting head of a light-based cutter", ["SP-WIN-10", "Protective Window"], category="paraphrase"),
    # -- distractor: strongest keyword matches the wrong sibling first --
    EvalQuestion("SigmaMax laser for 30mm mild steel", ["FL-6KW", "6kW"], category="distractor"),
    EvalQuestion("SigmaMax laser cutting 16mm stainless", ["FL-3KW", "3kW"], category="distractor"),
    EvalQuestion("HyperCut plasma under fifteen thousand dollars", ["PC-65A", "11,400", "11400"], category="distractor"),
    EvalQuestion("press brake tonnage above one hundred tons", ["125-ton", "BM-220", "100-ton", "BP-100T"], category="distractor"),
    EvalQuestion("cutting machine for 120mm plate that avoids heat distortion", ["WJ-4015", "WaterJet"], category="distractor"),
]


def _seed_hard_workspace(workspace_id: str) -> None:
    """Brennan golden entities + the distractor corpus, vector-mirrored."""
    _seed_eval_workspace(workspace_id)  # schema + brennan entities + vectors

    from core.graphrag_engine import GraphRAGEngine

    engine = GraphRAGEngine(workspace_id=workspace_id)
    engine.ingest_structured_data(entities=HARD_CORPUS, relationships=HARD_RELATIONSHIPS)
    engine.backfill_node_vectors(workspace_id)


async def evaluate_hard(workspace_id: str = None) -> EvalReport:
    """Run HARD_SET through the same public retrieval path as the main gate."""
    import uuid as _uuid

    workspace_id = workspace_id or f"memory-eval-hard-{_uuid.uuid4().hex[:8]}"
    report = EvalReport()
    await asyncio.to_thread(_seed_hard_workspace, workspace_id)

    from core.graphrag_engine import GraphRAGEngine

    engine = GraphRAGEngine(workspace_id=workspace_id)

    for q in HARD_SET:
        context = ""
        try:
            context = await engine.get_context_for_ai(query=q.question)
        except Exception as e:
            logger.warning(f"hard eval: retrieval failed for {q.question!r}: {e}")
        matched = next(
            (s for s in q.expected_snippets if s.lower() in (context or "").lower()),
            None,
        )
        report.results.append(EvalResult(
            question=q.question,
            hit=matched is not None,
            category=q.category,
            matched_snippet=matched,
            context_chars=len(context or ""),
        ))
    return report


if __name__ == "__main__":
    import json as _json

    _report = asyncio.run(evaluate_hard())
    print(_json.dumps(_report.summary(), indent=2))
