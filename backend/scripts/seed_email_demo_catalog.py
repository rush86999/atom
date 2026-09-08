"""Seed the email-send policy demo data (DEV ONLY).

Populates the workspace's machine catalog (business_product_services) and
known customers (ecommerce_customers) from the demo Brennan Machinery
mailbox threads so the policy gate's alternatives / customer-intro rules can
be verified against real data.

Data notes (transparency): model ids + categories are taken from the live
demo mailbox + repo fixtures (SR48P/PH-52 shears, Sotchman 50514-EC
ironworker, EN100 tube bender, Baxter 115C / WG-350DSAV bandsaws, TK-2450
slip roll). base_price is intentionally NOT set here (no observed price
list in the local data — the consolidated list sheet is a separate
workstream); the price gate stays param-verified until the real catalog is
ingested. Every row is marked metadata.demo_seed=true + source.

Idempotent: rows are matched on external_id and never duplicated. Refuses
to run unless ENVIRONMENT=development.
"""
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("seed_email_demo_catalog")

TENANT = WORKSPACE = "default"

# (external_id, name, description, category) — model codes/categories from the
# demo mailbox threads; brand names deliberately omitted; all placeholder data.
MACHINES = [
    ("demo-SR48P", "SR48P", "SR48P shear", "shears"),
    ("demo-PH-52", "PH-52", "PH-52 shear (52-inch class)", "shears"),
    ("demo-50514-EC", "50514-EC", "50-ton single operator ironworker", "ironworkers"),
    ("demo-EN100", "EN100", "EN100 pipe & tube bender", "tube_benders"),
    ("demo-115C", "115C", "115C bandsaw", "bandsaws"),
    ("demo-WG-350DSAV", "WG-350DSAV", "WG-350DSAV bandsaw", "bandsaws"),
    ("demo-TK-2450-STAND", "TK-2450-STAND", "TK2450 slip roll stand", "slip_rolls"),
]

# (email, first_name, last_name, is_b2b) — SYNTHETIC placeholders only. Never
# commit real counterparty PII from the demo mailbox into this public repo.
CUSTOMERS = [
    ("buyer.one@example.com", "Alex", "Morgan", True),
    ("buyer.two@example.com", "Jordan", "Casey", True),
]


def main() -> int:
    from core.database import get_db_session  # noqa: F401 — triggers env/settings load
    from core.models import BusinessProductService, EcommerceCustomer

    env = os.getenv("ENVIRONMENT", "").lower()
    if env != "development":
        logger.error("Refusing to run outside development (ENVIRONMENT=%r)", env)
        return 2

    added_machines = 0
    added_customers = 0
    removed = 0
    with get_db_session() as db:
        # Replace semantics for demo rows: clear every previous demo_seed row
        # first (idempotent + keeps the dev DB in sync when this script evolves;
        # non-demo rows are never touched).
        for row in db.query(BusinessProductService).all():
            if (row.metadata_json or {}).get("demo_seed"):
                db.delete(row)
                removed += 1
        for row in db.query(EcommerceCustomer).all():
            if (row.metadata_json or {}).get("demo_seed"):
                db.delete(row)
                removed += 1

        for ext_id, name, description, category in MACHINES:
            db.add(BusinessProductService(
                tenant_id=TENANT,
                workspace_id=WORKSPACE,
                external_id=ext_id,
                name=name,
                type="product",
                description=description,
                currency="CAD",
                metadata_json={
                    "demo_seed": True,
                    "category": category,
                    "source": "synthetic demo seed 2026-09-08 (no real PII)",
                },
            ))
            added_machines += 1

        for email, first, last, b2b in CUSTOMERS:
            db.add(EcommerceCustomer(
                tenant_id=TENANT,
                email=email,
                first_name=first,
                last_name=last,
                is_b2b=b2b,
                metadata_json={
                    "demo_seed": True,
                    "source": "synthetic demo seed 2026-09-08 (no real PII)",
                },
            ))
            added_customers += 1

        db.commit()
        m_total = db.query(BusinessProductService).count()
        c_total = db.query(EcommerceCustomer).count()

    logger.info("removed previous demo rows=%d | machines=%d (total=%d) | customers=%d (total=%d)",
                removed, added_machines, m_total, added_customers, c_total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
