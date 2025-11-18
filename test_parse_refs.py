#!/usr/bin/env python3
import re

def parse_cell_references(formula: str):
    if not formula or not formula.startswith("="):
        return set()
    pattern = r'\b([A-Z]+\d+)\b'
    matches = re.findall(pattern, formula, re.IGNORECASE)
    return set(m.upper() for m in matches)

# Test with actual formulas
formulas = [
    '=IF(OR(B5="",C5=""),"",B5*C5/100)',
    '=IF(B5="","",B5+D5)',
]

for f in formulas:
    refs = parse_cell_references(f)
    print(f"Formula: {f}")
    print(f"  Refs: {refs}\n")
