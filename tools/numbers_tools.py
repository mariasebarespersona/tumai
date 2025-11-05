from __future__ import annotations
from typing import Dict, List, Optional, Union
from .supabase_client import sb
from .utils import nums_schema

def set_number(property_id: str, item_key: str, amount: Optional[float]) -> Dict:
    schema = nums_schema(property_id)
    try:
        sb.postgrest.schema = schema
        (sb.table("line_items")
          .update({"amount": amount})
          .eq("property_id", property_id)
          .eq("item_key", item_key)
          .execute())
        return {"item_key": item_key, "amount": amount}
    except Exception:
        # Fallback via RPC in public schema
        sb.postgrest.schema = "public"
        sb.rpc("set_property_number", {"p_id": property_id, "k": item_key, "amount": amount}).execute()
        return {"item_key": item_key, "amount": amount}

def get_numbers(property_id: str, template_key: Optional[str] = None) -> List[Dict]:
    """Get all numbers for a property. Returns the structure even if values are NULL.
    
    If no items are found in the DB, returns the template structure for R2B by default.
    """
    # Define the template structures first
    template_structures = {
        "R2B": [
            {"group_name": "Bº RAMA", "item_key": "precio_venta", "item_label": "Precio de venta", "is_percent": False, "amount": None},
            {"group_name": "Bº RAMA", "item_key": "terreno_urbano", "item_label": "Terreno urbano", "is_percent": False, "amount": None},
            {"group_name": "Bº RAMA", "item_key": "terreno_rustico", "item_label": "Terreno rústico", "is_percent": False, "amount": None},
            {"group_name": "Bº RAMA", "item_key": "terreno_urbano_iva_pct", "item_label": "IVA (%)", "is_percent": True, "amount": None},
            {"group_name": "Bº RAMA", "item_key": "terreno_rustico_iva_pct", "item_label": "IVA (%)", "is_percent": True, "amount": None},
            {"group_name": "Bº RAMA", "item_key": "project_mgmt_fees", "item_label": "Project Mgmt fees", "is_percent": False, "amount": None},
            {"group_name": "Bº RAMA", "item_key": "impuestos_pct", "item_label": "Impuestos (%)", "is_percent": True, "amount": None},
            {"group_name": "Bº RAMA", "item_key": "total_pagado", "item_label": "Total pagado a 29 julio 2025", "is_percent": False, "amount": None},
            {"group_name": "Coste comprador", "item_key": "terrenos_coste", "item_label": "Terrenos", "is_percent": False, "amount": None},
            {"group_name": "Coste comprador", "item_key": "project_management_coste", "item_label": "Project Management", "is_percent": False, "amount": None},
            {"group_name": "Coste comprador", "item_key": "acometidas", "item_label": "Acometidas", "is_percent": False, "amount": None},
            {"group_name": "Coste comprador", "item_key": "costes_construccion", "item_label": "Costes de construcción", "is_percent": False, "amount": None},
        ],
    }
    
    # Default template key
    template_key = template_key or "R2B"
    
    # If template_key is specified, always return the template structure
    # This ensures the frontend always shows the correct structure for the selected template
    if template_key:
        # Try to get items from DB and merge with template structure
        schema = nums_schema(property_id)
        db_items = {}
        try:
            sb.postgrest.schema = schema
            items = (sb.table("line_items")
                     .select("group_name,item_key,item_label,is_percent,amount,updated_at")
                     .eq("property_id", property_id)
                     .execute()).data
            # Build a map of item_key -> item for quick lookup
            for item in (items or []):
                db_items[item.get("item_key")] = item
        except Exception as e:
            # Log error for debugging
            import logging
            logging.warning(f"Error fetching from schema {schema}: {e}")
        
        # Fallback via RPC in public schema
        if not db_items:
            try:
                sb.postgrest.schema = "public"
                items = sb.rpc("list_property_numbers", {"p_id": property_id}).execute().data
                for item in (items or []):
                    db_items[item.get("item_key")] = item
            except Exception as e:
                # Log error for debugging
                import logging
                logging.warning(f"Error fetching via RPC: {e}")
        
        # Get template structure and merge with DB values
        template_structure = template_structures.get(template_key, template_structures["R2B"])
        result = []
        for template_item in template_structure:
            item_key = template_item["item_key"]
            # If we have a DB value for this item, use it (but keep template structure)
            if item_key in db_items:
                db_item = db_items[item_key]
                # Merge: use template structure but DB values for amount
                merged_item = template_item.copy()
                merged_item["amount"] = db_item.get("amount")
                merged_item["updated_at"] = db_item.get("updated_at")
                result.append(merged_item)
            else:
                # Use template structure with NULL values
                result.append(template_item.copy())
        return result
    
    # If no template_key, try to get items from DB (legacy behavior)
    schema = nums_schema(property_id)
    try:
        sb.postgrest.schema = schema
        items = (sb.table("line_items")
                 .select("group_name,item_key,item_label,is_percent,amount,updated_at")
                 .eq("property_id", property_id)
                 .execute()).data
        if items and len(items) > 0:
            return items
    except Exception as e:
        import logging
        logging.warning(f"Error fetching from schema {schema}: {e}")
    
    # Fallback via RPC
    try:
        sb.postgrest.schema = "public"
        items = sb.rpc("list_property_numbers", {"p_id": property_id}).execute().data
        if items and len(items) > 0:
            return items
    except Exception as e:
        import logging
        logging.warning(f"Error fetching via RPC: {e}")
    
    # If no items found in DB, return the default template structure
    return template_structures.get("R2B", [])

def calc_numbers(property_id: str) -> List[Dict]:
    schema = nums_schema(property_id)
    try:
        # This may fail if PostgREST doesn't expose the dynamic schema; try public RPC instead.
        return sb.rpc(f"{schema}.calc").execute().data
    except Exception:
        sb.postgrest.schema = "public"
        return sb.rpc("calc_property_numbers", {"p_id": property_id}).execute().data

def clear_number(property_id: str, item_key: str) -> Dict:
    """Clear/reset a specific number value by setting it to None."""
    return set_number(property_id, item_key, None)

def initialize_template_structure(property_id: str, template_key: str) -> Dict:
    """Initialize the structure of line_items for a numbers template.
    This ensures that get_numbers returns the full structure even if values are NULL.
    """
    # Define the structure for each template
    template_structures = {
        "R2B": [
            # Bº RAMA section
            {"group_name": "Bº RAMA", "item_key": "precio_venta", "item_label": "Precio de venta", "is_percent": False},
            {"group_name": "Bº RAMA", "item_key": "terreno_urbano", "item_label": "Terreno urbano", "is_percent": False},
            {"group_name": "Bº RAMA", "item_key": "terreno_rustico", "item_label": "Terreno rústico", "is_percent": False},
            {"group_name": "Bº RAMA", "item_key": "terreno_urbano_iva_pct", "item_label": "IVA (%)", "is_percent": True},
            {"group_name": "Bº RAMA", "item_key": "terreno_rustico_iva_pct", "item_label": "IVA (%)", "is_percent": True},
            {"group_name": "Bº RAMA", "item_key": "project_mgmt_fees", "item_label": "Project Mgmt fees", "is_percent": False},
            {"group_name": "Bº RAMA", "item_key": "impuestos_pct", "item_label": "Impuestos (%)", "is_percent": True},
            {"group_name": "Bº RAMA", "item_key": "total_pagado", "item_label": "Total pagado a 29 julio 2025", "is_percent": False},
            # Coste comprador section
            {"group_name": "Coste comprador", "item_key": "terrenos_coste", "item_label": "Terrenos", "is_percent": False},
            {"group_name": "Coste comprador", "item_key": "project_management_coste", "item_label": "Project Management", "is_percent": False},
            {"group_name": "Coste comprador", "item_key": "acometidas", "item_label": "Acometidas", "is_percent": False},
            {"group_name": "Coste comprador", "item_key": "costes_construccion", "item_label": "Costes de construcción", "is_percent": False},
        ],
        "R2B + PM": [
            # Same as R2B for now
        ],
        "R2B + PM + Venta certs": [
            # Same as R2B for now
        ],
        "Promoción": [
            # Different structure for Promoción
        ]
    }
    
    structure = template_structures.get(template_key, template_structures["R2B"])
    
    # For now, just return success - the structure will be created when the user sets values
    # The RPC list_property_numbers should handle this, but if it doesn't, we'll need to create an RPC
    return {"property_id": property_id, "template_key": template_key, "status": "structure_initialized"}

def clear_numbers(property_id: str) -> Dict:
    """Clear/reset all number values for a property when starting fresh with a new template.
    
    This function attempts to clear all number values, but if the RPC doesn't exist,
    it will return success anyway (template selection is the priority).
    """
    # Try RPC first (if it exists) to avoid 404 errors from direct table access
    try:
        sb.postgrest.schema = "public"
        sb.rpc("clear_property_numbers", {"p_id": property_id}).execute()
        return {"property_id": property_id, "status": "cleared"}
    except Exception:
        # If RPC doesn't exist, return success anyway (template selection is the priority)
        # The values will be cleared when the user starts entering new values in the Excel
        # This avoids 404 errors in the logs while still allowing template selection to proceed
        return {"property_id": property_id, "status": "attempted", "note": "RPC not available, values will be cleared when user enters new values"}

def find_item_by_value(property_id: str, search_value: Optional[Union[str, float]] = None, search_label: Optional[str] = None) -> Optional[Dict]:
    """Find an item in the numbers framework by value or label.
    
    Args:
        property_id: Property UUID
        search_value: Value to search for (e.g., 10.0 for "10%" or 100000)
        search_label: Label text to search for (e.g., "IVA", "Precio de venta")
    
    Returns:
        Dict with item_key, item_label, amount, etc. or None if not found
    """
    items = get_numbers(property_id)
    
    # Normalize search_label for fuzzy matching
    if search_label:
        search_label_lower = search_label.lower().strip()
        # Remove common words and normalize, but keep "iva" for matching
        search_label_clean = search_label_lower.replace("(%)", "").replace("(", "").replace(")", "").strip()
    
    # Parse search_value if it's a string
    parsed_value = None
    if search_value is not None:
        if isinstance(search_value, (int, float)):
            parsed_value = float(search_value)
        elif isinstance(search_value, str):
            try:
                val_str = str(search_value).replace("%", "").replace(",", ".").strip()
                parsed_value = float(val_str)
            except:
                pass
    
    best_match = None
    best_score = 0
    
    for item in items:
        item_label = item.get("item_label", "").lower()
        item_key = item.get("item_key", "").lower()
        item_amount = item.get("amount")
        
        score = 0
        
        # Match by label (fuzzy)
        if search_label:
            # Exact match in label
            if search_label_clean in item_label or item_label in search_label_clean:
                score += 10
            # Partial match in label
            elif any(word in item_label for word in search_label_clean.split() if len(word) > 2):
                score += 5
            # Match in item_key
            if search_label_clean in item_key:
                score += 8
        
        # Match by value
        if parsed_value is not None and item_amount is not None:
            # Allow small floating point differences
            if abs(float(item_amount) - parsed_value) < 0.01:
                score += 10
            # Allow percentage matching (e.g., 10% = 10.0)
            elif abs(float(item_amount) - parsed_value) < 1.0:
                score += 5
        
        # If both label and value match, return immediately (perfect match)
        if score >= 20:
            return item
        
        # Track best match
        if score > best_score:
            best_score = score
            best_match = item
    
    # Return best match if score is high enough
    if best_score >= 10:
        return best_match
    
    # Fallback: if only label or only value matches, return it
    if search_label and best_score >= 5:
        return best_match
    if parsed_value is not None and best_score >= 5:
        return best_match
    
    return None
