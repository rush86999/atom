#!/usr/bin/env python3
import os
import sys
import json
import re
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add backend to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from core.database import DATABASE_URL
from core.models import IntegrationCatalog, Base

def parse_ts_to_json(file_path):
    """Extracts the JSON array from a TypeScript export file"""
    try:
        content = Path(file_path).read_text(encoding="utf-8")
        # Match the array part: export const NAME: Type[] = [ ... ];
        match = re.search(r'=\s*(\[[\s\S]*\]);', content)
        if not match:
            print("Error: Could not find JSON array in {}".format(file_path))
            return []
        
        json_str = match.group(1)
        # Clean up any trailing commas that JSON doesn't like but TS does
        json_str = re.sub(r',(\s*[\]\}])', r'\1', json_str)
        return json.loads(json_str)
    except Exception as e:
        print("Error parsing {}: {}".format(file_path, e))
        return []

# Map Activepieces IDs to native Atom IDs
NATIVE_MAPPING = {
    "@activepieces/piece-slack": "slack",
    "@activepieces/piece-gmail": "gmail",
    "@activepieces/piece-asana": "asana",
    "@activepieces/piece-notion": "notion",
    "@activepieces/piece-hubspot": "hubspot",
    "@activepieces/piece-salesforce": "salesforce",
    "@activepieces/piece-github": "github",
    "@activepieces/piece-discord": "discord",
    "@activepieces/piece-stripe": "stripe",
    "@activepieces/piece-jira": "jira",
    "@activepieces/piece-zendesk": "zendesk",
    "@activepieces/piece-zoom": "zoom",
    "@activepieces/piece-google-calendar": "google_calendar",
    "@activepieces/piece-google-drive": "google_drive",
    "@activepieces/piece-dropbox": "dropbox",
    "@activepieces/piece-trello": "trello",
    "@activepieces/piece-airtable": "airtable",
    "@activepieces/piece-calendly": "calendly",
    "@activepieces/piece-mailchimp": "mailchimp",
    "@activepieces/piece-shopify": "shopify",
    "@activepieces/piece-quickbooks": "quickbooks",
    "@activepieces/piece-xero": "xero",
    "@activepieces/piece-linear": "linear",
    "@activepieces/piece-figma": "figma",
    "@activepieces/piece-openai": "openai",
}

def seed_integrations():
    print(f"Connecting to database: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Ensure table exists (though migrations should handle this)
    Base.metadata.create_all(engine)

    # Path to the auto-generated pieces
    ts_file = Path(__file__).parent.parent.parent / "frontend-nextjs" / "lib" / "auto-generated-pieces.ts"
    
    if not ts_file.exists():
        print(f"Error: {ts_file} not found. Run update-catalog.py first.")
        return

    pieces = parse_ts_to_json(ts_file)
    print(f"Found {len(pieces)} pieces in {ts_file}")

    # Add manual pieces if missing from auto-generated list
    # For now, we trust the auto-generated list + our deduplication logic
    
    count = 0
    for p in pieces:
        # Check if already exists
        existing = session.query(IntegrationCatalog).filter_by(id=p['id']).first()
        
        if existing:
            # Update
            existing.name = p['name']
            existing.description = p.get('description', '')
            existing.category = p['category']
            existing.icon = p.get('icon', '')
            existing.color = p.get('color', '#6366F1')
            existing.auth_type = p.get('authType', 'none')
            existing.triggers = p.get('triggers', [])
            existing.actions = p.get('actions', [])
            existing.native_id = NATIVE_MAPPING.get(p['id'])
        else:
            # Insert
            new_piece = IntegrationCatalog(
                id=p['id'],
                name=p['name'],
                description=p.get('description', ''),
                category=p['category'],
                icon=p.get('icon', ''),
                color=p.get('color', '#6366F1'),
                auth_type=p.get('authType', 'none'),
                triggers=p.get('triggers', []),
                actions=p.get('actions', []),
                native_id=NATIVE_MAPPING.get(p['id'])
            )
            session.add(new_piece)
        
        count += 1
        if count % 100 == 0:
            session.commit()
            print(f"Processed {count} pieces...")

    session.commit()
    print(f"Successfully seeded {count} integrations into the database.")
    session.close()

if __name__ == "__main__":
    seed_integrations()
