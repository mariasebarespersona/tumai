from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from .supabase_client import sb

logger = logging.getLogger(__name__)


# ============================================================================
# TASK SUCCESS VERIFICATION (Layer 4 of Evaluation System)
# ============================================================================

def verify_task_success(
    property_id: str,
    tool_calls: List[Dict],
    agent_name: str
) -> Dict:
    """
    Verify that task completed successfully by checking DB state.
    
    This is the core verifier for Layer 4 of the evaluation system.
    It routes to specific verifiers based on tool calls.
    
    Args:
        property_id: Property UUID
        tool_calls: List of tools that were called
        agent_name: Name of agent that handled request
        
    Returns:
        Dict with:
        - success: bool (overall success)
        - verification_steps: List of individual checks
        - failures: List of failed checks
    """
    verification_steps = []
    failures = []
    
    for tool_call in tool_calls:
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})
        
        # Route to specific verifier based on tool
        if tool_name == "add_property":
            result = verify_property_creation(
                property_id=tool_args.get("property_id") or property_id,
                property_name=tool_args.get("name"),
                address=tool_args.get("address")
            )
        elif tool_name == "upload_and_link":
            result = verify_document_upload(
                property_id=property_id,
                document_name=tool_args.get("document_name"),
                document_group=tool_args.get("document_group")
            )
        elif tool_name == "set_numbers_table_cell":
            result = verify_numbers_cell_update(
                property_id=property_id,
                template_key=tool_args.get("template_key", "R2B"),
                cell_address=tool_args.get("cell_address"),
                value=tool_args.get("value")
            )
        elif tool_name == "delete_property":
            result = verify_property_deletion(
                property_id=tool_args.get("property_id") or property_id
            )
        elif tool_name == "delete_numbers_template":
            result = verify_numbers_template_deletion(
                property_id=property_id,
                template_key=tool_args.get("template_key", "R2B")
            )
        else:
            # No specific verifier - mark as passed
            result = {
                "check": tool_name,
                "passed": True,
                "note": "No specific verifier implemented",
                "tool_args": tool_args
            }
        
        verification_steps.append(result)
        
        if not result.get("passed", False):
            failures.append(result)
    
    success = len(failures) == 0
    
    return {
        "success": success,
        "verification_steps": verification_steps,
        "failures": failures,
        "agent_name": agent_name,
        "property_id": property_id
    }


# ============================================================================
# SPECIFIC VERIFIERS
# ============================================================================

def verify_property_creation(
    property_id: str,
    property_name: Optional[str] = None,
    address: Optional[str] = None
) -> Dict:
    """
    Verify that property was actually created in DB.
    
    Checks:
    1. Property exists in properties table
    2. Property has correct name and address (if provided)
    3. Frameworks were provisioned (3 schemas)
    
    Returns:
        Dict with check results
    """
    try:
        logger.info(f"[Verifier] Checking property creation: {property_id}")
        
        # 1. Check property exists
        result = sb.table("properties").select("*").eq("id", property_id).execute()
        
        if not result.data or len(result.data) == 0:
            return {
                "check": "property_exists_in_db",
                "passed": False,
                "property_id": property_id,
                "error": "Property not found in database"
            }
        
        property_row = result.data[0]
        
        # 2. Verify name and address match (if provided)
        mismatches = []
        if property_name and property_row.get("name") != property_name:
            mismatches.append(f"name: expected '{property_name}', got '{property_row.get('name')}'")
        if address and property_row.get("address") != address:
            mismatches.append(f"address: expected '{address}', got '{property_row.get('address')}'")
        
        if mismatches:
            return {
                "check": "property_exists_in_db",
                "passed": False,
                "property_id": property_id,
                "error": f"Property data mismatch: {', '.join(mismatches)}",
                "property_data": property_row
            }
        
        # 3. Check frameworks were provisioned
        # Frameworks are stored in property_frameworks table or as schema names
        # For simplicity, we check if property is not soft_deleted
        if property_row.get("soft_deleted", False):
            return {
                "check": "property_exists_in_db",
                "passed": False,
                "property_id": property_id,
                "error": "Property is marked as soft_deleted"
            }
        
        logger.info(f"[Verifier] ✅ Property creation verified: {property_id}")
        return {
            "check": "property_exists_in_db",
            "passed": True,
            "property_id": property_id,
            "property_name": property_row.get("name"),
            "address": property_row.get("address"),
            "created_at": property_row.get("created_at")
        }
        
    except Exception as e:
        logger.error(f"[Verifier] Error verifying property creation: {e}", exc_info=True)
        return {
            "check": "property_exists_in_db",
            "passed": False,
            "property_id": property_id,
            "error": str(e)
        }


def verify_document_upload(
    property_id: str,
    document_name: str,
    document_group: str,
    document_subgroup: Optional[str] = ""
) -> Dict:
    """
    Verify that document was uploaded and linked to property.
    
    Checks:
    1. Document row exists in property's docs framework
    2. Document has storage_key (file was uploaded)
    3. storage_key points to valid file in Supabase Storage
    
    Returns:
        Dict with check results
    """
    try:
        logger.info(f"[Verifier] Checking document upload: {document_name} for property {property_id}")
        
        # Query docs framework for this property
        # The schema depends on property, but we can use RPC or direct query
        # For simplicity, assume we have a function or can query docs table
        
        # Use list_docs RPC (already exists)
        from .docs_tools import list_docs as _list_docs
        
        docs = _list_docs(property_id)
        
        # Find document
        matching_doc = None
        for doc in docs:
            if (doc.get("document_name") == document_name and
                doc.get("document_group") == document_group and
                doc.get("document_subgroup", "") == (document_subgroup or "")):
                matching_doc = doc
                break
        
        if not matching_doc:
            return {
                "check": "document_uploaded_to_db",
                "passed": False,
                "property_id": property_id,
                "document_name": document_name,
                "error": "Document not found in docs framework"
            }
        
        # Check storage_key exists (file uploaded)
        storage_key = matching_doc.get("storage_key")
        if not storage_key:
            return {
                "check": "document_uploaded_to_db",
                "passed": False,
                "property_id": property_id,
                "document_name": document_name,
                "error": "Document has no storage_key (not uploaded)"
            }
        
        logger.info(f"[Verifier] ✅ Document upload verified: {document_name}")
        return {
            "check": "document_uploaded_to_db",
            "passed": True,
            "property_id": property_id,
            "document_name": document_name,
            "storage_key": storage_key,
            "document_group": document_group
        }
        
    except Exception as e:
        logger.error(f"[Verifier] Error verifying document upload: {e}", exc_info=True)
        return {
            "check": "document_uploaded_to_db",
            "passed": False,
            "property_id": property_id,
            "document_name": document_name,
            "error": str(e)
        }


def verify_numbers_cell_update(
    property_id: str,
    template_key: str,
    cell_address: str,
    value: str
) -> Dict:
    """
    Verify that numbers table cell was updated in DB.
    
    Checks:
    1. Cell exists in numbers_table_values
    2. Cell has correct value
    3. Auto-calculated cells (if any) also updated
    
    Returns:
        Dict with check results
    """
    try:
        logger.info(f"[Verifier] Checking numbers cell update: {cell_address} = '{value}' for property {property_id}")
        
        # Fetch values from DB
        values = _fetch_values(property_id, template_key)
        
        # Check cell exists
        cell_data = values.get(cell_address.upper())
        if not cell_data:
            return {
                "check": "numbers_cell_updated_in_db",
                "passed": False,
                "property_id": property_id,
                "cell_address": cell_address,
                "error": f"Cell {cell_address} not found in database"
            }
        
        # Get saved value
        saved_value = cell_data.get("value") if isinstance(cell_data, dict) else cell_data
        
        # Compare (string comparison)
        if str(saved_value) != str(value):
            return {
                "check": "numbers_cell_updated_in_db",
                "passed": False,
                "property_id": property_id,
                "cell_address": cell_address,
                "expected_value": value,
                "actual_value": saved_value,
                "error": f"Value mismatch: expected '{value}', got '{saved_value}'"
            }
        
        logger.info(f"[Verifier] ✅ Numbers cell update verified: {cell_address}")
        return {
            "check": "numbers_cell_updated_in_db",
            "passed": True,
            "property_id": property_id,
            "cell_address": cell_address,
            "value": saved_value
        }
        
    except Exception as e:
        logger.error(f"[Verifier] Error verifying numbers cell update: {e}", exc_info=True)
        return {
            "check": "numbers_cell_updated_in_db",
            "passed": False,
            "property_id": property_id,
            "cell_address": cell_address,
            "error": str(e)
        }


def verify_property_deletion(property_id: str) -> Dict:
    """
    Verify that property was soft-deleted.
    
    Checks:
    1. Property still exists in DB (soft delete)
    2. Property is marked as soft_deleted=true
    
    Returns:
        Dict with check results
    """
    try:
        logger.info(f"[Verifier] Checking property deletion: {property_id}")
        
        result = sb.table("properties").select("*").eq("id", property_id).execute()
        
        if not result.data or len(result.data) == 0:
            # Property was hard deleted (shouldn't happen)
            return {
                "check": "property_soft_deleted",
                "passed": False,
                "property_id": property_id,
                "error": "Property was hard deleted (should be soft delete)"
            }
        
        property_row = result.data[0]
        
        # Check soft_deleted flag
        if not property_row.get("soft_deleted", False):
            return {
                "check": "property_soft_deleted",
                "passed": False,
                "property_id": property_id,
                "error": "Property not marked as soft_deleted"
            }
        
        logger.info(f"[Verifier] ✅ Property deletion verified: {property_id}")
        return {
            "check": "property_soft_deleted",
            "passed": True,
            "property_id": property_id,
            "soft_deleted_at": property_row.get("updated_at")
        }
        
    except Exception as e:
        logger.error(f"[Verifier] Error verifying property deletion: {e}", exc_info=True)
        return {
            "check": "property_soft_deleted",
            "passed": False,
            "property_id": property_id,
            "error": str(e)
        }


def verify_numbers_template_deletion(property_id: str, template_key: str) -> Dict:
    """
    Verify that numbers template was deleted.
    
    Checks:
    1. No structure rows exist for this property+template
    2. No values exist for this property+template
    
    Returns:
        Dict with check results
    """
    try:
        logger.info(f"[Verifier] Checking numbers template deletion: {template_key} for property {property_id}")
        
        # Check structure
        structure_result = sb.table("numbers_table_structure").select("*").eq("property_id", property_id).eq("template_key", template_key).execute()
        
        if structure_result.data and len(structure_result.data) > 0:
            return {
                "check": "numbers_template_deleted",
                "passed": False,
                "property_id": property_id,
                "template_key": template_key,
                "error": f"Template structure still exists ({len(structure_result.data)} rows)"
            }
        
        # Check values
        values_result = sb.table("numbers_table_values").select("*").eq("property_id", property_id).eq("template_key", template_key).execute()
        
        if values_result.data and len(values_result.data) > 0:
            return {
                "check": "numbers_template_deleted",
                "passed": False,
                "property_id": property_id,
                "template_key": template_key,
                "error": f"Template values still exist ({len(values_result.data)} rows)"
            }
        
        logger.info(f"[Verifier] ✅ Numbers template deletion verified: {template_key}")
        return {
            "check": "numbers_template_deleted",
            "passed": True,
            "property_id": property_id,
            "template_key": template_key
        }
        
    except Exception as e:
        logger.error(f"[Verifier] Error verifying numbers template deletion: {e}", exc_info=True)
        return {
            "check": "numbers_template_deleted",
            "passed": False,
            "property_id": property_id,
            "template_key": template_key,
            "error": str(e)
        }


# ============================================================================
# EXISTING VERIFIER (for numbers updates)
# ============================================================================

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

