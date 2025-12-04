from __future__ import annotations
import io, mimetypes, os, re, datetime as dt
from typing import Dict, List, Optional, Tuple
from .supabase_client import sb, BUCKET
from .utils import docs_schema, utcnow_iso
from difflib import SequenceMatcher

# -------- Fuzzy Matching Helper --------
def _fuzzy_match_keywords(text: str, min_similarity: float = 0.7) -> Optional[Tuple[str, str, str]]:
    """
    Advanced fuzzy matching to find the best matching document group.
    
    Returns: (keyword, group, subgroup) or None if no match above threshold
    """
    import logging
    logger = logging.getLogger(__name__)
    
    text_lower = text.lower()
    best_match = None
    best_score = 0.0
    
    # Build a flat list of all (keyword, group, subgroup) tuples
    all_keywords = []
    for key, kws in DOC_GROUPS.items():
        parts = key.split(":")
        group = parts[0]
        subgroup = parts[1] if len(parts) > 1 else ""
        for kw in kws:
            all_keywords.append((kw, group, subgroup))
    
    # Try exact substring match first (highest priority)
    for kw, group, subgroup in all_keywords:
        if kw in text_lower:
            logger.info(f"🎯 [fuzzy_match] EXACT match: '{kw}' in '{text}' → {group}:{subgroup}")
            return (kw, group, subgroup)
    
    # Try fuzzy matching with SequenceMatcher
    for kw, group, subgroup in all_keywords:
        # Compare filename with keyword
        similarity = SequenceMatcher(None, text_lower, kw).ratio()
        
        # Also compare each word in filename with keyword
        words = text_lower.split()
        for word in words:
            word_similarity = SequenceMatcher(None, word, kw).ratio()
            similarity = max(similarity, word_similarity)
        
        if similarity > best_score:
            best_score = similarity
            best_match = (kw, group, subgroup)
    
    if best_score >= min_similarity:
        logger.info(f"🔍 [fuzzy_match] FUZZY match: '{text}' → '{best_match[0]}' (score: {best_score:.2f}) → {best_match[1]}:{best_match[2]}")
        return best_match
    
    logger.warning(f"⚠️ [fuzzy_match] No match found for '{text}' (best score: {best_score:.2f}, threshold: {min_similarity})")
    return None


# -------- RAG-based Document Classification --------
def _rag_classify_document(file_bytes: bytes, filename: str) -> Optional[Tuple[str, str, str]]:
    """
    Use RAG to read the document content and classify it based on keywords.
    
    Returns: (keyword, group, subgroup) or None if RAG fails or no match
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Only try RAG for PDFs
        if not filename.lower().endswith('.pdf'):
            logger.debug(f"[rag_classify] Skipping non-PDF file: {filename}")
            return None
        
        # Extract text from PDF
        try:
            from pypdf import PdfReader
            pdf_reader = PdfReader(io.BytesIO(file_bytes))
            text = ""
            # Read first 3 pages only (for performance)
            for page in pdf_reader.pages[:3]:
                text += page.extract_text() or ""
            text = text.lower()[:2000]  # Limit to 2000 chars
            
            if len(text) < 20:
                logger.debug(f"[rag_classify] Not enough text extracted from {filename}")
                return None
            
            logger.info(f"📖 [rag_classify] Extracted {len(text)} chars from {filename}")
            
            # Search for keywords in extracted text
            all_keywords = []
            for key, kws in DOC_GROUPS.items():
                parts = key.split(":")
                group = parts[0]
                subgroup = parts[1] if len(parts) > 1 else ""
                for kw in kws:
                    all_keywords.append((kw, group, subgroup))
            
            # Sort by keyword length (longer = more specific)
            all_keywords.sort(key=lambda x: -len(x[0]))
            
            # Find best match
            for kw, group, subgroup in all_keywords:
                if kw in text:
                    logger.info(f"✅ [rag_classify] Found '{kw}' in document content → {group}:{subgroup}")
                    return (kw, group, subgroup)
            
            logger.warning(f"⚠️ [rag_classify] No keywords found in document content")
            return None
            
        except ImportError:
            logger.warning("[rag_classify] pypdf not installed, skipping RAG classification")
            return None
        except Exception as e:
            logger.error(f"❌ [rag_classify] Failed to extract text: {e}")
            return None
    
    except Exception as e:
        logger.error(f"❌ [rag_classify] Unexpected error: {e}")
        return None


# -------- classification proposal (simple heuristic + LLM-friendly output) -----
# NEW TAXONOMY ALIGNED WITH V4 (Visual Flowchart)
# 1. COMPRA (Mandatory)
# 2. Strategy Decision: R2B vs PROMOCION
# 3. If R2B: 
#    - Docs diseño + facturas (Mandatory)
#    - Sub-decision: Venta R2B vs Venta R2B + PM

DOC_GROUPS = {
    # 1. COMPRA (Compulsory)
    "COMPRA:": [
        "catastro", "nota simple", "acuerdo compraventa", "señal", "arras", "due diligence compra",
        "escritura notarial de compraventa", "notaria factura", "impuestos de compra", "registro de la propiedad"
    ],
    
    # 2. R2B -> 1. Docs diseño + facturas (Common for R2B)
    "R2B:Diseño": [
        "mapas nivel", "contrato arquitecto", "proyecto basico", "mediciones", "planos",
        "contrato aparejador", "licencia de obra", "acometidas", "contrato constructor"
    ],
    
    # 2. R2B -> 2.1 Venta R2B (subgroup name must match migration SQL: "Venta")
    "R2B:Venta": [
        "due diligence de venta", "arras venta", "venta terreno", "venta proyecto",
        "escritura compraventa", "impuestos de venta"
    ],
    
    # 2. R2B -> 2.2 Venta R2B + PM
    "R2B:Venta + PM": [
        "planificacion obra", "cronograma", "contrato obra", "facturas", "contrato raquel", "pm"
    ],
    
    # 3. PROMOCION (Alternative to R2B)
    "Promoción:Obra": [
        "planificacion obra", "cronograma", "contrato obra", "facturas", "oct", "seguro decenal",
        "libro del edificio", "escritura obra nueva"
    ],
    "Promoción:Venta": [
        "contrato arras venta", "registro obra nueva", "escritura compraventa", "impuestos de venta"
    ]
}

# Map keywords to canonical document names (exact cell names in DB)
KEYWORD_TO_DOCNAME = {
    # 1. COMPRA
    "catastro": "Catastro y la nota simple",
    "nota simple": "Catastro y la nota simple",
    "acuerdo compraventa": "Acuerdo compraventa (verbal)",
    "señal": "Señal / Arras",
    "arras": "Señal / Arras",
    "due diligence compra": "Due Diligence (DD) compra",
    "escritura notarial de compraventa": "Escritura notarial de compraventa",
    "notaria factura": "Notaria factura",
    "impuestos de compra": "Impuestos de compra (ITP/IVA/Actos jurídicos)",
    "registro de la propiedad": "Registro de la propiedad",

    # 2. R2B - Diseño
    "mapas nivel": "Mapas Nivel + facturas",
    "contrato arquitecto": "Contrato arquitecto + facturas arquitecto",
    "proyecto basico": "Projecto basico/ mediciones/planos",
    "mediciones": "Projecto basico/ mediciones/planos",
    "planos": "Projecto basico/ mediciones/planos",
    "contrato aparejador": "Contrato Aparejador + facturas",
    "licencia de obra": "Licencia de obra y acometidas + facturas",
    "acometidas": "Licencia de obra y acometidas + facturas",
    "contrato constructor": "Contrato constructor + facturas",

    # 2.1 R2B - Venta Simple (Renamed key in DOC_GROUPS for clarity)
    "due diligence de venta": "Due Diligence (DD) de venta",
    "arras venta": "Arras venta",
    "venta terreno": "Venta terreno",
    "venta proyecto": "Venta projecto",
    "escritura compraventa": "Escritura compraventa",
    "impuestos de venta": "Impuestos de venta",

    # 2.2 R2B - Venta + PM
    "planificacion obra": "Planificacion obra (cronograma)",
    "cronograma": "Planificacion obra (cronograma)",
    "contrato obra": "Contrato obra",
    "facturas": "Facturas (multiples documentos)",
    "contrato raquel": "Contrato Raquel como PM",
    "pm": "Contrato Raquel como PM",

    # 3. Promoción - Obra
    "oct": "OCT",
    "seguro decenal": "Seguro decenal",
    "libro del edificio": "Libro del edificio",
    "escritura obra nueva": "Escritura obra nueva",
    
    # 3. Promoción - Venta
    "contrato arras venta": "Contrato arras venta",
    "registro obra nueva": "Registro obra nueva",
}

# Docs that should spawn factura placeholders when uploaded
# Key: (Group, Subgroup, Name)
FACTURABLE_DOCS = {
    ("R2B", "Diseño", "Mapas Nivel + facturas"): "Facturas mapas nivel",
    ("R2B", "Diseño", "Contrato arquitecto + facturas arquitecto"): "Facturas arquitecto",
    ("R2B", "Diseño", "Projecto basico/ mediciones/planos"): "Facturas proyecto/planos",
    ("R2B", "Diseño", "Contrato Aparejador + facturas"): "Facturas aparejador",
    ("R2B", "Diseño", "Licencia de obra y acometidas + facturas"): "Facturas licencia y acometidas",
    ("R2B", "Diseño", "Contrato constructor + facturas"): "Facturas constructor",
    ("R2B", "Venta + PM", "Facturas (multiples documentos)"): "Facturas obra R2B",
    ("Promoción", "Obra", "Facturas (multiples documentos)"): "Facturas obra Promoción",
}

def _normalize(text: str) -> str:
    t = (text or "").lower()
    return re.sub(r"[^a-z0-9áéíóúüñ]+", " ", t)

def propose_slot(filename: str, text_hint: str = "", property_id: str = "", file_bytes: Optional[bytes] = None) -> Dict:
    import logging
    logger = logging.getLogger(__name__)
    
    date_match = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})|(\d{1,2}[-/]\d{1,2}[-/]\d{4})", filename)
    extracted_date = date_match.group(0).replace("/", "-") if date_match else None
    
    fn = _normalize(filename)
    hint = _normalize(text_hint)
    combined = fn + " " + hint
    
    is_factura = "factura" in combined or "invoice" in combined
    
    if is_factura and property_id:
        try:
            all_docs = list_docs(property_id)
            if extracted_date:
                for doc in all_docs:
                    if (doc.get("document_kind") == "factura" 
                        and doc.get("placeholder") 
                        and doc.get("due_date")):
                        doc_name = doc.get("document_name", "")
                        if extracted_date in doc_name:
                            return {
                                "document_group": doc.get("document_group"),
                                "document_subgroup": doc.get("document_subgroup") or "",
                                "document_name": doc_name,
                                "is_placeholder_replacement": True
                            }
            
            for parent_key, factura_title in FACTURABLE_DOCS.items():
                parent_name = parent_key[2].lower()
                if parent_name.split()[0] in combined:
                    for doc in all_docs:
                        if (doc.get("document_kind") == "factura"
                            and doc.get("placeholder")
                            and factura_title.lower() in doc.get("document_name", "").lower()
                            and not doc.get("storage_key")):
                            return {
                                "document_group": doc.get("document_group"),
                                "document_subgroup": doc.get("document_subgroup") or "",
                                "document_name": doc.get("document_name"),
                                "is_placeholder_replacement": True
                            }
        except Exception:
            pass
    
    # STEP 1: Try exact keyword matching (original logic)
    all_keywords = []
    for key, kws in DOC_GROUPS.items():
        for kw in kws:
            parts = key.split(":")
            group = parts[0]
            subgroup = parts[1] if len(parts) > 1 else ""
            all_keywords.append((kw, group, subgroup))
    
    all_keywords.sort(key=lambda x: -len(x[0]))
    
    for kw, group, subgroup in all_keywords:
        if kw in combined:
            doc_name = KEYWORD_TO_DOCNAME.get(kw, kw.title())
            logger.info(f"✅ [propose_slot] EXACT match: '{kw}' → {group}:{subgroup}")
            return {"document_group": group, "document_subgroup": subgroup, "document_name": doc_name}
    
    # STEP 2: Try fuzzy matching on filename
    logger.info(f"🔍 [propose_slot] No exact match, trying fuzzy matching for: {filename}")
    fuzzy_result = _fuzzy_match_keywords(combined, min_similarity=0.65)
    if fuzzy_result:
        kw, group, subgroup = fuzzy_result
        doc_name = KEYWORD_TO_DOCNAME.get(kw, kw.title())
        logger.info(f"✅ [propose_slot] FUZZY match: '{filename}' → {group}:{subgroup} (via keyword '{kw}')")
        return {"document_group": group, "document_subgroup": subgroup, "document_name": doc_name}
    
    # STEP 3: Try RAG to read document content (if file bytes available)
    if file_bytes:
        logger.info(f"📖 [propose_slot] Trying RAG classification for: {filename}")
        rag_result = _rag_classify_document(file_bytes, filename)
        if rag_result:
            kw, group, subgroup = rag_result
            doc_name = KEYWORD_TO_DOCNAME.get(kw, kw.title())
            logger.info(f"✅ [propose_slot] RAG match: '{filename}' → {group}:{subgroup} (found keyword '{kw}' in content)")
            return {"document_group": group, "document_subgroup": subgroup, "document_name": doc_name}
        logger.warning(f"⚠️ [propose_slot] RAG classification failed for: {filename}")
    else:
        logger.debug(f"⚠️ [propose_slot] No file_bytes provided, skipping RAG classification")
    
    logger.warning(f"⚠️ [propose_slot] All classification methods failed for: {filename}")
    logger.warning(f"   Available groups: {list(DOC_GROUPS.keys())}")
    
    # STEP 4: Last resort - ask the agent to clarify with the user
    return {
        "error": "Could not determine document category",
        "message": f"No pude identificar a qué categoría pertenece '{filename}'. Las categorías disponibles son: COMPRA (obligatorio), R2B (Diseño, Venta, Venta+PM), o Promoción (Obra, Venta). ¿Puedes decirme a cuál pertenece?",
        "available_groups": list(DOC_GROUPS.keys()),
        "suggestion": "Intenta usar palabras clave como: contrato, factura, plano, escritura, licencia, etc.",
        "document_group": None,  # Force agent to handle error
        "document_subgroup": None,
        "document_name": None
    }

def upload_and_link(property_id: str, file_bytes: bytes, filename: str,
                    document_group: str, document_subgroup: str, document_name: str,
                    metadata: Dict | None = None) -> Dict:
    import logging
    logger = logging.getLogger(__name__)
    
    key = f"property/{property_id}/{document_group}/{filename}"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    
    sb.storage.from_(BUCKET).upload(key, file_bytes, {"content-type": content_type, "upsert": "true"})
    signed = sb.storage.from_(BUCKET).create_signed_url(key, 3600)
    
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

    existing = []
    try:
        all_docs = sb.rpc("list_property_documents", {"p_id": property_id}).execute().data or []
        existing = [
            d for d in all_docs
            if d.get("document_group") == document_group
            and (d.get("document_subgroup") or "") == sg
            and d.get("document_name") == document_name
        ]
        if not existing:
            # Logic for auto-seeding with V3 structure
            try:
                logger.info(f"⚠️ Cell not found, initializing V3 schema for {property_id}")
                sb.rpc("ensure_documents_schema_v2", {"p_id": property_id}).execute()
                sb.rpc("seed_documents_v3", {"p_id": property_id}).execute()
                logger.info("✅ V3 schema initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize V3 schema: {e}")
                pass
        
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
        
    except Exception as e:
        raise Exception(f"Failed to update database: {e}")

    facturas_info = {}
    try:
        facturas_info = _maybe_generate_facturas(property_id, document_group, sg, document_name, existing[0]["id"] if existing else None)
    except Exception:
        pass

    result = {"storage_key": key, "signed_url": signed.get("signedURL"), "document_name": document_name}
    if facturas_info:
        result["facturas_generated"] = facturas_info
    return result

def _month_sequence(start_date: dt.date, count: int, day_of_month: int, step: int = 1) -> List[dt.date]:
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
    key = (group, subgroup or "", name)
    if key not in FACTURABLE_DOCS:
        return {"status": "not_facturable"}

    try:
        from .rag_tool import qa_payment_schedule
    except Exception:
        return {"status": "rag_unavailable"}

    info = qa_payment_schedule(property_id, group, subgroup, name)
    extracted = info.get("extracted", {}) if isinstance(info, dict) else {}
    frequency = extracted.get("frequency")
    day_of_month = extracted.get("day_of_month")
    total_payments = extracted.get("total_payments")
    contract_years = extracted.get("contract_years")
    
    if (not day_of_month) and info.get("next_due_date"):
        try:
            dom = int(str(info.get("next_due_date")).split("-")[-1])
            if 1 <= dom <= 28:
                day_of_month = dom
                frequency = frequency or "monthly"
        except Exception:
            pass
    
    if not frequency or not day_of_month:
        return {"status": "rag_failed", "info": info}
    
    if total_payments:
        count = int(total_payments)
    elif frequency == "yearly":
        count = contract_years if contract_years else 1
    elif frequency == "quarterly":
        count = (contract_years * 4) if contract_years else 4
    elif frequency == "monthly":
        count = (contract_years * 12) if contract_years else 12
    elif frequency == "every_15_days":
        count = (contract_years * 24) if contract_years else 24
    else:
        count = 12
    
    count = min(count, 36)
    start = dt.date.today()
    
    if frequency == "monthly":
        seq = _month_sequence(start, count, int(day_of_month))
    elif frequency == "quarterly":
        seq = _month_sequence(start, count, int(day_of_month), step=3)
    elif frequency == "yearly":
        seq = _month_sequence(start, count, int(day_of_month), step=12)
    else:
        seq = _month_sequence(start, count, int(day_of_month))

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
            pass
    return {"status": "created", "count": created, "day": int(day_of_month), "frequency": frequency}

def seed_facturas_for(property_id: str, document_group: str, document_subgroup: str, document_name: str,
                      day_of_month: int, months: int = 12, start_date: Optional[str] = None) -> Dict:
    sg = document_subgroup or ""
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
            pass
    return {"created": created}

def list_docs(property_id: str) -> List[Dict]:
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        sb.postgrest.schema = "public"
        result = sb.rpc("list_property_documents", {"p_id": property_id}).execute().data
        
        # Return full structure - optimization was breaking other parts of the code
        # that expect document_group, document_subgroup, document_name keys
        return result or []
    except Exception as rpc_error:
        logger.error(f"❌ RPC failed: {rpc_error}")
        return []

def signed_url_for(property_id: str, document_group: str, document_subgroup: str, document_name: str, expires: int = 31536000) -> str:
    import logging
    logger = logging.getLogger(__name__)
    
    sg = document_subgroup or ""
    
    # Try exact match first
    key = sb.rpc(
        "get_property_document_storage_key",
        {"p_id": property_id, "g": document_group, "sg": sg, "n": document_name}
    ).execute().data
    
    if key:
        return sb.storage.from_(BUCKET).create_signed_url(key, expires)["signedURL"]
    
    # If exact match fails, try fuzzy matching on all documents in this group/subgroup
    logger.info(f"[signed_url_for] Exact match failed for '{document_name}', trying fuzzy match...")
    all_rows = sb.rpc("list_property_documents", {"p_id": property_id}).execute().data or []
    
    # First, filter documents in the same group/subgroup that have a file
    candidates = [
        r for r in all_rows
        if r.get("document_group") == document_group
        and (r.get("document_subgroup") or "") == sg
        and (r.get("storage_key") or r.get("file_storage_key"))  # Only documents with uploaded files
    ]
    
    # If no candidates in the exact subgroup, expand search to the entire group
    if not candidates:
        logger.info(f"[signed_url_for] No documents in {document_group}/{sg}, expanding search to entire {document_group} group...")
        # Debug: log all documents in this property
        logger.info(f"[signed_url_for] DEBUG: Total documents in property: {len(all_rows)}")
        for r in all_rows:
            has_file = bool(r.get("storage_key") or r.get("file_storage_key"))
            # Verbose debug logging disabled - causes log bloat with 60+ documents
            # logger.debug(f"[signed_url_for] doc='{r.get('document_name')}', group={r.get('document_group')}, subgroup='{r.get('document_subgroup')}', has_file={has_file}")
        
        candidates = [
            r for r in all_rows
            if r.get("document_group") == document_group
            and (r.get("storage_key") or r.get("file_storage_key"))  # Only documents with uploaded files (ignore subgroup)
        ]
        logger.info(f"[signed_url_for] DEBUG: Found {len(candidates)} candidates in {document_group} group")
    
    # Check if any candidate contains the requested name (fuzzy match)
    # e.g., "Contrato arquitecto" matches "Contrato arquitecto + facturas arquitecto"
    normalized_request = document_name.lower().strip()
    for candidate in candidates:
        candidate_name = candidate.get("document_name", "").lower().strip()
        if normalized_request in candidate_name or candidate_name in normalized_request:
            matched_name = candidate.get("document_name")
            matched_subgroup = candidate.get("document_subgroup") or ""
            logger.info(f"[signed_url_for] ✅ Fuzzy match: '{document_name}' → '{matched_name}' (subgroup: '{matched_subgroup}')")
            # Now get the signed URL for the matched document using the CORRECT subgroup from the candidate
            key = sb.rpc(
                "get_property_document_storage_key",
                {"p_id": property_id, "g": document_group, "sg": matched_subgroup, "n": matched_name}
            ).execute().data
            if key:
                return sb.storage.from_(BUCKET).create_signed_url(key, expires)["signedURL"]
    
    # If no fuzzy match found, raise error
    candidate_names = [c.get("document_name") for c in candidates]
    logger.error(f"[signed_url_for] ❌ No match for '{document_name}' in {document_group}/{sg}. Candidates: {candidate_names}")
    raise ValueError(f"No file stored for '{document_name}'. Available: {', '.join(candidate_names) if candidate_names else 'none'}")

def slot_exists(property_id: str, document_group: str, document_subgroup: str, document_name: str) -> Dict:
    sg = document_subgroup or ""
    rows = sb.rpc("list_property_documents", {"p_id": property_id}).execute().data or []
    names = [r["document_name"] for r in rows if r.get("document_group") == document_group and (r.get("document_subgroup") or "") == sg]
    return {"exists": document_name in names, "candidates": names}

def list_related_facturas(property_id: str, document_group: str, document_subgroup: str, document_name: str) -> List[Dict]:
    sg = document_subgroup or ""
    try:
        sb.postgrest.schema = "public"
        all_rows = sb.rpc("list_property_documents", {"p_id": property_id}).execute().data or []
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

def purge_property_documents(property_id: str) -> dict:
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
                pass
            try:
                payload = {
                    "p_id": property_id,
                    "g": r.get("document_group"),
                    "sg": r.get("document_subgroup") or "",
                    "n": r.get("document_name"),
                    "storage_key": None,  # Use None to store NULL in DB
                    "content_type": None,
                    "metadata": {},
                    "signed_url": None,
                    "expires_at": None,
                }
                sb.rpc("update_property_document_link", payload).execute()
                cleared += 1
            except Exception:
                pass
    return {"removed_files": removed, "cleared_rows": cleared}

def purge_all_documents() -> dict:
    props = (sb.table("properties").select("id,name").execute()).data
    total_removed = 0
    total_cleared = 0
    for p in props or []:
        res = purge_property_documents(p["id"])
        total_removed += res.get("removed_files", 0)
        total_cleared += res.get("cleared_rows", 0)
    return {"properties": len(props or []), "removed_files": total_removed, "cleared_rows": total_cleared}

def seed_mock_documents(property_id: str, index_after: bool = True) -> dict:
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
        base = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_") or "doc"
        filename = f"mock_{base}.txt"
        content = (
            f"DOCUMENTO SIMULADO PARA PRUEBAS\n\n"
            f"Propiedad: {property_id}\nGrupo: {group}\nSubgrupo: {subgroup}\nNombre: {name}\n\n"
            "Este archivo es un placeholder generado automáticamente para permitir el prototipado del framework de resumen.\n"
        ).encode("utf-8")
        try:
            upload_and_link(property_id, content, filename, group, subgroup, name, metadata={"mock": True})
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

# NEW TOOL for Strategy Management
def set_property_strategy(property_id: str, strategy: str) -> str:
    """Set the management strategy for a property (R2B, PROMOCION, R2B_VENTA, R2B_PM).
    This unlocks the corresponding document sections.
    """
    valid_strategies = ["R2B", "PROMOCION", "R2B_VENTA", "R2B_PM"]
    if strategy not in valid_strategies:
        return f"Error: Invalid strategy. Must be one of {valid_strategies}"
    
    try:
        sb.rpc("set_property_strategy", {"p_id": property_id, "new_strategy": strategy}).execute()
        return f"Success: Property strategy set to {strategy}"
    except Exception as e:
        return f"Error setting strategy: {e}"

def get_property_strategy(property_id: str) -> str:
    try:
        res = sb.rpc("get_property_strategy", {"p_id": property_id}).execute()
        return res.data or "PENDING"
    except Exception:
        return "UNKNOWN"


def delete_document(property_id: str, document_name: str, document_group: str = "", document_subgroup: str = "", confirmed: bool = False) -> Dict:
    """
    Delete a document from a SPECIFIC property.
    
    CRITICAL: This only deletes the document from the specified property_id.
    It does NOT affect documents in other properties.
    
    TWO-STEP PROCESS:
    1. First call WITHOUT confirmed=True: Returns document details for user confirmation
    2. Second call WITH confirmed=True + exact group/subgroup: Executes deletion
    
    Args:
        property_id: UUID of the property (REQUIRED - ensures we only delete from THIS property)
        document_name: Name of the document to delete (can be partial for fuzzy matching)
        document_group: Optional - filter by group (COMPRA, R2B, Promoción). REQUIRED for confirmed=True
        document_subgroup: Optional - filter by subgroup (Diseño, Venta, etc.)
        confirmed: If True, execute deletion. If False, return document details for confirmation.
    
    Returns:
        - If confirmed=False: {"needs_confirmation": True, "document": {...}, "message": "..."}
        - If confirmed=True: {"success": True, "deleted_document": "...", ...}
        - On error: {"success": False, "error": "..."}
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not property_id:
        return {"success": False, "error": "property_id is required to delete a document"}
    
    logger.info(f"🗑️ [delete_document] Searching for '{document_name}' in property {property_id}")
    
    # Get all documents for this property
    all_docs = list_docs(property_id)
    if not all_docs:
        return {"success": False, "error": f"No documents found for property {property_id}"}
    
    # Find matching document(s) - fuzzy match on name
    # CRITICAL: Prioritize documents with storage_key (actually uploaded files)
    normalized_search = document_name.lower().strip()
    matches = []
    fuzzy_matches = []  # Store (doc, similarity_score) for fuzzy matching
    
    for doc in all_docs:
        doc_name = doc.get("document_name", "").lower().strip()
        doc_group = doc.get("document_group", "")
        doc_subgroup = doc.get("document_subgroup", "") or ""
        has_file = bool(doc.get("storage_key") or doc.get("file_storage_key"))
        
        # If group/subgroup filters provided, check them too
        group_matches = not document_group or doc_group.lower() == document_group.lower()
        subgroup_matches = not document_subgroup or doc_subgroup.lower() == document_subgroup.lower()
        
        if not (group_matches and subgroup_matches):
            continue
        
        # Check for exact or partial substring match first
        if normalized_search in doc_name or doc_name in normalized_search:
            matches.append((doc, has_file))
            continue
        
        # Fuzzy matching using SequenceMatcher
        # "impuesto de venta" vs "impuestos de venta" should match
        similarity = SequenceMatcher(None, normalized_search, doc_name).ratio()
        
        # Also check word-by-word similarity (helps with singular/plural)
        search_words = set(normalized_search.split())
        doc_words = set(doc_name.split())
        common_words = search_words & doc_words
        word_overlap = len(common_words) / max(len(search_words), 1)
        
        # Combined score: similarity + word overlap bonus
        combined_score = similarity + (word_overlap * 0.3)
        
        if combined_score >= 0.75:  # Threshold for fuzzy match
            fuzzy_matches.append((doc, combined_score, has_file))
            logger.info(f"🔍 [delete_document] Fuzzy match: '{normalized_search}' ~ '{doc_name}' (score: {combined_score:.2f}, has_file: {has_file})")
    
    # If no exact matches, use fuzzy matches
    if not matches and fuzzy_matches:
        # Sort by: 1) has_file (True first), 2) score (highest first)
        fuzzy_matches.sort(key=lambda x: (x[2], x[1]), reverse=True)
        best_match = fuzzy_matches[0]
        matches.append((best_match[0], best_match[2]))
        logger.info(f"✅ [delete_document] Using best fuzzy match: {best_match[0].get('document_name')} (score: {best_match[1]:.2f}, has_file: {best_match[2]})")
    
    # CRITICAL: Prioritize documents with files over empty placeholders
    # Sort matches: documents with storage_key first
    if matches:
        matches.sort(key=lambda x: x[1], reverse=True)  # has_file=True first
        # Extract just the docs
        matches = [m[0] for m in matches]
    
    if not matches:
        # List available documents to help user
        available = [d.get("document_name") for d in all_docs if d.get("storage_key")]
        return {
            "success": False, 
            "error": f"No document matching '{document_name}' found in this property",
            "available_documents": available[:10]  # Show first 10
        }
    
    if len(matches) > 1:
        # Multiple matches - show all options for user to choose
        match_info = []
        for m in matches:
            has_file = bool(m.get("storage_key") or m.get("file_storage_key"))
            match_info.append({
                "document_name": m.get("document_name"),
                "document_group": m.get("document_group"),
                "document_subgroup": m.get("document_subgroup") or "",
                "has_file": has_file,
                "display": f"{m.get('document_group')}/{m.get('document_subgroup') or ''}{'/' if m.get('document_subgroup') else ''}{m.get('document_name')} {'✅' if has_file else '⏳'}"
            })
        return {
            "success": False,
            "needs_selection": True,
            "error": f"Encontré {len(matches)} documentos que coinciden con '{document_name}':",
            "matches": match_info,
            "message": "Por favor, especifica cuál quieres eliminar indicando el grupo (ej: 'R2B/Venta/Impuestos de venta')."
        }
    
    # Single match found
    doc_to_delete = matches[0]
    doc_id = doc_to_delete.get("id")
    storage_key = doc_to_delete.get("storage_key") or doc_to_delete.get("file_storage_key")
    full_name = doc_to_delete.get("document_name")
    group = doc_to_delete.get("document_group")
    subgroup = doc_to_delete.get("document_subgroup") or ""
    has_file = bool(storage_key)
    
    # Build display path for confirmation
    display_path = f"{group}"
    if subgroup:
        display_path += f" → {subgroup}"
    display_path += f" → {full_name}"
    
    logger.info(f"🗑️ [delete_document] Found document: {full_name} in {group}/{subgroup} (has_file={has_file}, confirmed={confirmed})")
    
    # ============================================================
    # STEP 1: If not confirmed, return details for user confirmation
    # ============================================================
    if not confirmed:
        return {
            "success": True,
            "needs_confirmation": True,
            "document": {
                "document_name": full_name,
                "document_group": group,
                "document_subgroup": subgroup,
                "has_file": has_file,
                "display_path": display_path
            },
            "message": f"¿Confirmas que quieres eliminar el documento '{full_name}' del grupo **{display_path}**? {'(Tiene archivo subido ✅)' if has_file else '(Sin archivo ⏳)'}",
            "instruction": "Para confirmar, llama delete_document con confirmed=True y los mismos parámetros."
        }
    
    # ============================================================
    # STEP 2: Confirmed - proceed with deletion
    # ============================================================
    
    # Warn if trying to delete a document without a file
    if not storage_key:
        logger.warning(f"⚠️ [delete_document] Document '{full_name}' has no file (storage_key=None). Nothing to delete from storage.")
    
    # Delete from storage if file exists
    if storage_key:
        try:
            sb.storage.from_(BUCKET).remove([storage_key])
            logger.info(f"✅ [delete_document] Removed file from storage: {storage_key}")
        except Exception as e:
            logger.warning(f"⚠️ [delete_document] Could not remove file from storage: {e}")
    
    # Clear the document link (set storage_key to NULL, keep the schema cell)
    try:
        payload = {
            "p_id": property_id,
            "g": group,
            "sg": subgroup,
            "n": full_name,
            "storage_key": None,
            "content_type": None,
            "metadata": {},
            "signed_url": None,
            "expires_at": None,
        }
        sb.rpc("update_property_document_link", payload).execute()
        logger.info(f"✅ [delete_document] Cleared document link in database (storage_key=NULL)")
    except Exception as e:
        logger.error(f"❌ [delete_document] Failed to clear document link: {e}")
        return {"success": False, "error": f"Failed to update database: {e}"}
    
    return {
        "success": True,
        "deleted_document": full_name,
        "document_group": group,
        "document_subgroup": subgroup,
        "property_id": property_id,
        "message": f"✅ Documento '{full_name}' eliminado correctamente del grupo {display_path}."
    }
