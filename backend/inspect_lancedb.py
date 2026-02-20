
import os
import lancedb

# Path to LanceDB (default based on common env vars)
DB_PATH = "./data/atom_memory/default_shared"


def inspect_paths():
    paths = [
        "./data/atom_memory/default_shared",
        "./data/atom_memory/default"
    ]
    
    for path in paths:
        print(f"\n--- Inspecting LanceDB at: {path} ---")
        if not os.path.exists(path):
            print("❌ Path does not exist!")
            continue

        try:
            db = lancedb.connect(path)
            tables = db.table_names()
            print(f"found tables: {tables}")
            
            if "documents" in tables:
                tbl = db.open_table("documents")
                count = len(tbl)
                print(f"✅ 'documents' table has {count} records.")
                
                if count > 0:
                    import pandas as pd
                    pd.set_option('display.max_colwidth', None)
                    pd.set_option('display.width', 1000)
                    
                    df = tbl.search().limit(5).to_pandas()
                    if 'created_at' in df.columns:
                        df = df.sort_values(by='created_at', ascending=False)
                    
                    # Print more rows and specific columns to find the missing document
                    print(f"Total documents: {len(df)}")
                    print(df[['id', 'user_id', 'workspace_id', 'text', 'metadata']].to_string())
            else:
                 print("⚠️ 'documents' table not found.")
        except Exception as e:
            print(f"❌ Error: {e}")



if __name__ == "__main__":
    inspect_paths()
