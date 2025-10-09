from __future__ import annotations
import io, mimetypes, os
from typing import Dict, List, Optional, Tuple
from .supabase_client import sb, BUCKET
from .utils import docs_schema, utcnow_iso

# -------- classification proposal (simple heuristic + LLM-friendly output) -----
DOC_GROUPS = {
    "Compra": ["escritura", "registro", "arras", "impuesto", "contrato privado", "itp", "iba"],
    "Reforma:Docs diseño": ["mapas", "planos", "arquitecto", "aparejador", "licencia"],
    "Reforma:Docs obra": ["constructor", "contrato constructor"],
    "Reforma:Docs facturas": ["factura", "fontaneria", "electricista", "calefaccion", "carpinteria", "diseño"],
    "Reforma:Docs registro obra nueva": ["registro documento", "documento de impuestos"],
    "Venta": ["certificacion"],
}


def propose_slot(filename: str, text_hint: str = "") -> Dict:
    fn = filename.lower()
    best = "Compra", "", "Contrato privado"
    for key, kws in DOC_GROUPS.items():
        score = sum(1 for kw in kws if kw in fn or kw in text_hint.lower())
        if score > 0:
            parts = key.split(":")
            group = parts[0]
            subgroup = parts[1] if len(parts) > 1 else ""
            # naive doc_name guess
            doc_name = next((kw.capitalize() for kw in kws if kw in fn), "Documento")
            return {"document_group": group, "document_subgroup": subgroup, "document_name": doc_name}
    return {"document_group": best[0], "document_subgroup": best[1], "document_name": best[2]}

# -------- upload + link --------------------------------------------------------

def upload_and_link(property_id: str, file_bytes: bytes, filename: str,
                    document_group: str, document_subgroup: str, document_name: str,
                    metadata: Dict | None = None) -> Dict:
    """
    1) upload to Storage at key: property/<pid>/<group>/<filename>
    2) update the matching cell row in per-property documents table
    """
    key = f"property/{property_id}/{document_group}/{filename}"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    # Use correct file_options keys for supabase-py
    sb.storage.from_(BUCKET).upload(key, file_bytes, {"content-type": content_type, "upsert": "true"})
    signed = sb.storage.from_(BUCKET).create_signed_url(key, 3600)  # 1 hour

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
        # Preferred path when PostgREST expone el esquema
        sb.postgrest.schema = schema
        (sb.table("documents")
          .update(upd)
          .eq("property_id", property_id)
          .eq("document_group", document_group)
          .eq("document_subgroup", sg)
          .eq("document_name", document_name)
          .execute())
    except Exception:
        # Fallback via RPC when per-property schema is not exposed to PostgREST
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

    return {"storage_key": key, "signed_url": signed.get("signedURL")}


def list_docs(property_id: str) -> List[Dict]:
    """List documents rows for a property. Falls back to RPC if dynamic schema is not exposed by PostgREST."""
    schema = docs_schema(property_id)
    try:
        sb.postgrest.schema = schema
        rows = (sb.table("documents")
                .select("document_group,document_subgroup,document_name,storage_key,metadata")
                .eq("property_id", property_id)
                .order("document_group,document_subgroup,document_name")
                .execute()).data
        return rows
    except Exception:
        # Fallback through RPC function that queries the per-property schema server-side
        # Requires SQL function: public.list_property_documents(p_id uuid)
        return sb.rpc("list_property_documents", {"p_id": property_id}).execute().data


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
