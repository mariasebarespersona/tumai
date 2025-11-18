"""
Recalculate all formulas in a Numbers Table.

This module provides functionality to recalculate ALL formulas in a numbers table,
not just those affected by a single cell update.
"""

import logging
from typing import Dict, Any
from tools.supabase_client import sb
from tools.formula_calculator_v3_simple import recalculate_all_formulas as recalc_all

logger = logging.getLogger(__name__)


def save_calculated_values(property_id: str, template_key: str, calculated: Dict[str, Any], structure: Dict) -> int:
    """Save calculated values to the database.
    
    Args:
        property_id: Property UUID
        template_key: Template key
        calculated: Dict of calculated values {cell_addr: value}
        structure: Excel structure (to get cell info)
    
    Returns:
        Number of cells saved
    """
    logger.info(f"[save_calculated_values] Saving {len(calculated)} calculated values to DB")
    
    saved_count = 0
    for cell_addr, calc_value in calculated.items():
        # Find cell info for labels
        cell_info = None
        for cell in structure.get("cells", []):
            if cell.get("address") == cell_addr:
                cell_info = cell
                break
        
        try:
            # Save via RPC
            sb.postgrest.schema = "public"
            sb.rpc("set_numbers_table_cell", {
                "p_property_id": property_id,
                "p_template_key": template_key,
                "p_cell_address": cell_addr,
                "p_value": str(calc_value),
                "p_row_label": cell_info.get("row_label") if cell_info else None,
                "p_col_label": cell_info.get("col_label") if cell_info else None,
                "p_format_json": cell_info.get("format", {}) if cell_info else {}
            }).execute()
            
            saved_count += 1
            logger.debug(f"[save_calculated_values] ✅ Saved {cell_addr} = {calc_value}")
        
        except Exception as e:
            logger.error(f"[save_calculated_values] ❌ Error saving {cell_addr}: {e}")
    
    logger.info(f"[save_calculated_values] ✅ Saved {saved_count}/{len(calculated)} calculated values")
    return saved_count


def recalculate_and_save(property_id: str, template_key: str) -> Dict:
    """Recalculate all formulas and save to database.
    
    This is the main entry point for full recalculation.
    
    Args:
        property_id: Property UUID
        template_key: Template key (e.g., "R2B")
    
    Returns:
        Dict with ok status, calculated cells, and saved count
    """
    try:
        # Import here to avoid circular imports
        from tools.numbers_tools import get_numbers_table_structure, get_numbers_table_values
        
        logger.info(f"[recalculate_and_save] 🔄 Starting full recalculation for {property_id}/{template_key}")
        
        # Get structure and current values
        structure = get_numbers_table_structure(property_id, template_key)
        current_values = get_numbers_table_values(property_id, template_key)
        
        # Recalculate all formulas using V2
        calculated = recalc_all(property_id, template_key, structure, current_values)
        
        if not calculated:
            logger.info(f"[recalculate_and_save] No formulas to calculate (either no formulas or missing dependencies)")
            return {
                "ok": True,
                "calculated": {},
                "saved_count": 0,
                "message": "No hay fórmulas para calcular con los valores actuales"
            }
        
        # Save to database
        saved_count = save_calculated_values(property_id, template_key, calculated, structure)
        
        logger.info(f"[recalculate_and_save] ✅ Recalculation complete: {len(calculated)} formulas calculated, {saved_count} saved")
        
        return {
            "ok": True,
            "calculated": calculated,
            "saved_count": saved_count,
            "message": f"Se han calculado automáticamente {len(calculated)} celdas: {', '.join(list(calculated.keys())[:5])}"
        }
    
    except Exception as e:
        logger.error(f"[recalculate_and_save] ❌ Error during recalculation: {e}", exc_info=True)
        return {
            "ok": False,
            "error": str(e),
            "message": f"Error al recalcular fórmulas: {e}"
        }

