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

# (external_id, name, description, category)
MACHINES = [
    ("demo-SR48P", "SR48P", "Tennsmith SR48P shear", "shears"),
    ("demo-PH-52", "PH-52", "PH-52 shear (52-inch class)", "shears"),
    ("demo-50514-EC", "50514-EC", "Sotchman 50-ton single operator ironworker", "ironworkers"),
    ("demo-EN100", "EN100", "EN100 pipe & tube bender", "tube_benders"),
    ("demo-BAXTER-115C", "BAXTER-115C", "Baxter 115C bandsaw", "bandsaws"),
    ("demo-WG-350DSAV", "WG-350DSAV", "WG-350DSAV bandsaw", "bandsaws"),
    ("demo-TK-2450-STAND", "TK-2450-STAND", "TK2450 slip roll stand (TAAG)", "slip_rolls"),
]

# (email, first_name, last_name, is_b2b)
CUSTOMERS = [
    ("aforrest@cbnco.com", "Andrew", "Forrester", True),
    ("mkellam@wfsltd.ca", "Mark", "Kellam", True),
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
    with get_db_session() as db:
        existing = {
            str(r).lower()
            for (r,) in db.query(BusinessProductService.external_id).all()
            if r
        }
        for ext_id, name, description, category in MACHINES:
            if ext_id.lower() in existing:
                continue
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
                    "source": "demo mailbox + repo fixtures 2026-09-08",
                },
            ))
            added_machines += 1

        known_emails = {str(e).lower() for (e,) in db.query(EcommerceCustomer.email).all() if e}
        for email, first, last, b2b in CUSTOMERS:
            if email.lower() in known_emails:
                continue
            db.add(EcommerceCustomer(
                tenant_id=TENANT,
                email=email,
                first_name=first,
                last_name=last,
                is_b2b=b2b,
                metadata_json={
                    "demo_seed": True,
                    "source": "demo mailbox + repo fixtures 2026-09-08",
                },
            ))
            added_customers += 1

        db.commit()
        m_total = db.query(BusinessProductService).count()
        c_total = db.query(EcommerceCustomer).count()

    logger.info("machines added=%d (total=%d) | customers added=%d (total=%d)",
                added_machines, m_total, added_customers, c_total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
