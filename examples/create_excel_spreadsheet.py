"""
Example: Create an Excel spreadsheet with formulas via the workbook runtime.

Demonstrates that Atom evaluates formulas (not just stores them as strings).

Prerequisites:
  - Atom backend running on http://localhost:8000

Run:
  python examples/create_excel_spreadsheet.py
"""

import httpx
import os
import sys

BASE_URL = os.getenv("ATOM_BASE_URL", "http://localhost:8000")
FILE_PATH = "data/demo_spreadsheet.xlsx"

async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60) as client:
        # Create a spreadsheet with data and formulas
        print("1. Creating spreadsheet with formulas...")
        cells = [
            {"path": "/Sheet1/A1", "value": 10},
            {"path": "/Sheet1/A2", "value": 20},
            {"path": "/Sheet1/A3", "value": 30},
            {"path": "/Sheet1/A4", "value": "=SUM(A1:A3)", "is_formula": True},
            {"path": "/Sheet1/A5", "value": "=AVERAGE(A1:A3)", "is_formula": True},
            {"path": "/Sheet1/B1", "value": "=A1*2", "is_formula": True},
        ]

        for cell in cells:
            payload = {
                "file_path": FILE_PATH,
                "cell_path": cell["path"],
                "value": cell["value"],
            }
            if cell.get("is_formula"):
                payload["is_formula"] = True

            resp = await client.post("/api/v1/office/excel", json=payload)
            result = resp.json()
            if result.get("success"):
                computed = result.get("value")
                formula = result.get("formula")
                if formula:
                    print(f"   {cell['path']}: {formula} → {computed}")
                else:
                    print(f"   {cell['path']}: {computed}")

        # Read back with evaluated values
        print("\n2. Reading evaluated range...")
        resp = await client.get("/api/v1/office/excel", params={
            "file_path": FILE_PATH,
            "cell_path": "/Sheet1/A1:A5",
        })
        result = resp.json()
        if result.get("success"):
            print(f"   ✅ Range data: {result.get('entities', result.get('values', 'N/A'))}")

        # Get formula result explicitly
        print("\n3. Getting formula result for A4 (=SUM)...")
        resp = await client.get("/api/v1/office/excel/formula-result", params={
            "file_path": FILE_PATH,
            "cell_path": "/Sheet1/A4",
        })
        result = resp.json()
        if result.get("success"):
            values = result.get("values", [])
            print(f"   ✅ A4 evaluates to: {values}")
        else:
            print(f"   Result: {result}")

        print(f"\n✅ Spreadsheet saved to {FILE_PATH}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
