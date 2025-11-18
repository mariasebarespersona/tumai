"""
Ultra-simple formula calculator for R2B template.

Instead of parsing complex Excel formulas, we just hardcode the R2B formula logic.
This is pragmatic and works 100% reliably.
"""

import logging
import re
from typing import Dict, Any, Optional, Set, List

logger = logging.getLogger(__name__)


def get_cell_value(cell_addr: str, values: Dict[str, Any]) -> Optional[float]:
    """Get numeric value from a cell, handling dict format from DB."""
    value = values.get(cell_addr)
    
    if value is None:
        return None
    
    # Extract from dict if needed
    if isinstance(value, dict):
        value = value.get("value", "")
    
    # Handle empty
    if value == "" or value is None:
        return None
    
    # Convert to float
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def evaluate_r2b_formula(cell_addr: str, values: Dict[str, Any]) -> Optional[float]:
    """Evaluate a specific R2B formula cell.
    
    Hardcoded logic for each R2B formula cell.
    """
    
    # IVA calculations (D column)
    if cell_addr == "D5":
        B5 = get_cell_value("B5", values)
        C5 = get_cell_value("C5", values)
        if B5 is None or C5 is None:
            return None
        return B5 * C5 / 100
    
    elif cell_addr == "D6":
        B6 = get_cell_value("B6", values)
        C6 = get_cell_value("C6", values)
        if B6 is None or C6 is None:
            return None
        return B6 * C6 / 100
    
    elif cell_addr == "D7":
        B7 = get_cell_value("B7", values)
        C7 = get_cell_value("C7", values)
        if B7 is None or C7 is None:
            return None
        return B7 * C7 / 100
    
    elif cell_addr == "D8":
        B8 = get_cell_value("B8", values)
        C8 = get_cell_value("C8", values)
        if B8 is None or C8 is None:
            return None
        return B8 * C8 / 100
    
    # Total with VAT (E column)
    elif cell_addr == "E5":
        B5 = get_cell_value("B5", values)
        D5 = get_cell_value("D5", values)
        if B5 is None:
            return None
        if D5 is None:
            D5 = 0  # If D5 not calculated yet, use 0
        return B5 + D5
    
    elif cell_addr == "E6":
        B6 = get_cell_value("B6", values)
        D6 = get_cell_value("D6", values)
        if B6 is None:
            return None
        if D6 is None:
            D6 = 0
        return B6 + D6
    
    elif cell_addr == "E7":
        B7 = get_cell_value("B7", values)
        D7 = get_cell_value("D7", values)
        if B7 is None:
            return None
        if D7 is None:
            D7 = 0
        return B7 + D7
    
    elif cell_addr == "E8":
        B8 = get_cell_value("B8", values)
        D8 = get_cell_value("D8", values)
        if B8 is None:
            return None
        if D8 is None:
            D8 = 0
        return B8 + D8
    
    # Profit calculations
    elif cell_addr == "B10":
        B6 = get_cell_value("B6", values)
        B7 = get_cell_value("B7", values)
        B8 = get_cell_value("B8", values)
        if B6 is None:
            return None
        if B7 is None:
            B7 = 0
        if B8 is None:
            B8 = 0
        return B6 - B7 - B8
    
    elif cell_addr == "B12":
        B10 = get_cell_value("B10", values)
        B11 = get_cell_value("B11", values)
        if B10 is None:
            return None
        if B11 is None:
            B11 = 0
        return B10 + B11
    
    elif cell_addr == "B13":
        B12 = get_cell_value("B12", values)
        if B12 is None:
            return None
        return B12 * 0.25
    
    elif cell_addr == "B14":
        B13 = get_cell_value("B13", values)
        if B13 is None:
            return None
        return B13
    
    elif cell_addr == "B15":
        B12 = get_cell_value("B12", values)
        B14 = get_cell_value("B14", values)
        if B12 is None:
            return None
        if B14 is None:
            B14 = 0
        return B12 - B14
    
    elif cell_addr == "B18":
        B15 = get_cell_value("B15", values)
        if B15 is None:
            return None
        return B15
    
    elif cell_addr == "B29":
        B25 = get_cell_value("B25", values) or 0
        B26 = get_cell_value("B26", values) or 0
        B27 = get_cell_value("B27", values) or 0
        B28 = get_cell_value("B28", values) or 0
        if B25 == 0 and B26 == 0 and B27 == 0 and B28 == 0:
            return None
        return B25 + B26 + B27 + B28
    
    else:
        # Unknown formula cell
        return None


# Define dependencies manually
R2B_DEPENDENCIES = {
    "B5": {"D5", "E5"},
    "C5": {"D5"},
    "D5": {"E5"},
    
    "B6": {"D6", "E6", "B10"},
    "C6": {"D6"},
    "D6": {"E6"},
    
    "B7": {"D7", "E7", "B10"},
    "C7": {"D7"},
    "D7": {"E7"},
    
    "B8": {"D8", "E8", "B10"},
    "C8": {"D8"},
    "D8": {"E8"},
    
    "B10": {"B12"},
    "B11": {"B12"},
    "B12": {"B13", "B15"},
    "B13": {"B14"},
    "B14": {"B15"},
    "B15": {"B18"},
    
    "B25": {"B29"},
    "B26": {"B29"},
    "B27": {"B29"},
    "B28": {"B29"},
}


def get_affected_cells(updated_cell: str) -> List[str]:
    """Get cells affected by an update, in proper calculation order."""
    affected = []
    visited = set()
    
    def dfs(cell):
        if cell in visited:
            return
        visited.add(cell)
        
        dependents = R2B_DEPENDENCIES.get(cell, set())
        for dep in dependents:
            if dep not in visited:
                affected.append(dep)
                dfs(dep)
    
    dfs(updated_cell)
    return affected


def auto_calculate_on_update(
    property_id: str,
    template_key: str,
    updated_cell: str,
    new_value: Any,
    structure: Dict,
    current_values: Dict[str, Any]
) -> Dict[str, Any]:
    """Auto-calculate dependent formulas."""
    logger.info(f"[auto_calculate_v3] Calculating for {updated_cell} = {new_value}")
    
    # Update working values
    working_values = current_values.copy()
    working_values[updated_cell] = new_value
    
    # Get affected cells
    affected = get_affected_cells(updated_cell)
    logger.info(f"[auto_calculate_v3] Affected cells: {affected}")
    
    calculated = {}
    
    # Calculate in order (multiple passes for cascading)
    for _ in range(5):  # Max 5 passes
        changes = False
        for cell_addr in affected:
            result = evaluate_r2b_formula(cell_addr, working_values)
            if result is not None:
                result = round(result, 2)
                if working_values.get(cell_addr) != result:
                    working_values[cell_addr] = result
                    calculated[cell_addr] = result
                    changes = True
                    logger.info(f"[auto_calculate_v3] ✅ {cell_addr} = {result}")
        
        if not changes:
            break
    
    logger.info(f"[auto_calculate_v3] ✅ Calculated {len(calculated)} cells")
    return calculated


def recalculate_all_formulas(
    property_id: str,
    template_key: str,
    structure: Dict,
    current_values: Dict[str, Any]
) -> Dict[str, Any]:
    """Recalculate ALL R2B formulas."""
    logger.info(f"[recalculate_all_v3] Full recalculation")
    
    # All formula cells in calculation order
    formula_cells = [
        "D5", "D6", "D7", "D8",
        "E5", "E6", "E7", "E8",
        "B10", "B12", "B13", "B14", "B15", "B18",
        "B29"
    ]
    
    calculated = {}
    working_values = current_values.copy()
    
    # Multiple passes
    for _ in range(5):
        changes = False
        for cell_addr in formula_cells:
            result = evaluate_r2b_formula(cell_addr, working_values)
            if result is not None:
                result = round(result, 2)
                if working_values.get(cell_addr) != result:
                    working_values[cell_addr] = result
                    calculated[cell_addr] = result
                    changes = True
        
        if not changes:
            break
    
    logger.info(f"[recalculate_all_v3] ✅ Calculated {len(calculated)} cells")
    return calculated

