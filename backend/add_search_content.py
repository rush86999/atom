import logging
import sys
import uuid
from datetime import datetime
from core.lancedb_handler import get_lancedb_handler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def add_content():
    print("\n=== Add Content to LanceDB Search ===")
    print("Type 'exit' at any prompt to quit.\n")

    handler = get_lancedb_handler()
    if not handler.db:
        print("ERROR: Could not connect to LanceDB. Check your configuration.")
        return

    while True:
        try:
            title = input("Enter Title: ").strip()
            if title.lower() == 'exit': break
            if not title:
                print("Title cannot be empty.")
                continue

            print("Enter Content (press Enter twice to finish):")
            lines = []
            while True:
                line = input()
                if not line and lines: # Stop on empty line if we have content
                    break
                if not line and not lines: # Don't stop if first line is empty, wait for content
                    continue
                lines.append(line)
            
            content = "\n".join(lines).strip()
            if content.lower() == 'exit': break
            
            doc_type = input("Enter Doc Type (document, meeting, note, email, pdf) [note]: ").strip().lower()
            if not doc_type: doc_type = "note"

            # Create document record
            doc_id = str(uuid.uuid4())
            doc = {
                "id": doc_id,
                "text": content,
                "metadata": {
                    "title": title,
                    "doc_type": doc_type,
                    "created_at": datetime.now().isoformat(),
                    "source": "manual_entry",
                    "author": "User"
                },
                "user_id": "user-123" # Match frontend-nextjs mock user ID
            }

            print(f"\nAdding document '{title}'...")
            count = handler.add_documents_batch("documents", [doc])
            
            if count > 0:
                print(f"✅ Successfully added document (ID: {doc_id})")
                print("You can now search for this content in the UI.")
            else:
                print("❌ Failed to add document.")
            
            print("\n-----------------------------------")

        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            break

if __name__ == "__main__":
    add_content()
