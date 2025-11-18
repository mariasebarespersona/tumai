"""
Formula Calculator V2 - Uses formulas library for proper Excel formula evaluation.

This version replaces the custom parser with the 'formulas' library which properly
handles all Excel functions including IF(), OR(), AND(), etc.
"""

import re
import logging
from typing import Dict, List, Set, Any, Optional

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


def evaluate_formula_v2(formula: str, cell_values: Dict[str, Any]) -> Optional[float]:
    """Evaluate an Excel formula using the formulas library.
    
    This properly handles all Excel functions including IF(), OR(), AND(), etc.
    
    Args:
        formula: Excel formula (e.g., "=IF(OR(B5="",C5=""),"",B5*C5/100)")
        cell_values: Dict mapping cell addresses to their values
    
    Returns:
        Calculated result or None if evaluation fails
    """
    import formulas
    
    try:
        # Ensure formula starts with =
        if not formula.startswith('='):
            formula = '=' + formula
        
        logger.debug(f"[evaluate_formula_v2] Evaluating: {formula}")
        
        # Prepare cell values
        values_dict = {}
        for cell_addr, value in cell_values.items():
            # Extract actual value if it's a dict
            actual_value = value
            if isinstance(value, dict):
                actual_value = value.get("value", "")
            
            # Convert to appropriate type
            cell_key = cell_addr.upper()
            if actual_value == "" or actual_value is None:
                values_dict[cell_key] = ""  # Empty cells
            elif isinstance(actual_value, (int, float)):
                values_dict[cell_key] = actual_value
            else:
                try:
                    values_dict[cell_key] = float(actual_value)
                except (ValueError, TypeError):
                    values_dict[cell_key] = str(actual_value)
        
        logger.debug(f"[evaluate_formula_v2] Values: {values_dict}")
        
        # Parse and evaluate using formulas library
        parser = formulas.Parser()
        ast_result = parser.ast(formula)
        
        if ast_result[1] is None:
            logger.warning(f"[evaluate_formula_v2] Failed to parse formula: {formula}")
            return None
        
        parsed = ast_result[1]
        
        # Compile the formula
        func = parsed.compile()
        
        # Execute with our cell values
        result = func(values_dict)
        
        logger.info(f"[evaluate_formula_v2] ✅ {formula[:60]} = {result}")
        
        # Handle result
        if result == "" or result is None:
            return None
        if isinstance(result, (int, float)):
            return float(result)
        try:
            return float(result)
        except (ValueError, TypeError):
            logger.debug(f"[evaluate_formula_v2] Non-numeric result: {result}")
            return None
    
    except Exception as e:
        logger.warning(f"[evaluate_formula_v2] Error: {e}")
        return None


def build_dependency_graph(structure: Dict) -> Dict[str, Set[str]]:
    """Build a REVERSE dependency graph: input_cell -> cells that depend on it.
    
    Returns:
        Dict mapping input cell to set of formula cells that use it
        Example: {"B5": {"D5", "E5"}} means D5 and E5 depend on B5
    """
    reverse_deps = {}
    
    cells_with_formulas = [c for c in structure.get("cells", []) if c.get("formula")]
    logger.info(f"[build_dependency_graph] Found {len(cells_with_formulas)} cells with formulas")
    
    for cell in cells_with_formulas:
        cell_addr = cell.get("address")
        formula = cell.get("formula")
        
        if formula and cell_addr:
            # Get all input cells that this formula uses
            input_refs = parse_cell_references(formula)
            logger.debug(f"[build_dependency_graph] {cell_addr} = {formula[:50]} uses {input_refs}")
            
            # For each input, register this formula cell as a dependent
            for input_cell in input_refs:
                if input_cell not in reverse_deps:
                    reverse_deps[input_cell] = set()
                reverse_deps[input_cell].add(cell_addr)
    
    logger.info(f"[build_dependency_graph] ✅ Built reverse dependency graph with {len(reverse_deps)} input cells")
    return reverse_deps


def get_affected_cells(updated_cell: str, reverse_deps: Dict[str, Set[str]]) -> List[str]:
    """Get all cells that need to be recalculated after updating a cell.
    
    Args:
        updated_cell: Cell address that was updated (e.g., "B5")
        reverse_deps: Reverse dependency graph from build_dependency_graph
    
    Returns:
        List of cell addresses that need recalculation, in cascading order
    """
    logger.info(f"[get_affected_cells] Finding cells affected by {updated_cell}")
    
    affected = []
    visited = set()
    
    def dfs(cell):
        """Depth-first search to find all dependent cells."""
        if cell in visited:
            return
        visited.add(cell)
        
        # Get direct dependents
        direct_dependents = reverse_deps.get(cell, set())
        
        for dependent in direct_dependents:
            if dependent not in visited:
                affected.append(dependent)
                # Recursively find dependents of this dependent (cascading)
                dfs(dependent)
    
    dfs(updated_cell)
    logger.info(f"[get_affected_cells] ✅ Total affected cells: {len(affected)} - {affected}")
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
    logger.info(f"[recalculate_formulas] Updated cells: {updated_cells}")
    
    # Build dependency graph
    reverse_deps = build_dependency_graph(structure)
    logger.info(f"[recalculate_formulas] Dependencies built: {len(reverse_deps)} input cells")
    
    # Find all affected cells (in cascading order)
    all_affected = set()
    for cell in updated_cells:
        logger.info(f"[recalculate_formulas] Getting affected cells for {cell}")
        affected = get_affected_cells(cell, reverse_deps)
        logger.info(f"[recalculate_formulas] Affected by {cell}: {affected}")
        all_affected.update(affected)
    
    logger.info(f"[recalculate_formulas] Total affected cells: {all_affected}")
    
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
            
            # Try to calculate using V2 evaluator
            result = evaluate_formula_v2(formula, working_values)
            
            if result is not None:
                # Round to 2 decimal places for currency
                result = round(result, 2)
                
                # Only update if changed
                old_value = working_values.get(cell_addr)
                if isinstance(old_value, dict):
                    old_value = old_value.get("value")
                
                if old_value != result:
                    working_values[cell_addr] = result
                    calculated[cell_addr] = result
                    changes_made = True
                    logger.debug(f"[recalculate_formulas] Calculated {cell_addr} = {result}")
        
        if not changes_made:
            break
    
    logger.info(f"[recalculate_formulas] ✅ Calculated {len(calculated)} cells after {iteration + 1} iterations")
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


def recalculate_all_formulas(
    property_id: str,
    template_key: str,
    structure: Dict,
    current_values: Dict[str, Any]
) -> Dict[str, Any]:
    """Recalculate ALL formulas in the template.
    
    Used when loading a template or after significant changes.
    
    Args:
        property_id: Property UUID
        template_key: Template key
        structure: Excel structure
        current_values: Current cell values
    
    Returns:
        Dict of all calculated values {cell_addr: calculated_value}
    """
    logger.info(f"[recalculate_all_formulas] Starting full recalculation")
    
    # Get all formula cells
    formula_cells = [c for c in structure.get("cells", []) if c.get("formula")]
    logger.info(f"[recalculate_all_formulas] Found {len(formula_cells)} formula cells")
    
    calculated = {}
    working_values = current_values.copy()
    
    # Multiple passes to handle dependencies
    max_iterations = 10
    for iteration in range(max_iterations):
        changes_made = False
        
        for cell in formula_cells:
            cell_addr = cell.get("address")
            formula = cell.get("formula")
            
            if not formula:
                continue
            
            # Try to calculate
            result = evaluate_formula_v2(formula, working_values)
            
            if result is not None:
                result = round(result, 2)
                
                # Only update if changed
                old_value = working_values.get(cell_addr)
                if isinstance(old_value, dict):
                    old_value = old_value.get("value")
                
                if old_value != result:
                    working_values[cell_addr] = result
                    calculated[cell_addr] = result
                    changes_made = True
                    logger.debug(f"[recalculate_all_formulas] Calculated {cell_addr} = {result}")
        
        if not changes_made:
            break
    
    logger.info(f"[recalculate_all_formulas] ✅ Calculated {len(calculated)} cells after {iteration + 1} iterations")
    return calculated

