from __future__ import annotations
import logging
from typing import Dict, Any
from .supabase_client import sb

logger = logging.getLogger(__name__)

def _fetch_values(property_id: str, template_key: str) -> Dict[str, Any]:
    try:
        sb.postgrest.schema = "public"
        res = sb.rpc("get_numbers_table_values", {
            "p_property_id": property_id,
            "p_template_key": template_key
        }).execute()
        data = res.data or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def verify_numbers_update(property_id: str, template_key: str, updated_cell: str, expected_value: str, auto_calculated: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Log-only verification for numbers updates:
    - Confirms that updated_cell exists and matches expected_value (string compare).
    - For auto_calculated cells, verifies values are numeric (float convertible).
    """
    try:
        values = _fetch_values(property_id, template_key)
        v = values.get(updated_cell.upper())
        saved = (v.get("value") if isinstance(v, dict) else v)
        ok_updated = (str(saved) == str(expected_value))
        issues: list[str] = []
        if not ok_updated:
            issues.append(f"{updated_cell} mismatch (db='{saved}' vs expected='{expected_value}')")
        # check numeric for auto_calculated
        if auto_calculated:
            for cell, val in auto_calculated.items():
                try:
                    float(str(val).replace(",", "."))
                except Exception:
                    issues.append(f"{cell} not numeric: '{val}'")
        status = {"ok": len(issues) == 0, "issues": issues}
        if status["ok"]:
            logger.info(f"[verify] numbers update ok: {updated_cell} and {len(auto_calculated or {})} calc cells")
        else:
            logger.warning(f"[verify] issues: {issues}")
        return status
    except Exception as e:
        logger.error(f"[verify] error: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}

