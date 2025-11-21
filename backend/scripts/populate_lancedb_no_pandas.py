#!/usr/bin/env python3
"""
Populate LanceDB WITHOUT pandas dependency
Uses only pyarrow and lancedb
"""

import sys
import os

# Test pyarrow first
try:
    import pyarrow as pa
    print(f"✅ PyArrow {pa.__version__} loaded")
except ImportError as e:
    print(f"❌ PyArrow not available: {e}")
    sys.exit(1)

# Now import lancedb WITHOUT triggering pandas
try:
    # Set environment variable to prevent pandas import if possible
    os.environ['LANCE_BYPASS_PANDAS'] = '1'
    
    import lancedb
    print(f"✅ LanceDB loaded")
except ImportError as e:
    print(f"❌ LanceDB not available: {e}")
    sys.exit(1)

def populate_lancedb():
    """Populate LanceDB using pure PyArrow data structures"""
    
    db_path = os.path.expanduser("~/atom_lancedb")
    print(f"\n📂 Connecting to LanceDB at: {db_path}")
    
    db = lancedb.connect(db_path)
    print("✅ Connected to LanceDB")
    
    # Define schema using PyArrow
    schema = pa.schema([
        pa.field("id", pa.string()),
        pa.field("text", pa.string()),
        pa.field("source", pa.string()),
        pa.field("metadata", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), 384))  # Using 384 for sentence-transformers
    ])
    
    # Create mock embeddings (384 dimensions)
    mock_vec = [0.1] * 384
    
    # Prepare data as PyArrow Table (NO PANDAS)
    data = {
        "id": ["doc_1", "doc_2", "meeting_1", "meeting_2", "task_1", "task_2"],
        "text": [
            "Q4 Marketing Strategy focuses on organic growth through content marketing and SEO optimization.",
            "API Documentation v2.0: All endpoints now require Bearer token authentication.",
            "Meeting Transcript: Team discussed the new frontend architecture. Decided to migrate to Next.js 14.",
            "Client Call Notes: Client requested a new feature for exporting reports to PDF.",
            "Task: Fix the login page layout issue on mobile devices.",
            "Task: Update the database schema to support multi-tenant architecture."
        ],
        "source": ["document", "document", "meeting", "meeting", "task", "task"],
        "metadata": [
            '{"title": "Q4 Marketing Plan"}',
            '{"title": "API Docs v2.0"}',
            '{"title": "Frontend Architecture Review"}',
            '{"title": "Weekly Client Sync"}',
            '{"title": "Fix Mobile Login"}',
            '{"title": "DB Schema Migration"}'
        ],
        "vector": [mock_vec] * 6
    }
    
    # Create PyArrow table directly
    table = pa.table(data, schema=schema)
    print(f"\n✅ Created PyArrow table with {table.num_rows} rows")
    
    # Create or overwrite the LanceDB table
    table_name = "document_chunks"
    if table_name in db.table_names():
        print(f"⚠️  Table '{table_name}' exists, dropping...")
        db.drop_table(table_name)
    
    lance_table = db.create_table(table_name, table)
    print(f"✅ Created LanceDB table '{table_name}'")
    
    # Verify
    count = lance_table.count_rows()
    print(f"✅ Table contains {count} rows")
    
    # Test search
    print("\n🔍 Testing search...")
    results = lance_table.search(mock_vec).limit(2).to_arrow()
    print(f"✅ Search returned {results.num_rows} results")
    
    print("\n" + "="*50)
    print("✅ LanceDB POPULATED SUCCESSFULLY!")
    print(f"Database path: {db_path}")
    print(f"Table: {table_name}")
    print(f"Rows: {count}")
    print("="*50)

if __name__ == "__main__":
    try:
        populate_lancedb()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
