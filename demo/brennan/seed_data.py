"""
Brennan.ca demo seed data.

Metal-fabrication machinery distributor scenario. Entities are written directly into
the knowledge graph (GraphNode/GraphEdge) so the agent "remembers" them immediately —
this is what the agent actually queries (the Zoho/Shopify adapters are read-only for
products/items, so seeding via those APIs isn't possible; the knowledge graph is the
source of truth the agent uses for recall).

All values are fictional demo data for brennan.ca.
"""

from typing import Any, Dict, List

WORKSPACE_ID = "brennan-demo"

# ---------------------------------------------------------------------------
# Product catalog (machines + spare parts)
# ---------------------------------------------------------------------------
PRODUCTS: List[Dict[str, Any]] = [
    {
        "id": "prod:press-brake-50t",
        "type": "product",
        "name": "AccurPress 50-Ton CNC Press Brake",
        "properties": {
            "sku": "BP-50T",
            "category": "press_brake",
            "tonnage": "50 ton",
            "bed_length": "2500mm",
            "list_price": 84500.00,
            "currency": "USD",
            "stock_on_hand": 3,
            "reorder_point": 1,
            "source": "zoho_inventory",
            "description": "50-ton CNC press brake with 2500mm bed, Delem DA-58T control.",
        },
    },
    {
        "id": "prod:fiber-laser-2kw",
        "type": "product",
        "name": "SigmaMax 2kW Fiber Laser Cutter",
        "properties": {
            "sku": "FL-2KW",
            "category": "laser",
            "max_material_thickness_steel": "20mm",
            "bed_size": "1500x3000mm",
            "list_price": 128000.00,
            "currency": "USD",
            "stock_on_hand": 2,
            "reorder_point": 1,
            "source": "zoho_inventory",
            "description": "2kW fiber laser, cuts up to 20mm mild steel, 12mm stainless.",
        },
    },
    {
        "id": "prod:plasma-cutter-105a",
        "type": "product",
        "name": "HyperCut 105A Plasma Cutter",
        "properties": {
            "sku": "PC-105A",
            "category": "plasma",
            "max_cut_capacity": "32mm",
            "list_price": 18900.00,
            "currency": "USD",
            "stock_on_hand": 5,
            "reorder_point": 2,
            "source": "zoho_inventory",
            "description": "105A plasma cutting system, 32mm clean cut capacity.",
        },
    },
    {
        "id": "prod:brake-die-set",
        "type": "product",
        "name": "Press Brake Multi-V Die Set (8-way)",
        "properties": {
            "sku": "SP-DIE-8W",
            "category": "spare_part",
            "compatible_with": "prod:press-brake-50t",
            "list_price": 1250.00,
            "currency": "USD",
            "stock_on_hand": 12,
            "reorder_point": 5,
            "source": "zoho_inventory",
            "description": "8-way multi-V die set, fits 50-ton press brake.",
        },
    },
    {
        "id": "prod:laser-nozzle-pack",
        "type": "product",
        "name": "Fiber Laser Nozzle Pack (10-pack, 2.0mm)",
        "properties": {
            "sku": "SP-NOZ-20",
            "category": "consumable",
            "compatible_with": "prod:fiber-laser-2kw",
            "list_price": 340.00,
            "currency": "USD",
            "stock_on_hand": 40,
            "reorder_point": 15,
            "source": "zoho_inventory",
            "description": "10-pack of 2.0mm nozzles for SigmaMax fiber laser.",
        },
    },
]

# ---------------------------------------------------------------------------
# Contacts: a sample customer + a vendor
# ---------------------------------------------------------------------------
CUSTOMERS: List[Dict[str, Any]] = [
    {
        "id": "contact:acme-fab",
        "type": "contact",
        "name": "ACME Fabrication Inc.",
        "properties": {
            "email": "purchasing@acmefab.com",
            "contact_person": "Sarah Chen",
            "contact_email": "sarah.chen@acmefab.com",
            "phone": "+1-416-555-0142",
            "address": "2400 Industrial Pkwy, Mississauga, ON",
            "type": "customer",
            "source": "zoho_books",
        },
    },
]

VENDORS: List[Dict[str, Any]] = [
    {
        "id": "contact:sigmamax-mfg",
        "type": "contact",
        "name": "SigmaMax Manufacturing",
        "properties": {
            "email": "support@sigmamaxmfg.com",
            "contact_person": "James Okafor",
            "contact_email": "james@sigmamaxmfg.com",
            "type": "vendor",
            "supplies": "prod:fiber-laser-2kw, prod:laser-nozzle-pack",
            "source": "zoho_books",
        },
    },
]

# ---------------------------------------------------------------------------
# Seed leads / inquiries (for the Sales Coordinator video)
# ---------------------------------------------------------------------------
LEADS: List[Dict[str, Any]] = [
    {
        "id": "lead:acme-press-brake-inquiry",
        "type": "lead",
        "name": "ACME Fab — 50-ton press brake inquiry",
        "properties": {
            "from_contact": "contact:acme-fab",
            "product": "prod:press-brake-50t",
            "budget": "around $80K USD",
            "timeline": "need delivery within 8 weeks",
            "source": "outlook",
            "status": "new",
            "note": "Sarah Chen emailed asking for a quote on the 50-ton press brake, delivery within 8 weeks.",
        },
    },
]

# ---------------------------------------------------------------------------
# Relationships (edges between the entities above)
# GraphRAGEngine.ingest_structured_data maps edges by entity NAME via `from`/`to`/`type`.
# ---------------------------------------------------------------------------
RELATIONSHIPS: List[Dict[str, Any]] = [
    # Vendors supply products
    {"from": "SigmaMax Manufacturing", "to": "SigmaMax 2kW Fiber Laser Cutter", "type": "supplies"},
    {"from": "SigmaMax Manufacturing", "to": "Fiber Laser Nozzle Pack (10-pack, 2.0mm)", "type": "supplies"},
    # Spare parts / consumables are compatible with machines
    {"from": "Press Brake Multi-V Die Set (8-way)", "to": "AccurPress 50-Ton CNC Press Brake", "type": "compatible_with"},
    {"from": "Fiber Laser Nozzle Pack (10-pack, 2.0mm)", "to": "SigmaMax 2kW Fiber Laser Cutter", "type": "compatible_with"},
    # ACME Fab inquired about the press brake
    {"from": "ACME Fabrication Inc.", "to": "ACME Fab — 50-ton press brake inquiry", "type": "raised"},
    {"from": "ACME Fab — 50-ton press brake inquiry", "to": "AccurPress 50-Ton CNC Press Brake", "type": "inquires_about"},
]

# ---------------------------------------------------------------------------
# Office template placeholder tokens
# Word templates use literal substring replacement (WordManager.modify_document).
# Excel templates use /Sheet/Cell paths (ExcelManager.write_cell).
# ---------------------------------------------------------------------------
WORD_PLACEHOLDERS = {
    "Quote.docx": {
        "<<CLIENT_NAME>>": "client_name",
        "<<CLIENT_ADDRESS>>": "client_address",
        "<<QUOTE_NUMBER>>": "quote_number",
        "<<QUOTE_DATE>>": "quote_date",
        "<<PRODUCT_DESCRIPTION>>": "product_description",
        "<<QUANTITY>>": "quantity",
        "<<UNIT_PRICE>>": "unit_price",
        "<<TOTAL>>": "total",
    },
    "Invoice.docx": {
        "<<CLIENT_NAME>>": "client_name",
        "<<INVOICE_NUMBER>>": "invoice_number",
        "<<INVOICE_DATE>>": "invoice_date",
        "<<ORDER_ID>>": "order_id",
        "<<AMOUNT_DUE>>": "amount_due",
    },
    "PurchaseOrder.docx": {
        "<<VENDOR_NAME>>": "vendor_name",
        "<<PO_NUMBER>>": "po_number",
        "<<PO_DATE>>": "po_date",
        "<<PART_NUMBER>>": "part_number",
        "<<PART_DESCRIPTION>>": "part_description",
        "<<PO_QUANTITY>>": "po_quantity",
        "<<PO_UNIT_PRICE>>": "po_unit_price",
    },
    "SpecSheet.docx": {
        "<<MACHINE_MODEL>>": "machine_model",
        "<<MAX_CAPACITY>>": "max_capacity",
        "<<BED_SIZE>>": "bed_size",
        "<<POWER>>": "power",
        "<<CONTROL_SYSTEM>>": "control_system",
    },
}

EXCEL_TEMPLATES = {
    "PriceList.xlsx": {
        "sheet": "PriceList",
        "cells": [
            # (cell_path, demo_value, is_formula)
            ("/PriceList/A1", "Brennan.ca — Price List", False),
            ("/PriceList/A3", "SKU", False),
            ("/PriceList/B3", "Product", False),
            ("/PriceList/C3", "List Price (USD)", False),
            ("/PriceList/D3", "Stock", False),
            ("/PriceList/A4", "BP-50T", False),
            ("/PriceList/B4", "AccurPress 50-Ton CNC Press Brake", False),
            ("/PriceList/C4", 84500.00, False),
            ("/PriceList/D4", 3, False),
            ("/PriceList/A5", "FL-2KW", False),
            ("/PriceList/B5", "SigmaMax 2kW Fiber Laser Cutter", False),
            ("/PriceList/C5", 128000.00, False),
            ("/PriceList/D5", 2, False),
            ("/PriceList/A6", "PC-105A", False),
            ("/PriceList/B6", "HyperCut 105A Plasma Cutter", False),
            ("/PriceList/C6", 18900.00, False),
            ("/PriceList/D6", 5, False),
            ("/PriceList/A8", "Total Inventory Value", False),
            ("/PriceList/C8", "=SUM(C4:C6)", True),
        ],
    },
}
