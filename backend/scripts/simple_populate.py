import lancedb
import pyarrow as pa
import os
import shutil

def populate():
    print("Initializing LanceDB...")
    db_path = "/tmp/atom_lancedb_simple"
    if os.path.exists(db_path):
        shutil.rmtree(db_path)
    
    db = lancedb.connect(db_path)
    
    # Define schema explicitly to avoid pandas inference
    schema = pa.schema([
        pa.field("id", pa.string()),
        pa.field("text", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), 384))
    ])
    
    print("Creating table...")
    # Mock embedding
    mock_vec = [0.1] * 384
    
    data = [
        {"id": "1", "text": "Document 1", "vector": mock_vec},
        {"id": "2", "text": "Document 2", "vector": mock_vec}
    ]
    
    tbl = db.create_table("test_table", data=data, schema=schema)
    print(f"Table created with {tbl.count_rows()} rows")
    
    print("Searching...")
    res = tbl.search(mock_vec).limit(1).to_list()
    print(f"Search result: {res}")

if __name__ == "__main__":
    populate()
