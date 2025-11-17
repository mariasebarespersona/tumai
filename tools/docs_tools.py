from __future__ import annotations
import io, mimetypes, os, re, datetime as dt
from typing import Dict, List, Optional, Tuple
from .supabase_client import sb, BUCKET
from .utils import docs_schema, utcnow_iso

# -------- classification proposal (simple heuristic + LLM-friendly output) -----
# New taxonomy aligned with pictures (I/II/III/IV)
# Groups: "R2B" (Section I - mandatory), "Venta R2B" (II), "Venta R2B + Raquel PM" (III), "Promoción" (IV)
# Subgroups used when helpful (e.g., "Compra", "Diseño/Obra", "Venta")

DOC_GROUPS = {
    # I) R2B (mandatory for all properties)
    "R2B:Compra": [
        "catastro", "nota simple", "acuerdo compraventa", "acuerdo de compraventa",
        "señal", "senal", "arras", "due diligence compra", "dd compra",
        "escritura notarial de compraventa", "escritura compraventa", "escritura notarial",
        "notaria factura", "notaría factura", "impuestos de compra", "itp", "iva", "actos juridicos", "actos jurídicos",
        "registro de la propiedad", "registro propiedad"
    ],
    "R2B:Diseño/Obra": [
        "mapas nivel", "mapas de nivel", "contrato arquitecto", "contrato de arquitecto",
        "proyecto basico", "proyecto básico", "mediciones", "planos",
        "contrato aparejador", "licencia de obra", "acometidas",
        "contrato constructor"
    ],

    # II) Venta R2B
    "Venta R2B:": [
        "due diligence de venta", "dd de venta", "arras venta", "venta terreno",
        "venta proyecto", "escritura compraventa", "impuestos de venta"
    ],

    # III) Venta R2B + Raquel PM
    "Venta R2B + Raquel PM:": [
        "planificacion obra", "planificación obra", "cronograma", "contrato obra",
        "facturas", "contrato raquel", "pm"
    ],

    # IV) Promoción (Obra nueva + Venta)
    "Promoción:Obra nueva": [
        "planificacion obra", "planificación obra", "cronograma", "contrato obra",
        "facturas", "oct", "seguro decenal", "libro del edificio", "escritura obra nueva"
    ],
    "Promoción:Venta": [
        "contrato arras venta", "registro obra nueva", "escritura compraventa", "impuestos de venta"
    ],
}

# Map keywords to canonical document names (exact cell names in DB)
KEYWORD_TO_DOCNAME = {
    # I) R2B - Compra
    "catastro": "Catastro y nota simple",
    "nota simple": "Catastro y nota simple",
    "acuerdo compraventa": "Acuerdo compraventa (verbal)",
    "acuerdo de compraventa": "Acuerdo compraventa (verbal)",
    "señal": "Señal / Arras",
    "senal": "Señal / Arras",
    "arras": "Señal / Arras",
    "due diligence compra": "Due Diligence (DD) compra",
    "dd compra": "Due Diligence (DD) compra",
    "escritura notarial de compraventa": "Escritura notarial de compraventa",
    "escritura compraventa": "Escritura notarial de compraventa",
    "escritura notarial": "Escritura notarial de compraventa",
    "notaria factura": "Notaría — factura",
    "notaría factura": "Notaría — factura",
    "impuestos de compra": "Impuestos de compra (ITP/IVA/Actos jurídicos)",
    "itp": "Impuestos de compra (ITP/IVA/Actos jurídicos)",
    "iva": "Impuestos de compra (ITP/IVA/Actos jurídicos)",
    "actos juridicos": "Impuestos de compra (ITP/IVA/Actos jurídicos)",
    "actos jurídicos": "Impuestos de compra (ITP/IVA/Actos jurídicos)",
    "registro de la propiedad": "Registro de la propiedad",
    "registro propiedad": "Registro de la propiedad",

    # I) R2B - Diseño/Obra
    "mapas nivel": "Mapas Nivel",
    "mapas de nivel": "Mapas Nivel",
    "contrato arquitecto": "Contrato arquitecto",
    "contrato de arquitecto": "Contrato arquitecto",
    "proyecto basico": "Proyecto básico / mediciones / planos",
    "proyecto básico": "Proyecto básico / mediciones / planos",
    "mediciones": "Proyecto básico / mediciones / planos",
    "planos": "Proyecto básico / mediciones / planos",
    "contrato aparejador": "Contrato Aparejador",
    "licencia de obra": "Licencia de obra y acometidas",
    "acometidas": "Licencia de obra y acometidas",
    "contrato constructor": "Contrato constructor",

    # II) Venta R2B
    "due diligence de venta": "Due Diligence (DD) de venta",
    "dd de venta": "Due Diligence (DD) de venta",
    "arras venta": "Arras venta",
    "venta terreno": "Venta terreno",
    "venta proyecto": "Venta proyecto",
    "impuestos de venta": "Impuestos de venta",

    # III) Venta R2B + Raquel PM
    "planificacion obra": "Planificación obra (cronograma)",
    "planificación obra": "Planificación obra (cronograma)",
    "cronograma": "Planificación obra (cronograma)",
    "contrato obra": "Contrato obra",
    "facturas": "Facturas (múltiples documentos)",
    "contrato raquel": "Contrato Raquel como PM",
    "pm": "Contrato Raquel como PM",

    # IV) Promoción (Obra nueva + Venta)
    "oct": "OCT",
    "seguro decenal": "Seguro decenal",
    "libro del edificio": "Libro del edificio",
    "escritura obra nueva": "Escritura obra nueva",
    "contrato arras venta": "Contrato arras venta",
    "registro obra nueva": "Registro obra nueva",
}

# Docs that should spawn factura placeholders when uploaded
FACTURABLE_DOCS = {
    ("R2B", "Diseño/Obra", "Mapas Nivel"): "Facturas mapas nivel",
    ("R2B", "Diseño/Obra", "Contrato arquitecto"): "Facturas arquitecto",
    ("R2B", "Diseño/Obra", "Proyecto básico / mediciones / planos"): "Facturas proyecto/planos",
    ("R2B", "Diseño/Obra", "Contrato Aparejador"): "Facturas aparejador",
    ("R2B", "Diseño/Obra", "Licencia de obra y acometidas"): "Facturas licencia y acometidas",
    ("R2B", "Diseño/Obra", "Contrato constructor"): "Facturas constructor",
}


def _normalize(text: str) -> str:
    # Lowercase and collapse non-alnum to spaces for robust keyword matches
    t = (text or "").lower()
    return re.sub(r"[^a-z0-9áéíóúüñ]+", " ", t)


def propose_slot(filename: str, text_hint: str = "", property_id: str = "") -> Dict:
    """Propose document slot based on filename and hint. 
    If it's a factura, tries to match with existing placeholders by date/name.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # IMPORTANT: Extract date BEFORE normalizing (normalize removes hyphens/slashes)
    date_match = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})|(\d{1,2}[-/]\d{1,2}[-/]\d{4})", filename)
    extracted_date = date_match.group(0).replace("/", "-") if date_match else None
    
    fn = _normalize(filename)
    hint = _normalize(text_hint)
    combined = fn + " " + hint
    
    logger.info(f"🔍 propose_slot: filename={filename}, property_id={property_id}, combined={combined}")
    logger.info(f"📅 Extracted date from filename (before normalize): {extracted_date}")
    
    # Check if this is a factura being uploaded
    is_factura = "factura" in combined or "invoice" in combined
    logger.info(f"📋 is_factura={is_factura}")
    
    # If it's a factura AND we have property_id, try to match with placeholders
    if is_factura and property_id:
        try:
            
            # Try to find matching placeholder
            all_docs = list_docs(property_id)
            
            # Count facturas for debugging
            factura_placeholders = [d for d in all_docs if d.get("document_kind") == "factura" and d.get("placeholder")]
            logger.info(f"🔎 Found {len(factura_placeholders)} factura placeholders in total")
            
            # First pass: exact date match
            if extracted_date:
                logger.info(f"🔍 Looking for placeholders with date: {extracted_date}")
                for doc in all_docs:
                    if (doc.get("document_kind") == "factura" 
                        and doc.get("placeholder") 
                        and doc.get("due_date")):
                        doc_name = doc.get("document_name", "")
                        # Match: "Facturas arquitecto — 2025-11-05"
                        logger.info(f"  Checking: {doc_name}")
                        if extracted_date in doc_name:
                            logger.info(f"✅ MATCH FOUND: {doc_name}")
                            return {
                                "document_group": doc.get("document_group"),
                                "document_subgroup": doc.get("document_subgroup") or "",
                                "document_name": doc_name,
                                "is_placeholder_replacement": True
                            }
                logger.info(f"❌ No exact date match found for {extracted_date}")
            
            # Second pass: match by parent document type in filename
            # e.g., "factura-arquitecto-2025-11-05.pdf" → find "Facturas arquitecto" placeholders
            for parent_key, factura_title in FACTURABLE_DOCS.items():
                parent_name = parent_key[2].lower()
                # Check if parent name keyword appears in combined text
                if parent_name.split()[0] in combined:  # e.g., "arquitecto" in "factura-arquitecto"
                    # Find the first pending placeholder for this parent
                    for doc in all_docs:
                        if (doc.get("document_kind") == "factura"
                            and doc.get("placeholder")
                            and factura_title.lower() in doc.get("document_name", "").lower()
                            and not doc.get("storage_key")):  # not yet filled
                            return {
                                "document_group": doc.get("document_group"),
                                "document_subgroup": doc.get("document_subgroup") or "",
                                "document_name": doc.get("document_name"),
                                "is_placeholder_replacement": True
                            }
        except Exception as e:
            # Log and continue to standard classification
            import logging
            logging.getLogger(__name__).warning(f"Factura placeholder matching failed: {e}")
    
    # Standard document classification (not a factura or no match found)
    all_keywords = []
    for key, kws in DOC_GROUPS.items():
        for kw in kws:
            parts = key.split(":")
            group = parts[0]
            subgroup = parts[1] if len(parts) > 1 else ""
            all_keywords.append((kw, group, subgroup))
    
    # Sort by keyword length (longest first) to prioritize specific matches
    all_keywords.sort(key=lambda x: -len(x[0]))
    
    # Find the first (longest) keyword that matches
    for kw, group, subgroup in all_keywords:
        if kw in combined:
            doc_name = KEYWORD_TO_DOCNAME.get(kw, kw.title())
            return {"document_group": group, "document_subgroup": subgroup, "document_name": doc_name}
    
    # Default fallback
    return {"document_group": "R2B", "document_subgroup": "Compra", "document_name": "Acuerdo compraventa (verbal)"}

# -------- upload + link --------------------------------------------------------

def upload_and_link(property_id: str, file_bytes: bytes, filename: str,
                    document_group: str, document_subgroup: str, document_name: str,
                    metadata: Dict | None = None) -> Dict:
    """
    1) upload to Storage at key: property/<pid>/<group>/<filename>
    2) update the matching cell row in per-property documents table
    """
    import logging
    logger = logging.getLogger(__name__)
    
    key = f"property/{property_id}/{document_group}/{filename}"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    
    logger.info(f"📤 Uploading document: {filename} → {key}")

    # Step 1: Upload to Storage FIRST (with upsert for idempotency)
    try:
        sb.storage.from_(BUCKET).upload(key, file_bytes, {"content-type": content_type, "upsert": "true"})
        logger.info(f"✅ Storage upload successful: {key}")
    except Exception as e:
        logger.error(f"❌ Storage upload failed for {key}: {e}")
        raise Exception(f"Failed to upload file to storage: {e}")
    
    # Step 2: Get signed URL
    try:
        signed = sb.storage.from_(BUCKET).create_signed_url(key, 3600)  # 1 hour
        logger.info(f"✅ Signed URL created for {key}")
    except Exception as e:
        logger.error(f"❌ Failed to create signed URL for {key}: {e}")
        raise Exception(f"Failed to create signed URL: {e}")

    schema = docs_schema(property_id)
    sg = document_subgroup or ""
    expires_at = utcnow_iso()

    upd = {
        "storage_key": key,
        "content_type": content_type,
        "metadata": metadata or {},
        "last_signed_url": signed.get("signedURL"),
        "signed_url_expires_at": expires_at,
    }

    # Always use RPC to avoid PostgREST schema cache issues (PGRST205)
    existing: List[Dict] = []
    try:
        # 1) Verify cell exists via RPC
        all_docs = sb.rpc("list_property_documents", {"p_id": property_id}).execute().data or []
        existing = [
            d for d in all_docs
            if d.get("document_group") == document_group
            and (d.get("document_subgroup") or "") == sg
            and d.get("document_name") == document_name
        ]
        if not existing:
            # CRÍTICO: Si la celda no existe, intentar inicializar el esquema primero
            logger.warning(f"⚠️ Celda no encontrada: {document_group} / {sg} / {document_name}. Intentando inicializar esquema...")
            try:
                # Intentar inicializar el esquema de documentos para esta propiedad
                sb.rpc("ensure_documents_schema_v2", {"p_id": property_id}).execute()
                logger.info(f"✅ Esquema inicializado para propiedad {property_id}")
                # Verificar de nuevo después de inicializar
                all_docs = sb.rpc("list_property_documents", {"p_id": property_id}).execute().data or []
                existing = [
                    d for d in all_docs
                    if d.get("document_group") == document_group
                    and (d.get("document_subgroup") or "") == sg
                    and d.get("document_name") == document_name
                ]
                if not existing:
                    raise ValueError(
                        f"La celda no existe después de inicializar el esquema: {document_group} / {sg} / {document_name}."
                    )
            except Exception as init_error:
                logger.error(f"❌ Error al inicializar esquema: {init_error}")
                raise ValueError(
                    f"La celda no existe: {document_group} / {sg} / {document_name}. Error al inicializar esquema: {init_error}"
                )
        
        # 2) Update via RPC
        payload = {
            "p_id": property_id,
            "g": document_group,
            "sg": sg,
            "n": document_name,
            "storage_key": key,
            "content_type": content_type,
            "metadata": metadata or {},
            "signed_url": signed.get("signedURL"),
            "expires_at": expires_at,
        }
        sb.rpc("update_property_document_link", payload).execute()
        logger.info(f"✅ Database updated via RPC for {document_name}")
        
    except Exception as e:
        logger.error(f"❌ RPC update failed: {e}")
        raise Exception(f"Failed to update database: {e}")

    # After successful link, attempt factura placeholder generation if applicable
    facturas_info = {}
    try:
        facturas_info = _maybe_generate_facturas(property_id, document_group, sg, document_name, existing[0]["id"] if existing else None)
    except Exception as gen_err:
        # Non-fatal
        logger = __import__("logging").getLogger(__name__)
        logger.warning(f"Factura placeholder generation skipped: {gen_err}")

    logger.info(f"🎉 Document upload complete: {filename}")
    result = {"storage_key": key, "signed_url": signed.get("signedURL"), "document_name": document_name}
    if facturas_info:
        result["facturas_generated"] = facturas_info
    return result


def _month_sequence(start_date: dt.date, count: int, day_of_month: int, step: int = 1) -> List[dt.date]:
    """Generate a sequence of dates with given day_of_month, stepping by 'step' months.
    Args:
        start_date: Starting date
        count: Number of dates to generate
        day_of_month: Day of month (1-28)
        step: Number of months between each date (1=monthly, 3=quarterly, 12=yearly)
    """
    dates: List[dt.date] = []
    dom = max(1, min(28, int(day_of_month)))
    y, m = start_date.year, start_date.month
    for i in range(count):
        month = m + (i * step)
        year = y + (month - 1) // 12
        mm = ((month - 1) % 12) + 1
        dates.append(dt.date(year, mm, dom))
    return dates


def _maybe_generate_facturas(property_id: str, group: str, subgroup: str, name: str, parent_id: Optional[str]) -> Dict:
    """If the uploaded doc is in the facturable set, read cadence via QA
    and create up to 12 monthly factura placeholders attached to the parent.
    Returns: {status: "created"|"not_facturable"|"rag_failed", count: int, day: int}
    """
    # Check if the (group, subgroup, name) is configured for invoices
    key = (group, subgroup or "", name)
    if key not in FACTURABLE_DOCS:
        return {"status": "not_facturable"}

    try:
        from .rag_tool import qa_payment_schedule
    except Exception:
        return {"status": "rag_unavailable"}

    # Ask the LLM for cadence information
    info = qa_payment_schedule(property_id, group, subgroup, name)
    extracted = info.get("extracted", {}) if isinstance(info, dict) else {}
    frequency = extracted.get("frequency")
    day_of_month = extracted.get("day_of_month")
    total_payments = extracted.get("total_payments")
    contract_years = extracted.get("contract_years")
    
    # Fallback: if monthly frequency present but no day, try derive from next_due_date
    if (not day_of_month) and info.get("next_due_date"):
        try:
            dom = int(str(info.get("next_due_date")).split("-")[-1])
            if 1 <= dom <= 28:
                day_of_month = dom
                frequency = frequency or "monthly"
        except Exception:
            pass
    
    # Determine number of placeholders to create based on frequency and duration
    if not frequency or not day_of_month:
        # RAG didn't find a clear cadence
        return {"status": "rag_failed", "info": info}
    
    # Calculate count based on explicit total_payments or derive from frequency + duration
    if total_payments:
        count = int(total_payments)
    elif frequency == "yearly":
        count = contract_years if contract_years else 1
    elif frequency == "quarterly":
        count = (contract_years * 4) if contract_years else 4
    elif frequency == "monthly":
        count = (contract_years * 12) if contract_years else 12  # default 1 year
    elif frequency == "every_15_days":
        count = (contract_years * 24) if contract_years else 24
    else:
        count = 12  # fallback
    
    count = min(count, 36)  # cap at 36 to avoid excessive placeholders
    
    start = dt.date.today()
    
    # Generate dates based on frequency
    if frequency == "monthly":
        seq = _month_sequence(start, count, int(day_of_month))
    elif frequency == "quarterly":
        seq = _month_sequence(start, count, int(day_of_month), step=3)
    elif frequency == "yearly":
        seq = _month_sequence(start, count, int(day_of_month), step=12)
    else:
        seq = _month_sequence(start, count, int(day_of_month))

    # Insert placeholders via RPC to avoid PostgREST schema cache issues
    base_title = FACTURABLE_DOCS[key]
    created = 0
    for d in seq:
        factura_name = f"{base_title} — {d.isoformat()}"
        try:
            sb.rpc("insert_property_document", {
                "p_id": property_id,
                "g": group,
                "sg": subgroup or "",
                "n": factura_name,
                "doc_kind": "factura",
                "parent_id": parent_id,
                "due_date": d.isoformat(),
                "is_placeholder": True,
                "is_auto_generated": True,
                "metadata": {"generated_from": name}
            }).execute()
            created += 1
        except Exception:
            # Continue best-effort
            pass
    return {"status": "created", "count": created, "day": int(day_of_month), "frequency": frequency}


def seed_facturas_for(property_id: str, document_group: str, document_subgroup: str, document_name: str,
                      day_of_month: int, months: int = 12, start_date: Optional[str] = None) -> Dict:
    """Create factura placeholders for a given parent document with a fixed monthly cadence.
    Args:
      - day_of_month: 1..28
      - months: number of placeholders (default 12)
      - start_date: ISO date (YYYY-MM-DD); if None, today
    Returns: {created: int}
    """
    sg = document_subgroup or ""
    # Find parent id via RPC
    all_docs = sb.rpc("list_property_documents", {"p_id": property_id}).execute().data or []
    parent_id = None
    for d in all_docs:
        if (d.get("document_group") == document_group
            and (d.get("document_subgroup") or "") == sg
            and d.get("document_name") == document_name):
            parent_id = d.get("id")
            break
    if not parent_id:
        return {"created": 0, "error": "parent_not_found"}
    # Base title from mapping
    base_title = FACTURABLE_DOCS.get((document_group, sg, document_name), "Facturas")
    start = dt.date.fromisoformat(start_date) if start_date else dt.date.today()
    seq = _month_sequence(start, max(1, int(months)), max(1, min(28, int(day_of_month))))
    created = 0
    for d in seq:
        factura_name = f"{base_title} — {d.isoformat()}"
        try:
            sb.rpc("insert_property_document", {
                "p_id": property_id,
                "g": document_group,
                "sg": sg,
                "n": factura_name,
                "doc_kind": "factura",
                "parent_id": parent_id,
                "due_date": d.isoformat(),
                "is_placeholder": True,
                "is_auto_generated": True,
                "metadata": {"generated_from": document_name, "seeded": True}
            }).execute()
            created += 1
        except Exception:
            # ignore duplicates or insert errors for idempotency
            pass
    return {"created": created}


def list_docs(property_id: str) -> List[Dict]:
    """
    List documents rows for a property. Falls back to RPC if dynamic schema is not exposed by PostgREST.
    
    IMPORTANT: This reads directly from the database, NOT from cache or vector index.
    This ensures we always see the latest uploaded documents.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"📋 Listing documents for property: {property_id}")
    schema = docs_schema(property_id)
    logger.info(f"🔍 Using schema: {schema}")
    try:
        sb.postgrest.schema = schema
        rows = (sb.table("documents")
                .select("document_group,document_subgroup,document_name,storage_key,metadata,document_kind,parent_document_id,due_date,placeholder,auto_generated")
                .eq("property_id", property_id)
                .order("document_group,document_subgroup,document_name")
                .execute()).data
        logger.info(f"✅ Direct query in {schema} returned {len(rows)} rows")
        # Some deployments don't expose per-schema tables fully and return 0 without error.
        # In that case, fall back to RPC which is schema-aware server-side.
        if not rows:
            logger.warning("⚠️ Direct query returned 0 rows. Falling back to RPC list_property_documents")
            try:
                # Ensure RPC is called on public schema
                sb.postgrest.schema = "public"
            except Exception:
                pass
            result = sb.rpc("list_property_documents", {"p_id": property_id}).execute().data
            return result or []
        return rows
    except Exception as e:
        logger.warning(f"⚠️ Direct query failed, trying RPC: {e}")
        # Fallback through RPC function that queries the per-property schema server-side
        # Requires SQL function: public.list_property_documents(p_id uuid)
        try:
            try:
                sb.postgrest.schema = "public"
            except Exception:
                pass
            result = sb.rpc("list_property_documents", {"p_id": property_id}).execute().data
            logger.info(f"✅ Found {len(result)} documents via RPC")
            return result
        except Exception as rpc_error:
            logger.error(f"❌ RPC also failed: {rpc_error}")
            return []


def signed_url_for(property_id: str, document_group: str, document_subgroup: str, document_name: str, expires: int = 3600) -> str:
    sg = document_subgroup or ""
    # Always use RPC to avoid PGRST205
    key = sb.rpc(
        "get_property_document_storage_key",
        {"p_id": property_id, "g": document_group, "sg": sg, "n": document_name}
    ).execute().data
    if not key:
        raise ValueError("No file stored for that document cell")
    return sb.storage.from_(BUCKET).create_signed_url(key, expires)["signedURL"]


def slot_exists(property_id: str, document_group: str, document_subgroup: str, document_name: str) -> Dict:
    """Check whether a (group, subgroup, name) cell exists in the per-property documents table.
    Returns {exists: bool, candidates: [names available in that group/subgroup]}.
    """
    sg = document_subgroup or ""
    # Always use RPC to avoid PGRST205
    rows = sb.rpc("list_property_documents", {"p_id": property_id}).execute().data or []
    names = [r["document_name"] for r in rows if r.get("document_group") == document_group and (r.get("document_subgroup") or "") == sg]
    return {"exists": document_name in names, "candidates": names}


# -------- queries: related facturas -----------------------------------------
def list_related_facturas(property_id: str, document_group: str, document_subgroup: str, document_name: str) -> List[Dict]:
    """Return all factura rows attached to a given document (parent→children).
    This version uses the RPC `list_property_documents` to avoid schema permission issues.
    Each item: {document_name, due_date, placeholder, storage_key}.
    """
    sg = document_subgroup or ""
    try:
        # Always call RPC on public schema
        try:
            sb.postgrest.schema = "public"
        except Exception:
            pass
        all_rows = sb.rpc("list_property_documents", {"p_id": property_id}).execute().data or []
        # Find parent id
        parent_id = None
        for r in all_rows:
            if (
                r.get("document_group") == document_group
                and (r.get("document_subgroup") or "") == sg
                and r.get("document_name") == document_name
            ):
                parent_id = r.get("id")
                break
        rel: List[Dict] = []
        for r in all_rows:
            if (
                r.get("document_group") == document_group
                and (r.get("document_subgroup") or "") == sg
                and r.get("document_kind") == "factura"
                and (not parent_id or r.get("parent_document_id") == parent_id)
            ):
                rel.append({
                    "document_name": r.get("document_name"),
                    "due_date": r.get("due_date"),
                    "placeholder": r.get("placeholder"),
                    "storage_key": r.get("storage_key"),
                    "metadata": r.get("metadata"),
                })
        return rel
    except Exception:
        return []

# -------- destructive operations (use with caution) ---------------------------
def _clear_document_link(property_id: str, document_group: str, document_subgroup: str, document_name: str) -> None:
    """Clear storage/link metadata for a specific document cell in the per-property schema.
    Sets storage_key to empty string, clears content_type/metadata/urls.
    """
    schema = docs_schema(property_id)
    sg = document_subgroup or ""
    upd = {
        "storage_key": "",
        "content_type": None,
        "metadata": {},
        "last_signed_url": None,
        "signed_url_expires_at": None,
    }
    try:
        sb.postgrest.schema = schema
        (sb.table("documents")
           .update(upd)
           .eq("property_id", property_id)
           .eq("document_group", document_group)
           .eq("document_subgroup", sg)
           .eq("document_name", document_name)
           .execute())
    except Exception:
        # Fallback via RPC – attempt to reuse update function with empty values
        payload = {
            "p_id": property_id,
            "g": document_group,
            "sg": sg,
            "n": document_name,
            "storage_key": "",
            "content_type": None,
            "metadata": {},
            "signed_url": "",
            "expires_at": utcnow_iso(),
        }
        try:
            sb.rpc("update_property_document_link", payload).execute()
        except Exception:
            # If server RPC isn't available, we silently continue after deleting storage
            pass


def purge_property_documents(property_id: str) -> dict:
    """Remove all uploaded files for a single property and clear their links.
    Returns a summary dict: {removed_files: int, cleared_rows: int}.
    """
    rows = list_docs(property_id)
    removed = 0
    cleared = 0
    for r in rows:
        key = r.get("storage_key")
        if key:
            try:
                sb.storage.from_(BUCKET).remove([key])
                removed += 1
            except Exception:
                # Continue clearing link even if storage removal fails
                pass
            try:
                _clear_document_link(property_id, r.get("document_group",""), r.get("document_subgroup",""), r.get("document_name",""))
                cleared += 1
            except Exception:
                pass
    return {"removed_files": removed, "cleared_rows": cleared}


def purge_all_documents() -> dict:
    """Iterate over all properties and purge their uploaded documents."""
    props = (sb.table("properties").select("id,name").execute()).data
    total_removed = 0
    total_cleared = 0
    for p in props or []:
        res = purge_property_documents(p["id"])
        total_removed += res.get("removed_files", 0)
        total_cleared += res.get("cleared_rows", 0)
    return {"properties": len(props or []), "removed_files": total_removed, "cleared_rows": total_cleared}


# -------- utilities to seed mock documents for prototyping --------------------
def seed_mock_documents(property_id: str, index_after: bool = True) -> dict:
    """Create lightweight placeholder text files for every document row without a file.
    The placeholders make it possible to prototype summary framework without real docs.
    """
    import re
    seeded = 0
    errors: List[str] = []
    rows = list_docs(property_id)
    for r in rows:
        if r.get("storage_key"):
            continue
        group = r.get("document_group", "")
        subgroup = r.get("document_subgroup", "") or ""
        name = r.get("document_name", "Documento")
        # Build a safe filename
        base = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_") or "doc"
        filename = f"mock_{base}.txt"
        content = (
            f"DOCUMENTO SIMULADO PARA PRUEBAS\n\n"
            f"Propiedad: {property_id}\nGrupo: {group}\nSubgrupo: {subgroup}\nNombre: {name}\n\n"
            "Este archivo es un placeholder generado automáticamente para permitir el prototipado del framework de resumen.\n"
        ).encode("utf-8")
        try:
            upload_and_link(property_id, content, filename, group, subgroup, name, metadata={"mock": True})
            # Optionally index for RAG
            if index_after:
                try:
                    from .rag_index import index_document
                    index_document(property_id, group, subgroup, name)
                except Exception:
                    pass
            seeded += 1
        except Exception as e:
            errors.append(f"{group}/{subgroup}/{name}: {e}")
    return {"seeded": seeded, "errors": errors}
