from tools.formula_calculator import recalculate_all_formulas


def test_d5_e5_cascade_minimal_structure():
    # Minimal structure with necessary formulas only.
    structure = {
        "cells": [
            {"address": "D5", "formula": "=B5*C5/100"},
            {"address": "E5", "formula": "=B5+D5"},
        ]
    }
    current = {"B5": {"value": "3000"}, "C5": {"value": "15"}}
    calc = recalculate_all_formulas("prop", "R2B", structure, current)
    assert float(calc["D5"]) == 450.0
    assert float(calc["E5"]) == 3450.0

