#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from tools.supabase_client import sb
import json

property_id = "839134f3-302f-4e00-b2e9-6a5c1c177fd1"
template_key = "R2B"

print(f"\n=== Checking structure for {property_id} / {template_key} ===\n")

# Get structure
result = sb.rpc("get_numbers_template_structure", {
    "p_property_id": property_id,
    "p_template_key": template_key
}).execute()

if result.data:
    structure = result.data
    cells = structure.get("cells", [])
    print(f"Total cells in structure: {len(cells)}")
    
    # Count formulas
    formula_cells = [c for c in cells if c.get("formula")]
    print(f"Cells with formulas: {len(formula_cells)}")
    
    # Show formula cells
    print("\n=== Formula cells ===")
    for cell in formula_cells[:10]:
        print(f"{cell['address']}: {cell.get('formula', 'NONE')[:80]}")
    
    # Check specific cells
    print("\n=== Checking B5, C5, D5, E5 ===")
    for addr in ["B5", "C5", "D5", "E5"]:
        cell = next((c for c in cells if c.get("address") == addr), None)
        if cell:
            print(f"{addr}: formula={cell.get('formula', 'NONE')}, value={cell.get('value', 'NONE')}")
        else:
            print(f"{addr}: NOT FOUND")
else:
    print("No structure found!")
