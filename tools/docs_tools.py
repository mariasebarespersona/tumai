from __future__ import annotations
import io, mimetypes, os, re
from typing import Dict, List, Optional, Tuple
from .supabase_client import sb, BUCKET
from .utils import docs_schema, utcnow_iso

# -------- classification proposal (simple heuristic + LLM-friendly output) -----
DOC_GROUPS = {
    "Compra": ["escritura notarial", "escritura", "registro publico", "registro", "arras", "impuestos", "impuesto", "contrato privado", "itp", "iba", "comentario sobre impuestos"],
    "Reforma:Docs diseño": ["contrato arquitecto", "contrato aparejador", "mapas de nivel", "mapas", "planos del terreno", "planos arquitecto", "planos de la casa", "planos", "licencia obra", "licencia", "arquitecto", "aparejador"],
    "Reforma:Docs obra": ["contrato constructor", "constructor"],
    "Reforma:Docs facturas": ["factura fontaneria", "factura electricista", "factura calefaccion", "factura carpinteria", "factura diseño", "factura"],
    "Reforma:Docs registro obra nueva": ["registro documento", "documento de impuestos"],
    "Venta": ["certificacion"],
}

# Mapear keywords a nombres canónicos EXACTOS de las celdas existentes en BD
KEYWORD_TO_DOCNAME = {
    # Compra
    "escritura notarial": "Escritura notarial",
    "escritura": "Escritura notarial",
    "registro publico": "Registro publico",
    "registro": "Registro publico",
    "arras": "Arras",
    "impuestos": "Impuestos",
    "impuesto": "Impuestos",
    "contrato privado": "Contrato privado",
    "comentario sobre impuestos": "Comentario sobre impuestos ITP/IBA",
    "itp": "Comentario sobre impuestos ITP/IBA",
    "iba": "Comentario sobre impuestos ITP/IBA",
    # Reforma - Docs diseño
    "contrato arquitecto": "Contrato arquitecto",
    "contrato aparejador": "Contrato aparejador",
    "mapas de nivel": "Mapas de nivel",
    "mapas": "Mapas de nivel",
    "planos del terreno": "Planos del terreno",
    "planos arquitecto": "Planos arquitecto/de la casa",
    "planos de la casa": "Planos arquitecto/de la casa",
    "planos": "Planos arquitecto/de la casa",
    "licencia obra": "Licencia obra",
    "licencia": "Licencia obra",
    # Reforma - Docs obra
    "contrato constructor": "Contrato constructor",
    "constructor": "Contrato constructor",
    # Reforma - Docs facturas
    "factura fontaneria": "Factura fontaneria",
    "factura electricista": "Factura electricista",
    "factura calefaccion": "Factura calefaccion",
    "factura carpinteria": "Factura carpinteria",
    "factura diseño": "Factura diseño",
    "factura": "Factura diseño",
    # Reforma - Docs registro obra nueva
    "registro documento": "Registro documento",
    "documento de impuestos": "Documento de impuestos",
    # Venta
    "certificacion": "Certificacion",
}


def _normalize(text: str) -> str:
    # Lowercase and collapse non-alnum to spaces for robust keyword matches
    t = (text or "").lower()
    return re.sub(r"[^a-z0-9áéíóúüñ]+", " ", t)


def propose_slot(filename: str, text_hint: str = "") -> Dict:
    fn = _normalize(filename)
    hint = _normalize(text_hint)
    combined = fn + " " + hint
    
    # First, try to find the longest matching keyword across all groups
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
    return {"document_group": "Compra", "document_subgroup": "", "document_name": "Contrato privado"}

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

    try:
        # Preferred path cuando PostgREST expone el esquema
        sb.postgrest.schema = schema
        # Verifica que la celda objetivo exista; si no, aborta (no se crean nuevas celdas)
        existing = (sb.table("documents")
                      .select("id,storage_key,document_name")
                      .eq("property_id", property_id)
                      .eq("document_group", document_group)
                      .eq("document_subgroup", sg)
                      .eq("document_name", document_name)
                      .limit(1)
                      .execute()).data
        if not existing:
            raise ValueError(
                f"La celda no existe: {document_group} / {sg} / {document_name}."
            )

        result = (sb.table("documents")
           .update(upd)
           .eq("property_id", property_id)
           .eq("document_group", document_group)
           .eq("document_subgroup", sg)
           .eq("document_name", document_name)
           .execute())
        
        logger.info(f"✅ Database updated successfully for {document_name}")
        
    except Exception as e:
        logger.warning(f"⚠️ Direct DB update failed, trying RPC fallback: {e}")
        # Fallback via RPC when per-property schema is not exposed to PostgREST
        try:
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
        except Exception as rpc_error:
            logger.error(f"❌ RPC fallback also failed: {rpc_error}")
            raise Exception(f"Failed to update database: {rpc_error}")

    logger.info(f"🎉 Document upload complete: {filename}")
    return {"storage_key": key, "signed_url": signed.get("signedURL"), "document_name": document_name}


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
    try:
        sb.postgrest.schema = schema
        rows = (sb.table("documents")
                .select("document_group,document_subgroup,document_name,storage_key,metadata")
                .eq("property_id", property_id)
                .order("document_group,document_subgroup,document_name")
                .execute()).data
        logger.info(f"✅ Found {len(rows)} documents via direct query")
        return rows
    except Exception as e:
        logger.warning(f"⚠️ Direct query failed, trying RPC: {e}")
        # Fallback through RPC function that queries the per-property schema server-side
        # Requires SQL function: public.list_property_documents(p_id uuid)
        try:
            result = sb.rpc("list_property_documents", {"p_id": property_id}).execute().data
            logger.info(f"✅ Found {len(result)} documents via RPC")
            return result
        except Exception as rpc_error:
            logger.error(f"❌ RPC also failed: {rpc_error}")
            return []


def signed_url_for(property_id: str, document_group: str, document_subgroup: str, document_name: str, expires: int = 3600) -> str:
    schema = docs_schema(property_id)
    sg = document_subgroup or ""
    try:
        sb.postgrest.schema = schema
        rec = (sb.table("documents")
                 .select("storage_key")
                 .eq("property_id", property_id)
                 .eq("document_group", document_group)
                 .eq("document_subgroup", sg)
                 .eq("document_name", document_name).limit(1).execute()).data
        if not rec or not rec[0]["storage_key"]:
            raise ValueError("No file stored for that document cell")
        key = rec[0]["storage_key"]
    except Exception:
        # Fallback via RPC
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
    schema = docs_schema(property_id)
    sg = document_subgroup or ""
    try:
        sb.postgrest.schema = schema
        rows = (sb.table("documents")
                  .select("document_name")
                  .eq("property_id", property_id)
                  .eq("document_group", document_group)
                  .eq("document_subgroup", sg)
                  .execute()).data
        names = [r["document_name"] for r in rows]
        return {"exists": document_name in names, "candidates": names}
    except Exception:
        # Fallback via RPC that lists documents and we filter client-side
        rows = sb.rpc("list_property_documents", {"p_id": property_id}).execute().data
        names = [r["document_name"] for r in rows if r.get("document_group") == document_group and (r.get("document_subgroup") or "") == sg]
        return {"exists": document_name in names, "candidates": names}


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
