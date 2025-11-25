# tools/registry.py
from __future__ import annotations
from typing import List, Dict, Optional, Union
from pydantic import BaseModel, Field
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)

# import your pure functions
from .property_tools import add_property as _add_property, list_frameworks as _list_frameworks
from .property_tools import get_property as _get_property, find_property as _find_property, list_properties as _list_properties
from .property_tools import search_properties as _search_properties
from .property_tools import delete_property as _delete_property, delete_properties as _delete_properties
from .docs_tools import (
    propose_slot as _propose_slot,
    upload_and_link as _upload_and_link,
    list_docs as _list_docs,
    signed_url_for as _signed_url_for,
    slot_exists as _slot_exists,
    list_related_facturas as _list_related_facturas,
    seed_facturas_for as _seed_facturas_for,
    seed_mock_documents as _seed_mock_documents,
    purge_property_documents as _purge_property_documents,
    purge_all_documents as _purge_all_documents,
    set_property_strategy as _set_property_strategy, # NEW
    get_property_strategy as _get_property_strategy, # NEW
)
from .numbers_tools import (
    set_number as _set_number, 
    get_numbers as _get_numbers, 
    calc_numbers as _calc_numbers,
    clear_number as _clear_number,
    find_item_by_value as _find_item_by_value,
    set_numbers_table_cell as _set_numbers_table_cell,
    clear_numbers_table_cell as _clear_numbers_table_cell,
    delete_numbers_template as _delete_numbers_template,
)
from .numbers_agent import (
    compute_and_log as _numbers_compute_and_log,
    generate_numbers_excel as _numbers_excel,
    generate_numbers_table_excel as _numbers_table_excel,
    what_if as _numbers_what_if,
    sensitivity_grid as _numbers_sensitivity,
    break_even_precio as _numbers_break_even,
    chart_waterfall as _numbers_chart_waterfall,
    chart_cost_stack as _numbers_chart_cost_stack,
    chart_sensitivity_heatmap as _numbers_chart_sensitivity,
)
from .summary_tools import get_summary_spec as _get_summary_spec, upsert_summary_value as _upsert_summary_value, compute_summary as _compute_summary
from .summary_ppt import build_summary_ppt as _build_summary_ppt
from .email_tool import send_email as _send_email
from .voice_tool import transcribe_google_wav as _transcribe_google_wav, tts_google as _tts_google, process_voice_input as _process_voice_input, create_voice_response as _create_voice_response
from .rag_tool import summarize_document as _summarize_document, qa_document as _qa_document, qa_payment_schedule as _qa_payment_schedule
from .rag_index import index_document as _index_document, qa_with_citations as _qa_with_citations, index_all_documents as _index_all_documents
from .reminders_tools import create_reminder as _create_reminder, extract_payment_date_from_document as _extract_payment_date, list_reminders as _list_reminders, cancel_reminder as _cancel_reminder
# ---------- Set current property (LLM-controlled) ----------
class SetCurrentPropertyInput(BaseModel):
    property_id: str = Field(..., description="UUID of the property to set as current")

@tool("set_current_property")
def set_current_property_tool(property_id: str) -> Dict:
    """Fix the current working property explicitly. LLM must call this after selecting a property. Returns {property_id, property_name}."""
    row = _get_property(property_id)
    if not row:
        return {"error": "property_not_found", "property_id": property_id}
    return {"property_id": row.get("id"), "property_name": row.get("name")}

# ---------- Schemas ----------

class AddPropertyInput(BaseModel):
    name: str = Field(..., description="Property name as shown to user")
    address: str = Field(..., description="Property full address")

@tool("add_property")
def add_property_tool(name: str, address: str) -> Dict:
    """Create a new property in Supabase (triggers provisioning of 3 frameworks)."""
    return _add_property(name, address)


class ListFrameworksInput(BaseModel):
    property_id: str = Field(..., description="UUID of the property")

@tool("list_frameworks")
def list_frameworks_tool(property_id: str) -> Dict:
    """Return schema names for the property's three frameworks."""
    return _list_frameworks(property_id)


class DeletePropertyInput(BaseModel):
    property_id: str = Field(..., description="UUID of the property to delete")
    purge_docs_first: bool = Field(True, description="Whether to purge uploaded documents before deletion")

@tool("delete_property")
def delete_property_tool(property_id: str, purge_docs_first: bool = True) -> Dict:
    """Delete/remove a property (soft-delete) and optionally purge its uploaded documents. 
    Use this when user says "borra la propiedad", "elimina esta propiedad", "delete this property", etc.
    The property_id should be the currently active property unless user specifies a different one.
    Returns {"deleted": True} on success. After deletion, property_id will be automatically cleared from context."""
    return _delete_property(property_id, purge_docs_first)


class DeletePropertiesInput(BaseModel):
    property_ids: List[str] = Field(..., description="List of property UUIDs to delete")
    purge_docs_first: bool = True

@tool("delete_properties")
def delete_properties_tool(property_ids: List[str], purge_docs_first: bool = True) -> Dict:
    """Delete multiple properties (soft-delete) in sequence. Returns per-id results and total deleted.
    Use when the user asks to remove several properties at once, e.g. "borra Casa Demo 2 y Casa Demo 3".
    The LLM should resolve names to ids first using `search_properties` or a prior list.
    """
    return _delete_properties(property_ids, purge_docs_first)


class ProposeDocInput(BaseModel):
    filename: str
    hint: str = Field("", description="Optional free text / user hint to help classification")
    property_id: str = Field("", description="Optional property_id to help match facturas with placeholders")

@tool("propose_doc_slot")
def propose_doc_slot_tool(filename: str, hint: str = "", property_id: str = "") -> Dict:
    """Propose where a document should live in the documents framework. 
    If filename contains 'factura' and property_id is provided, will try to match with existing placeholders."""
    return _propose_slot(filename, hint, property_id)


class UploadAndLinkInput(BaseModel):
    property_id: str
    filename: str
    bytes_b64: str = Field(..., description="Base64 of the file to upload")
    document_group: str
    document_subgroup: str = ""
    document_name: str
    metadata: Dict = {}

@tool("upload_and_link")
def upload_and_link_tool(property_id: str, filename: str, bytes_b64: str,
                         document_group: str, document_subgroup: str, document_name: str,
                         metadata: Dict) -> Dict:
    """Upload the file to Storage and link it to the correct row in docs framework."""
    import base64
    file_bytes = base64.b64decode(bytes_b64)
    return _upload_and_link(property_id, file_bytes, filename,
                            document_group, document_subgroup, document_name, metadata)


class ListDocsInput(BaseModel):
    property_id: str

@tool("list_docs")
def list_docs_tool(property_id: str) -> Dict:
    """List all document rows for this property in REAL-TIME from the database.
    
    CRITICAL: ALWAYS call this tool when user asks to list/show/see documents. DO NOT rely on memory or previous calls.
    
    Returns: Dict with explicit categorization to prevent misinterpretation:
    {
        "uploaded": [...],  # Documents with storage_key (ACTUALLY UPLOADED)
        "pending": [...],   # Documents without storage_key (NOT YET UPLOADED)
        "total_uploaded": N,
        "total_pending": M,
        "summary": "Human-readable summary"
    }
    
    Each document has: document_group, document_subgroup, document_name, storage_key, metadata."""
    import logging
    logger = logging.getLogger(__name__)
    
    docs = _list_docs(property_id)
    
    # Explicitly separate uploaded vs pending
    uploaded_docs = [d for d in docs if d.get("storage_key")]
    pending_docs = [d for d in docs if not d.get("storage_key")]
    
    total_uploaded = len(uploaded_docs)
    total_pending = len(pending_docs)
    
    logger.info(f"🔍 [list_docs_tool] Property {property_id[:8]}...")
    logger.info(f"   - Total docs: {len(docs)}")
    logger.info(f"   - Uploaded (with storage_key): {total_uploaded}")
    logger.info(f"   - Pending (no storage_key): {total_pending}")
    
    # Create explicit summary to prevent agent confusion
    if total_uploaded == 0:
        summary = f"No hay documentos subidos. Hay {total_pending} documentos pendientes."
    elif total_uploaded == 1:
        summary = f"Hay 1 documento subido y {total_pending} pendientes."
    else:
        summary = f"Hay {total_uploaded} documentos subidos y {total_pending} pendientes."
    
    # Return structured data that's IMPOSSIBLE to misinterpret
    return {
        "uploaded": uploaded_docs,
        "pending": pending_docs,
        "total_uploaded": total_uploaded,
        "total_pending": total_pending,
        "summary": summary,
        "all_docs": docs  # Backwards compatibility
    }
    
    # Log all uploaded documents for verification
    if uploaded_docs:
        logger.info(f"   - Uploaded documents:")
        for doc in uploaded_docs:
            logger.info(f"     * {doc.get('document_group')} / {doc.get('document_subgroup')} / {doc.get('document_name')}")
    
    return docs


class SignedUrlInput(BaseModel):
    property_id: str
    document_group: str
    document_subgroup: str = ""
    document_name: str

@tool("signed_url_for")
def signed_url_for_tool(property_id: str, document_group: str, document_subgroup: str, document_name: str) -> Dict:
    """Create a signed URL for a stored document. The URL is valid for 24 hours (86400 seconds).
    Use this when you need to send a document link by email.
    Returns: {"signed_url": "https://..."}"""
    # Use 24 hours expiration (86400 seconds) for email links
    url = _signed_url_for(property_id, document_group, document_subgroup, document_name, expires=86400)
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[signed_url_for_tool] Generated URL for {document_name}, expires in 24h: {url[:50]}...")
    return {"signed_url": url}


class SlotExistsInput(BaseModel):
    property_id: str
    document_group: str
    document_subgroup: str = ""
    document_name: str

@tool("slot_exists")
def slot_exists_tool(property_id: str, document_group: str, document_subgroup: str, document_name: str) -> Dict:
    """Check if a document slot exists in the per-property documents framework (and list available names)."""
    return _slot_exists(property_id, document_group, document_subgroup, document_name)


# --- Related facturas ---
class ListRelatedFacturasInput(BaseModel):
    property_id: str
    document_group: str
    document_subgroup: str = ""
    document_name: str

@tool("list_related_facturas")
def list_related_facturas_tool(property_id: str, document_group: str, document_subgroup: str, document_name: str) -> List[Dict]:
    """List invoice placeholders/children for a given document (returns name, due_date, placeholder, storage_key)."""
    return _list_related_facturas(property_id, document_group, document_subgroup, document_name)


class SeedFacturasForInput(BaseModel):
    property_id: str
    document_group: str
    document_subgroup: str = ""
    document_name: str
    day_of_month: int = Field(..., ge=1, le=28)
    months: int = Field(12, ge=1, le=24)
    start_date: Optional[str] = Field(None, description="YYYY-MM-DD; default today")

@tool("seed_facturas_for")
def seed_facturas_for_tool(property_id: str, document_group: str, document_subgroup: str, document_name: str,
                           day_of_month: int, months: int = 12, start_date: Optional[str] = None) -> Dict:
    """Create monthly factura placeholders (children) for a parent document. Use when extraction fails or user provides a day. Idempotent."""
    return _seed_facturas_for(property_id, document_group, document_subgroup, document_name, day_of_month, months, start_date)


# --- seed mock docs for prototyping ---
class SeedMockDocsInput(BaseModel):
    property_id: str
    index_after: bool = True

@tool("seed_mock_documents")
def seed_mock_documents_tool(property_id: str, index_after: bool = True) -> Dict:
    """Create placeholder text files for all missing documents of a property. For prototyping only (marks metadata mock=True)."""
    return _seed_mock_documents(property_id, index_after)


# --- Purge documents ---
class PurgePropertyDocsInput(BaseModel):
    property_id: str

@tool("purge_property_documents")
def purge_property_documents_tool(property_id: str) -> Dict:
    """Delete all uploaded files for a single property and clear the document links."""
    return _purge_property_documents(property_id)


@tool("purge_all_documents")
def purge_all_documents_tool() -> Dict:
    """Delete all uploaded files for all properties and clear links."""
    return _purge_all_documents()

# --- Strategy Management (NEW) ---
class SetPropertyStrategyInput(BaseModel):
    property_id: str
    strategy: str = Field(..., description="Strategy: 'R2B', 'PROMOCION', 'R2B_VENTA', 'R2B_PM'")

@tool("set_property_strategy")
def set_property_strategy_tool(property_id: str, strategy: str) -> str:
    """Set the management strategy for a property (R2B, PROMOCION, R2B_VENTA, R2B_PM).
    This unlocks the corresponding document sections.
    """
    return _set_property_strategy(property_id, strategy)

class GetPropertyStrategyInput(BaseModel):
    property_id: str

@tool("get_property_strategy")
def get_property_strategy_tool(property_id: str) -> str:
    """Get the current management strategy for a property."""
    return _get_property_strategy(property_id)


class SetNumberInput(BaseModel):
    property_id: str
    item_key: str
    amount: Optional[float] = Field(None, description="Amount to set. Use None to clear/delete the value.")

@tool("set_number")
def set_number_tool(property_id: str, item_key: str, amount: Optional[float] = None) -> Dict:
    """Set a numeric input in the numbers framework. Use None to clear/delete a value."""
    return _set_number(property_id, item_key, amount)


class ClearNumberInput(BaseModel):
    property_id: str
    item_key: str

@tool("clear_number")
def clear_number_tool(property_id: str, item_key: str) -> Dict:
    """Clear/delete a specific number value in the numbers framework by setting it to None."""
    return _clear_number(property_id, item_key)


class FindItemByValueInput(BaseModel):
    property_id: str
    search_value: Optional[float] = Field(None, description="Value to search for (e.g., 10.0 for '10%')")
    search_label: Optional[str] = Field(None, description="Label text to search for (e.g., 'IVA', 'Precio de venta')")

@tool("find_item_by_value")
def find_item_by_value_tool(property_id: str, search_value: Optional[float] = None, search_label: Optional[str] = None) -> Optional[Dict]:
    """Find an item in the numbers framework by value or label. Useful for commands like 'borra IVA 10%'."""
    return _find_item_by_value(property_id, search_value, search_label)


class SetNumbersTableCellInput(BaseModel):
    property_id: str
    template_key: str = Field(default="R2B", description="Template key (usually 'R2B')")
    cell_address: str = Field(..., description="Excel cell address like 'B5', 'C10', etc.")
    value: str = Field(..., description="Value to set in the cell (as string)")

@tool("set_numbers_table_cell")
def set_numbers_table_cell_tool(property_id: str, template_key: str, cell_address: str, value: str) -> Dict:
    """Set a cell value in the Numbers Table (R2B template) using Excel cell addresses like 'B5', 'C10', etc.
    
    🔥 CÁLCULO AUTOMÁTICO EN CASCADA:
    - Cuando actualizas una celda amarilla (input del usuario como B5, C5), todas las fórmulas dependientes 
      se calculan AUTOMÁTICAMENTE en cascada.
    - Ejemplo: B5=1000, C5=21 → D5 (=B5*C5/100) se calcula a 210, luego E5 (=B5+D5) se calcula a 1210
    - El resultado incluirá "auto_calculated" con las celdas recalculadas automáticamente.
    
    This is the correct tool to use when working with the Numbers Table Framework.
    Example: set_numbers_table_cell(property_id='...', template_key='R2B', cell_address='B5', value='5000')
    
    Returns:
        Dict with ok=True, cell details, and "auto_calculated" dict with automatically calculated cells
    """
    return _set_numbers_table_cell(property_id, template_key, cell_address, value)


class ClearNumbersTableCellInput(BaseModel):
    property_id: str
    template_key: str = Field(default="R2B", description="Template key (usually 'R2B')")
    cell_address: str = Field(..., description="Excel cell address like 'B5', 'C10', etc.")

@tool("clear_numbers_table_cell")
def clear_numbers_table_cell_tool(property_id: str, template_key: str, cell_address: str) -> Dict:
    """Clear/delete a cell value in the Numbers Table (R2B template) using Excel cell addresses.
    This permanently removes the value from the database.
    Example: clear_numbers_table_cell(property_id='...', template_key='R2B', cell_address='B7')
    """
    return _clear_numbers_table_cell(property_id, template_key, cell_address)


@tool("delete_numbers_template")
def delete_numbers_template_tool(property_id: str, template_key: str = "R2B") -> Dict:
    """Delete the entire Numbers template (structure and all values) for a property.
    
    Use this when the user wants to:
    - Remove the Numbers table completely
    - Start fresh with a new template
    - Fix issues by re-importing the template
    
    This will DELETE ALL data in the Numbers table for this property.
    
    Example: delete_numbers_template(property_id='...', template_key='R2B')
    
    Returns:
        Dict with ok=True and counts of deleted records
    """
    return _delete_numbers_template(property_id, template_key)


class GetNumbersInput(BaseModel):
    property_id: str

@tool("get_numbers")
def get_numbers_tool(property_id: str) -> List[Dict]:
    """Return all inputs in numbers framework."""
    return _get_numbers(property_id)


class CalcNumbersInput(BaseModel):
    property_id: str

@tool("calc_numbers")
def calc_numbers_tool(property_id: str) -> List[Dict]:
    """Compute derived metrics using the schema-local calc() function."""
    return _calc_numbers(property_id)


# --- Numbers Agent derived computation and Excel export ---
class NumbersComputeInput(BaseModel):
    property_id: str
    triggered_by: str = Field("agent")
    trigger_type: str = Field("manual")

@tool("numbers_compute")
def numbers_compute_tool(property_id: str, triggered_by: str = "agent", trigger_type: str = "manual") -> Dict:
    """Compute derived metrics (impuestos_total, costes_totales, net_profit, roi_pct, etc.) and persist calc_outputs + calc_log. NEVER invents numbers; uses current inputs only."""
    return _numbers_compute_and_log(property_id, triggered_by, trigger_type)


class NumbersExcelInput(BaseModel):
    property_id: str

@tool("numbers_excel_export")
def numbers_excel_export_tool(property_id: str) -> Dict:
    """Generate an Excel (.xlsx) for the current numbers framework (Inputs, Derived, Anomalies) and return {filename, bytes_b64}."""
    import base64
    data = _numbers_excel(property_id)
    return {"filename": "numbers_framework.xlsx", "bytes_b64": base64.b64encode(data).decode("utf-8")}


@tool("export_numbers_table")
def export_numbers_table_tool(property_id: str, template_key: str = "R2B") -> Dict:
    """Export the Numbers table as an Excel file with the exact structure (headers, labels, format, values).
    This recreates the original Excel template with all current values from the database.
    Returns {filename, bytes_b64}."""
    import base64
    data = _numbers_table_excel(property_id, template_key)
    return {"filename": f"numbers_table_{template_key}.xlsx", "bytes_b64": base64.b64encode(data).decode("utf-8")}


# --- Scenarios ---
class NumbersWhatIfInput(BaseModel):
    property_id: str
    deltas: Dict[str, float]
    name: Optional[str] = None

@tool("numbers_what_if")
def numbers_what_if_tool(property_id: str, deltas: Dict[str, float], name: Optional[str] = None) -> Dict:
    """Compute a what-if scenario over the current numbers (deltas are fractional: -0.1 means -10%). Persist snapshot and return inputs/outputs/anomalies."""
    return _numbers_what_if(property_id, deltas, name)


class NumbersSensitivityInput(BaseModel):
    property_id: str
    precio_vec: List[float]
    costes_vec: List[float]

@tool("numbers_sensitivity")
def numbers_sensitivity_tool(property_id: str, precio_vec: List[float], costes_vec: List[float]) -> Dict:
    """Compute a 2D sensitivity grid for net_profit over precio_venta and costes_construccion fractional vectors."""
    return _numbers_sensitivity(property_id, precio_vec, costes_vec)


class NumbersBreakEvenInput(BaseModel):
    property_id: str
    tol: Optional[float] = 1.0

@tool("numbers_break_even")
def numbers_break_even_tool(property_id: str, tol: Optional[float] = 1.0) -> Dict:
    """Solve for precio_venta such that net_profit ≈ 0. Returns precio_venta and net_profit."""
    return _numbers_break_even(property_id, tol or 1.0)


# --- Charts ---
class NumbersChartWaterfallInput(BaseModel):
    property_id: str

@tool("numbers_chart_waterfall")
def numbers_chart_waterfall_tool(property_id: str) -> Dict:
    """Generate a waterfall chart (PNG) and return {signed_url}."""
    return _numbers_chart_waterfall(property_id)


class NumbersChartStackInput(BaseModel):
    property_id: str

@tool("numbers_chart_stack")
def numbers_chart_stack_tool(property_id: str) -> Dict:
    """Generate a stacked 100% cost composition chart (PNG) and return {signed_url}."""
    return _numbers_chart_cost_stack(property_id)


class NumbersChartSensitivityInput(BaseModel):
    property_id: str
    precio_vec: List[float]
    costes_vec: List[float]

@tool("numbers_chart_sensitivity")
def numbers_chart_sensitivity_tool(property_id: str, precio_vec: List[float], costes_vec: List[float]) -> Dict:
    """Generate a sensitivity heatmap (PNG) using given vectors; return {signed_url}."""
    return _numbers_chart_sensitivity(property_id, precio_vec, costes_vec)


# --- Numbers template selection (session-level) ---
class SetNumbersTemplateInput(BaseModel):
    property_id: str
    template_key: str = Field(..., description="One of: R2B | R2B+PM | R2B+PM+Venta certs | Promocion")

@tool("set_numbers_template")
def set_numbers_template_tool(property_id: str, template_key: str) -> Dict:
    """Set the active Numbers template for this property/session. 
    If the template doesn't exist in the database, it will be automatically imported from Excel.
    This will clear all existing values and start fresh."""
    from .numbers_tools import clear_numbers, initialize_template_structure, get_numbers_table_structure, import_excel_template
    import os
    
    # Check if structure already exists in DB
    structure = get_numbers_table_structure(property_id, template_key)
    
    # If structure exists and has cells, we're done
    if structure and structure.get("cells"):
        logger.info(f"Template {template_key} already exists in DB for property {property_id}")
        # CRÍTICO: NO decir "values_cleared: True" si no borramos nada
        return {"property_id": property_id, "template_key": template_key, "values_cleared": False, "imported": False, "note": "Template already exists, values preserved"}
    
    # Structure doesn't exist - try to import or initialize
    # For R2B template, try to import from Excel file upload (user must upload via UI)
    # For other templates or if import not available, use legacy initialization
    if template_key == "R2B":
        logger.info(f"Template {template_key} not found in DB. User should upload Excel file via UI button.")
        # Don't try Graph API import - user should upload file directly
        # The UI will show upload button and handle import
    else:
        # For non-R2B templates, use legacy initialization
        try:
            logger.info(f"Using legacy initialization for template {template_key}")
            initialize_template_structure(property_id, template_key)
        except Exception as e:
            logger.warning(f"Legacy initialization failed: {e}")
    
    # Clear all existing number values when selecting a new template
    try:
        clear_numbers(property_id)
    except:
        # If clearing fails, continue anyway - template selection is the priority
        pass
    
    return {"property_id": property_id, "template_key": template_key, "values_cleared": True, "imported": structure is None or not structure.get("cells")}


class GetSummarySpecInput(BaseModel):
    property_id: str

@tool("get_summary_spec")
def get_summary_spec_tool(property_id: str) -> List[Dict]:
    """Return the summary spec rows (for the agent to compute later)."""
    return _get_summary_spec(property_id)


class UpsertSummaryValueInput(BaseModel):
    property_id: str
    item_key: str
    amount: float
    provenance: Dict = {}

@tool("upsert_summary_value")
def upsert_summary_value_tool(property_id: str, item_key: str, amount: float, provenance: Dict) -> Dict:
    """Write a summary result value for a given item_key."""
    return _upsert_summary_value(property_id, item_key, amount, provenance)


class SendEmailInput(BaseModel):
    to: List[str]
    subject: str
    html: str

@tool("send_email")
def send_email_tool(to: List[str], subject: str, html: str) -> Dict:
    """Send an email (no attachments by default).
    
    When sending a document link, the HTML should include a clickable link like:
    <a href="https://signed-url-here" target="_blank">Descargar documento</a>
    
    Example HTML for document:
    <html><body>
      <p>Aquí está el documento que solicitaste: [document_name]</p>
      <p><a href="[signed_url]" target="_blank" style="background-color: #3d7435; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Descargar documento</a></p>
    </body></html>
    """
    return _send_email(to, subject, html)


class SendNumbersTableEmailInput(BaseModel):
    property_id: str
    template_key: str = Field(default="R2B", description="Template key (usually 'R2B')")
    to: List[str] = Field(..., description="List of email addresses to send to")
    subject: Optional[str] = Field(default=None, description="Email subject (optional, will use default if not provided)")

@tool("send_numbers_table_email")
def send_numbers_table_email_tool(property_id: str, template_key: str, to: List[str], subject: Optional[str] = None) -> Dict:
    """Send the Numbers table Excel file by email.
    Generates the Excel file from the Numbers table and sends it as an attachment.
    Example: send_numbers_table_email(property_id='...', template_key='R2B', to=['user@example.com'], subject='Plantilla R2B')
    """
    import base64
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"[send_numbers_table_email] Generating Excel for property_id={property_id}, template_key={template_key}")
        # Generate Excel file using the Numbers Table Framework
        excel_data = _numbers_table_excel(property_id, template_key)
        
        logger.info(f"[send_numbers_table_email] Excel generated successfully, size: {len(excel_data)} bytes")
        
        # Decode base64 if needed (export_numbers_table returns base64)
        # Actually, _numbers_table_excel returns bytes directly, not base64
        excel_bytes = excel_data
        
        # Generate filename
        filename = f"numbers_table_{template_key}.xlsx"
        
        # Default subject if not provided
        if not subject:
            subject = f"Plantilla de Números {template_key}"
        
        # Create HTML email body
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #3d7435;">📊 Plantilla de Números {template_key}</h2>
            <p>Adjunto encontrarás la plantilla de números {template_key} con todos los valores actuales.</p>
            <p>Este archivo Excel contiene la estructura completa de la plantilla y todos los valores guardados.</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                Este email fue generado automáticamente por RAMA Country Living.
            </p>
        </body>
        </html>
        """
        
        # Send email with attachment
        result = _send_email(to, subject, html, attachments=[(filename, excel_bytes)])
        
        logger.info(f"✅ Numbers table Excel sent to {to}: {filename}")
        return {
            "ok": True,
            "sent": True,
            "to": to,
            "subject": subject,
            "filename": filename,
            "message": f"Plantilla de números {template_key} enviada por email a {', '.join(to)}"
        }
    except Exception as e:
        logger.error(f"Error sending Numbers table email: {e}", exc_info=True)
        return {
            "ok": False,
            "error": str(e),
            "message": f"Error al enviar la plantilla por email: {str(e)}"
        }


# --- compute_summary tool ---
class ComputeSummaryInput(BaseModel):
    property_id: str
    only_items: Optional[List[str]] = Field(default=None, description="Optional list of item_keys to compute only those")

@tool("compute_summary")
def compute_summary_tool(property_id: str, only_items: Optional[List[str]] = None) -> Dict:
    """Compute summary_values per summary_spec: pulls from documents & numbers, evaluates formulas, upserts results."""
    return _compute_summary(property_id, only_items)


# --- Summary PowerPoint ---
class BuildSummaryPPTInput(BaseModel):
    property_id: str
    property_name: Optional[str] = None
    address: Optional[str] = None

@tool("build_summary_ppt")
def build_summary_ppt_tool(property_id: str, property_name: Optional[str] = None, address: Optional[str] = None, format: str = "pdf") -> Dict:
    """Build a summary presentation (PDF or PPTX) with fixed slides and upload to Supabase Storage. Returns {filename, signed_url} for download. Nunca inventa datos: usa números y docs existentes. Default format: PDF."""
    import base64
    from .supabase_client import sb
    
    data = _build_summary_ppt(property_id, property_name, address, format=format)
    ext = "pdf" if format.lower() == "pdf" else "pptx"
    filename = f"resumen_propiedad_{property_id[:8]}.{ext}"
    
    # Upload to Supabase Storage
    from .supabase_client import BUCKET
    bucket = BUCKET
    storage_key = f"summaries/{property_id}/{filename}"
    content_type = "application/pdf" if ext == "pdf" else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    
    try:
        # Upload with upsert to overwrite if exists
        sb.storage.from_(bucket).upload(storage_key, data, {"content-type": content_type, "upsert": "true"})
        
        # Generate signed URL (24 hours)
        signed = sb.storage.from_(bucket).create_signed_url(storage_key, 86400)
        signed_url = signed.get("signedURL")
        
        return {
            "filename": filename,
            "signed_url": signed_url,
            "storage_key": storage_key,
            "size_bytes": len(data)
        }
    except Exception as e:
        # Fallback: return base64 if storage fails
        return {
            "filename": filename,
            "bytes_b64": base64.b64encode(data).decode("utf-8"),
            "error": f"Storage upload failed: {str(e)}"
        }

# --- Reminders ---
class CreateReminderInput(BaseModel):
    property_id: str = Field(..., description="UUID de la propiedad")
    title: str = Field(..., description="Título del recordatorio (ej: 'Pago a arquitecto')")
    description: str = Field(..., description="Descripción detallada del recordatorio")
    reminder_date: str = Field(..., description="Fecha del recordatorio en formato DD/MM/YYYY o texto natural (ej: 'día 5', '15 de diciembre')")
    recipient_email: Optional[str] = Field(None, description="Email del destinatario (opcional)")
    document_reference: Optional[Dict] = Field(None, description="Referencia al documento relacionado")
    recurrence: Optional[str] = Field(None, description="Tipo de recurrencia: 'monthly' (mensual), 'yearly' (anual), o None para único")
    recurrence_count: Optional[int] = Field(None, description="Número de ocurrencias (default: 12 para monthly, 1 para None)")

@tool("create_reminder")
def create_reminder_tool(property_id: str, title: str, description: str, reminder_date: str, recipient_email: Optional[str] = None, document_reference: Optional[Dict] = None, recurrence: Optional[str] = None, recurrence_count: Optional[int] = None) -> Dict:
    """Crea un recordatorio (o múltiples si es recurrente). Si el usuario dice 'cada mes', usa recurrence='monthly' y recurrence_count=12. Si dice 'cada año', usa recurrence='yearly'. Para recordatorios únicos, deja recurrence=None."""
    return _create_reminder(property_id, title, description, reminder_date, recipient_email, document_reference, recurrence=recurrence, recurrence_count=recurrence_count)

class ExtractPaymentDateInput(BaseModel):
    property_id: str
    document_group: str
    document_subgroup: str
    document_name: str
    payment_concept: str = Field(..., description="Concepto del pago a buscar (ej: 'pago al arquitecto')")

@tool("extract_payment_date")
def extract_payment_date_tool(property_id: str, document_group: str, document_subgroup: str, document_name: str, payment_concept: str) -> Dict:
    """Extrae la fecha de pago de un documento específico usando análisis de contenido."""
    return _extract_payment_date(property_id, document_group, document_subgroup, document_name, payment_concept)

class ListRemindersInput(BaseModel):
    property_id: str
    status: Optional[str] = Field(None, description="Filtrar por estado: pending, sent, cancelled")

@tool("list_reminders")
def list_reminders_tool(property_id: str, status: Optional[str] = None) -> List[Dict]:
    """Lista todos los recordatorios de una propiedad. Muestra título, fecha, y estado."""
    return _list_reminders(property_id, status)

class CancelReminderInput(BaseModel):
    reminder_id: str = Field(..., description="UUID del recordatorio a cancelar")

@tool("cancel_reminder")
def cancel_reminder_tool(reminder_id: str) -> Dict:
    """Cancela un recordatorio existente."""
    return _cancel_reminder(reminder_id)

# --- Google voice tools ---
class TranscribeAudioInput(BaseModel):
    bytes_b64: str
    language_code: Optional[str] = None

@tool("transcribe_audio")
def transcribe_audio_tool(bytes_b64: str, language_code: Optional[str] = None) -> Dict:
    """Speech-to-Text using Google Cloud Speech. Returns {'text': ...}."""
    import base64
    text = _transcribe_google_wav(base64.b64decode(bytes_b64), language_code)
    return {"text": text}

class SynthesizeSpeechInput(BaseModel):
    text: str
    language_code: Optional[str] = None
    voice_name: Optional[str] = None

@tool("synthesize_speech")
def synthesize_speech_tool(text: str, language_code: Optional[str] = None, voice_name: Optional[str] = None) -> Dict:
    """Text-to-Speech using Google Cloud TTS. Returns {'audio_b64_mp3': ...}."""
    import base64
    audio = _tts_google(text, language_code, voice_name)
    return {"audio_b64_mp3": base64.b64encode(audio).decode("utf-8")}

class ProcessVoiceInputInput(BaseModel):
    audio_b64: str
    language_code: Optional[str] = None

@tool("process_voice_input")
def process_voice_input_tool(audio_b64: str, language_code: Optional[str] = None) -> Dict:
    """Process voice input from frontend. Returns structured response with transcribed text."""
    import base64
    audio_data = base64.b64decode(audio_b64)
    return _process_voice_input(audio_data, language_code)

class CreateVoiceResponseInput(BaseModel):
    text: str
    language_code: Optional[str] = None

@tool("create_voice_response")
def create_voice_response_tool(text: str, language_code: Optional[str] = None) -> Dict:
    """Create voice response for given text. Returns both text and audio data."""
    return _create_voice_response(text, language_code)

# --- property query tools ---
class GetPropertyInput(BaseModel):
    property_id: str

@tool("get_property")
def get_property_tool(property_id: str) -> Optional[Dict]:
    """Fetch a property row by UUID."""
    return _get_property(property_id)


class FindPropertyInput(BaseModel):
    name: str
    address: str

@tool("find_property")
def find_property_tool(name: str, address: str) -> Optional[Dict]:
    """Find a property by name and address (exact match)."""
    return _find_property(name, address)


class ListPropertiesInput(BaseModel):
    limit: int = Field(20, ge=1, le=100)

@tool("list_properties")
def list_properties_tool(limit: int = 20) -> List[Dict]:
    """List recent properties for verification and selection."""
    return _list_properties(limit)

class SearchPropertiesInput(BaseModel):
    query: str = Field(..., description="Free text to match name or address (ilike).")
    limit: int = Field(5, ge=1, le=50)

@tool("search_properties")
def search_properties_tool(query: str, limit: int = 5) -> List[Dict]:
    """Search properties by name or address (fuzzy, case-insensitive)."""
    return _search_properties(query, limit)

# --- summarize document (RAG-lite) ---
class SummarizeDocumentInput(BaseModel):
    property_id: str
    document_group: str
    document_subgroup: str = ""
    document_name: str
    model: Optional[str] = None
    max_sentences: int = Field(5, ge=1, le=15)

@tool("summarize_document")
def summarize_document_tool(property_id: str, document_group: str, document_subgroup: str, document_name: str, model: Optional[str] = None, max_sentences: int = 5) -> Dict:
    """Fetches the document via signed URL and returns a short summary. Use when the user asks to summarize a specific document."""
    return _summarize_document(property_id, document_group, document_subgroup, document_name, model, max_sentences)

# --- question-answer on a specific document ---
class QADocumentInput(BaseModel):
    property_id: str
    document_group: str
    document_subgroup: str = ""
    document_name: str
    question: str
    model: Optional[str] = None

@tool("qa_document")
def qa_document_tool(property_id: str, document_group: str, document_subgroup: str, document_name: str, question: str, model: Optional[str] = None) -> Dict:
    """Answer a focused question about a single stored document in Spanish."""
    return _qa_document(property_id, document_group, document_subgroup, document_name, question, model)

# --- payment schedule QA ---
class QAPaymentScheduleInput(BaseModel):
    property_id: str
    document_group: str
    document_subgroup: str = ""
    document_name: str
    today_iso: Optional[str] = None

@tool("qa_payment_schedule")
def qa_payment_schedule_tool(property_id: str, document_group: str, document_subgroup: str, document_name: str, today_iso: Optional[str] = None) -> Dict:
    """Extract payment cadence and compute next due date based on the document text."""
    return _qa_payment_schedule(property_id, document_group, document_subgroup, document_name, today_iso)

# --- RAG indexing + QA with citations ---
class IndexDocumentInput(BaseModel):
    property_id: str
    document_group: str
    document_subgroup: str = ""
    document_name: str

@tool("rag_index_document")
def rag_index_document_tool(property_id: str, document_group: str, document_subgroup: str, document_name: str) -> Dict:
    """Fetches, splits and stores document chunks for retrieval QA."""
    return _index_document(property_id, document_group, document_subgroup, document_name)

class QAWithCitationsInput(BaseModel):
    property_id: str
    query: str
    top_k: int = 5
    document_name: str | None = None
    document_group: str | None = None
    document_subgroup: str | None = None

@tool("rag_qa_with_citations")
def rag_qa_with_citations_tool(property_id: str, query: str, top_k: int = 5, document_name: str | None = None, document_group: str | None = None, document_subgroup: str | None = None) -> Dict:
    """RAG QA over indexed chunks; returns answer and citations. Optionally filter by document_name, document_group, document_subgroup to search only in specific document(s)."""
    return _qa_with_citations(property_id, query, top_k, document_name=document_name, document_group=document_group, document_subgroup=document_subgroup)

class IndexAllDocumentsInput(BaseModel):
    property_id: str

@tool("rag_index_all_documents")
def rag_index_all_documents_tool(property_id: str) -> Dict:
    """Index all documents with file for a property. Use at session start or when results seem incomplete."""
    return _index_all_documents(property_id)

# Export the registry
TOOLS = [
    add_property_tool,
    list_frameworks_tool,
    delete_property_tool,
    delete_properties_tool,
    propose_doc_slot_tool,
    upload_and_link_tool,
    list_docs_tool,
    signed_url_for_tool,
    set_number_tool,
    clear_number_tool,  # NEW - Clear/delete a specific number value
    find_item_by_value_tool,  # NEW - Find item by value or label
    set_numbers_table_cell_tool,  # NEW - Set cell value in Numbers Table (R2B) using Excel addresses
    clear_numbers_table_cell_tool,  # NEW - Clear/delete cell value in Numbers Table (R2B) using Excel addresses
    set_numbers_template_tool,  # NEW - Set Numbers template selection
    delete_numbers_template_tool,  # NEW - Delete entire Numbers template and all values
    get_numbers_tool,
    calc_numbers_tool,
    numbers_compute_tool,
    numbers_excel_export_tool,
    numbers_what_if_tool,
    numbers_sensitivity_tool,
    numbers_break_even_tool,
    numbers_chart_waterfall_tool,
    numbers_chart_stack_tool,
    numbers_chart_sensitivity_tool,
    get_summary_spec_tool,
    upsert_summary_value_tool,
    send_email_tool,
    send_numbers_table_email_tool,  # NEW - Send Numbers table Excel by email
    compute_summary_tool,          # NEW
    build_summary_ppt_tool,        # NEW - Generate PDF summary
    transcribe_audio_tool,         # NEW
    synthesize_speech_tool,
    process_voice_input_tool,      # NEW - Enhanced voice processing
    create_voice_response_tool,    # NEW - Enhanced voice response
    get_property_tool,             # NEW
    set_current_property_tool,     # NEW
    find_property_tool,            # NEW
    list_properties_tool,          # NEW
    search_properties_tool,        # NEW
    summarize_document_tool,       # NEW
    qa_document_tool,              # NEW
    qa_payment_schedule_tool,      # NEW
    rag_index_document_tool,       # NEW
    rag_qa_with_citations_tool,    # NEW
    rag_index_all_documents_tool,  # NEW
    slot_exists_tool,              # NEW
    list_related_facturas_tool,    # NEW - List placeholders/children invoices
    seed_facturas_for_tool,        # NEW - Seed invoice placeholders
    purge_property_documents_tool, # NEW
    purge_all_documents_tool,      # NEW
    set_property_strategy_tool,    # NEW
    get_property_strategy_tool,    # NEW
    create_reminder_tool,          # NEW - Recordatorios
    extract_payment_date_tool,     # NEW - Extrae fechas de documentos
    list_reminders_tool,           # NEW - Lista recordatorios
    cancel_reminder_tool,          # NEW - Cancela recordatorios
]
