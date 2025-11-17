"""
Formula Calculator for Numbers Table Framework

This module handles automatic calculation of Excel-like formulas in the Numbers Table.
When a user updates a cell, this calculator evaluates all dependent formulas in cascade.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)


def parse_cell_references(formula: str) -> Set[str]:
    """Extract all cell references from a formula.
    
    Args:
        formula: Excel formula string (e.g., "=B6*C6/100")
    
    Returns:
        Set of cell addresses referenced in the formula (e.g., {"B6", "C6"})
    """
    if not formula or not formula.startswith("="):
        return set()
    
    # Match Excel cell references (A1, AB123, etc.)
    pattern = r'\b([A-Z]+\d+)\b'
    matches = re.findall(pattern, formula, re.IGNORECASE)
    return set(m.upper() for m in matches)


def evaluate_formula(formula: str, cell_values: Dict[str, Any]) -> Optional[float]:
    """Evaluate an Excel formula using provided cell values.
    
    Args:
        formula: Excel formula string (e.g., "=B6*C6/100")
        cell_values: Dict mapping cell addresses to their values (e.g., {"B6": 1000, "C6": 21})
    
    Returns:
        Calculated result as float, or None if formula cannot be evaluated
    """
    if not formula or not formula.startswith("="):
        return None
    
    try:
        # Remove leading "="
        expression = formula[1:].strip()
        
        # Replace cell references with their values
        for cell_addr, value in cell_values.items():
            if value is not None:
                # Convert value to float for calculation
                try:
                    # CRITICAL: Extract 'value' field if value is a dict (from DB)
                    if isinstance(value, dict):
                        actual_value = value.get("value", "")
                    else:
                        actual_value = value
                    
                    # Skip if empty or non-numeric text
                    if not actual_value or actual_value == "":
                        continue
                    
                    # Try to convert to float
                    float_val = float(actual_value) if not isinstance(actual_value, (int, float)) else actual_value
                    
                    # Replace cell reference with value (case-insensitive)
                    expression = re.sub(
                        rf'\b{re.escape(cell_addr)}\b',
                        str(float_val),
                        expression,
                        flags=re.IGNORECASE
                    )
                except (ValueError, TypeError) as e:
                    # Only warn for actual calculation errors, not for text cells like "R2B"
                    if cell_addr in expression:
                        logger.debug(f"Skipping non-numeric cell {cell_addr}: {value}")
                    continue
        
        # Check if all cell references have been replaced
        remaining_refs = re.findall(r'\b([A-Z]+\d+)\b', expression, re.IGNORECASE)
        if remaining_refs:
            logger.debug(f"Formula has unresolved cell references: {remaining_refs}")
            return None
        
        # Handle Excel functions (IF, SUM, etc.)
        # For now, support basic IF function
        if "IF(" in expression.upper():
            expression = handle_if_function(expression)
        
        # Evaluate the expression
        # Security: only allow safe operations
        allowed_chars = set("0123456789.+-*/() ")
        if not all(c in allowed_chars for c in expression.replace("IF", "").replace("if", "")):
            logger.warning(f"Formula contains unsafe characters: {expression}")
            return None
        
        result = eval(expression, {"__builtins__": {}}, {})
        return float(result) if result is not None else None
        
    except Exception as e:
        logger.error(f"Error evaluating formula '{formula}': {e}")
        return None


def handle_if_function(expression: str) -> str:
    """Convert Excel IF function to Python conditional.
    
    Args:
        expression: Expression containing IF function (e.g., "IF(C8>0, B8*C8/100, 0)")
    
    Returns:
        Python-compatible conditional expression (e.g., "(B8*C8/100) if (C8>0) else (0)")
    """
    # Simple IF pattern: IF(condition, value_if_true, value_if_false)
    pattern = r'IF\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)'
    
    def replace_if(match):
        condition = match.group(1).strip()
        value_true = match.group(2).strip()
        value_false = match.group(3).strip()
        return f"(({value_true}) if ({condition}) else ({value_false}))"
    
    result = re.sub(pattern, replace_if, expression, flags=re.IGNORECASE)
    return result


def build_dependency_graph(structure: Dict) -> Dict[str, Set[str]]:
    """Build a dependency graph showing which cells depend on which others.
    
    Args:
        structure: Excel structure with cells and formulas
    
    Returns:
        Dict mapping cell address to set of cells it depends on
        Example: {"D5": {"B5", "C5"}, "E5": {"B5", "D5"}}
    """
    dependencies = {}
    
    cells_with_formulas = [c for c in structure.get("cells", []) if c.get("formula")]
    logger.info(f"[build_dependency_graph] Found {len(cells_with_formulas)} cells with formulas")
    
    for cell in cells_with_formulas:
        cell_addr = cell.get("address")
        formula = cell.get("formula")
        
        if formula and cell_addr:
            refs = parse_cell_references(formula)
            if refs:
                dependencies[cell_addr] = refs
                logger.debug(f"[build_dependency_graph] {cell_addr} depends on {refs}")
    
    logger.info(f"[build_dependency_graph] Built dependency graph with {len(dependencies)} cells")
    return dependencies


def get_affected_cells(updated_cell: str, dependencies: Dict[str, Set[str]]) -> List[str]:
    """Get all cells that need to be recalculated after updating a cell.
    
    Args:
        updated_cell: Cell address that was updated (e.g., "B5")
        dependencies: Dependency graph from build_dependency_graph
    
    Returns:
        List of cell addresses that need recalculation, in order (e.g., ["D5", "E5"])
    """
    logger.info(f"[get_affected_cells] Finding cells affected by {updated_cell}")
    logger.info(f"[get_affected_cells] Dependency graph has {len(dependencies)} cells: {list(dependencies.keys())[:10]}")
    
    affected = []
    visited = set()
    
    def dfs(cell):
        """Depth-first search to find all dependent cells."""
        if cell in visited:
            return
        visited.add(cell)
        
        # Find cells that depend on this cell
        found_dependents = []
        for dep_cell, refs in dependencies.items():
            if cell in refs and dep_cell not in visited:
                found_dependents.append(dep_cell)
                affected.append(dep_cell)
                dfs(dep_cell)
        
        if found_dependents:
            logger.info(f"[get_affected_cells] Cell {cell} affects: {found_dependents}")
        else:
            logger.debug(f"[get_affected_cells] No cells depend on {cell}")
    
    dfs(updated_cell)
    logger.info(f"[get_affected_cells] Total affected cells: {len(affected)} - {affected}")
    return affected


def recalculate_formulas(
    updated_cells: List[str],
    structure: Dict,
    current_values: Dict[str, Any]
) -> Dict[str, Any]:
    """Recalculate all formulas affected by cell updates.
    
    Args:
        updated_cells: List of cell addresses that were updated by user
        structure: Excel structure with cells and formulas
        current_values: Current cell values {cell_addr: value}
    
    Returns:
        Dict of newly calculated values {cell_addr: calculated_value}
    """
    # Build dependency graph
    dependencies = build_dependency_graph(structure)
    
    # Find all affected cells (in order)
    all_affected = set()
    for cell in updated_cells:
        affected = get_affected_cells(cell, dependencies)
        all_affected.update(affected)
    
    # Create formula map
    formula_map = {}
    for cell in structure.get("cells", []):
        if cell.get("formula"):
            formula_map[cell["address"]] = cell["formula"]
    
    # Calculate affected cells
    calculated = {}
    working_values = current_values.copy()
    
    # Multiple passes to handle cascading formulas
    max_iterations = 10
    for iteration in range(max_iterations):
        changes_made = False
        
        for cell_addr in sorted(all_affected):  # Sort for consistent order
            if cell_addr not in formula_map:
                continue
            
            formula = formula_map[cell_addr]
            
            # Try to calculate
            result = evaluate_formula(formula, working_values)
            
            if result is not None:
                # Round to 2 decimal places for currency
                result = round(result, 2)
                
                # Update if changed
                if cell_addr not in calculated or calculated[cell_addr] != result:
                    calculated[cell_addr] = result
                    working_values[cell_addr] = result
                    changes_made = True
                    logger.info(f"[recalculate_formulas] Calculated {cell_addr} = {result} (formula: {formula})")
        
        if not changes_made:
            break
    
    return calculated


def auto_calculate_on_update(
    property_id: str,
    template_key: str,
    updated_cell: str,
    new_value: Any,
    structure: Dict,
    current_values: Dict[str, Any]
) -> Dict[str, Any]:
    """Automatically calculate dependent formulas when a cell is updated.
    
    This is the main entry point for auto-calculation in the Numbers Table.
    
    Args:
        property_id: Property UUID
        template_key: Template key (e.g., "R2B")
        updated_cell: Cell address that was updated (e.g., "B5")
        new_value: New value set by user
        structure: Excel structure with cells and formulas
        current_values: Current cell values from database
    
    Returns:
        Dict of cells to update in database {cell_addr: calculated_value}
    """
    logger.info(f"[auto_calculate_on_update] Starting auto-calculation for {updated_cell} = {new_value}")
    
    # Update working values with new user input
    working_values = current_values.copy()
    working_values[updated_cell] = new_value
    
    # Recalculate all affected formulas
    calculated = recalculate_formulas([updated_cell], structure, working_values)
    
    logger.info(f"[auto_calculate_on_update] Auto-calculated {len(calculated)} cells: {list(calculated.keys())}")
    
    return calculated

