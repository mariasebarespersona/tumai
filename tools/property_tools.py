from __future__ import annotations
from typing import Optional, Dict, List
from .supabase_client import sb
from .utils import docs_schema, nums_schema, sum_schema


def add_property(name: str, address: str) -> Dict:
    """
    Create a new property and automatically initialize:
    1. Documents schema (with all R2B document cells)
    2. Numbers table framework (tables are ready, template selection happens later)
    
    CRÍTICO: Siempre inicializa ambos esquemas para que la propiedad esté lista para usar.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    r = sb.table("properties").insert({"name": name, "address": address}).execute()
    prop = r.data[0]
    property_id = prop["id"]
    
    # CRÍTICO: Inicializar esquema de documentos automáticamente
    try:
        logger.info(f"🔧 Inicializando esquema de documentos para propiedad {property_id}...")
        sb.rpc("ensure_documents_schema_v2", {"p_id": property_id}).execute()
        logger.info(f"✅ Esquema de documentos inicializado para {name}")
    except Exception as e:
        logger.error(f"❌ Error al inicializar esquema de documentos para {property_id}: {e}")
        # No fallar la creación de la propiedad, pero registrar el error
        # El esquema se puede inicializar más tarde si es necesario
    
    # CRÍTICO: Las tablas de números ya existen en el esquema público,
    # no necesitan inicialización de esquema. El usuario seleccionará la plantilla después.
    # Las tablas `numbers_templates` y `numbers_table_values` están listas para usar.
    
    return {"id": property_id, "name": name, "address": address}


def list_frameworks(property_id: str) -> Dict:
    sid = property_id.replace("-", "")[:8]
    return {
        "documents_schema": f"prop_{sid}__documents_framework",
        "numbers_schema": f"prop_{sid}__numbers_framework",
        "summary_schema": f"prop_{sid}__framework_summary_property",
    }


# ---- Verification helpers ----

def get_property(property_id: str) -> Optional[Dict]:
    rows = (sb.table("properties").select("*").eq("id", property_id).limit(1).execute()).data
    return rows[0] if rows else None


def find_property(name: str, address: str) -> Optional[Dict]:
    rows = (
        sb.table("properties")
        .select("*")
        .eq("name", name)
        .eq("address", address)
        .limit(1)
        .execute()
    ).data
    return rows[0] if rows else None


def list_properties(limit: int = 20) -> List[Dict]:
    try:
        rows = (
            sb.table("properties")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        ).data
        # Filter out soft-deleted entries (prefixed name)
        return [r for r in (rows or []) if not str(r.get("name","")) .startswith("__DELETED__ ")]
    except Exception as e:
        import logging
        logging.error(f"Error listing properties: {e}")
        return []


def search_properties(query: str, limit: int = 5) -> List[Dict]:
    """Fuzzy search by name or address (case-insensitive + typo-tolerant).

    Strategy:
    1) Direct ilike match using PostgREST
    2) Word-wise ilike match for significant tokens
    3) Client-side fuzzy scoring across recent properties (handles minor typos like 'Demos'→'Demo')
    """
    try:
        import logging, unicodedata, re
        from difflib import SequenceMatcher
        logger = logging.getLogger(__name__)

        def norm(s: str) -> str:
            s = s or ""
            s = ''.join(c for c in unicodedata.normalize('NFKD', s) if unicodedata.category(c) != 'Mn')
            s = s.lower()
            s = re.sub(r"[^a-z0-9\s]", " ", s)
            s = re.sub(r"\s+", " ", s).strip()
            return s

        query_clean = (query or "").strip()
        if not query_clean:
            return []

        # Strategy 1: Direct pattern
        pattern = f"*{query_clean}*"
        results = (
            sb.table("properties")
            .select("id,name,address")
            .or_(f"name.ilike.{pattern},address.ilike.{pattern}")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        ).data
        if results:
            results = [r for r in results if not str(r.get("name","")) .startswith("__DELETED__ ")]
            if results:
                return results

        # Strategy 2: token-based ilike
        words = query_clean.split()
        if len(words) > 1:
            skip_words = {'la', 'el', 'de', 'en', 'a', 'con', 'propiedad', 'casa', 'finca'}
            for word in words:
                if word.lower() not in skip_words and len(word) >= 3:
                    pattern = f"*{word}*"
                    results = (
                        sb.table("properties")
                        .select("id,name,address")
                        .or_(f"name.ilike.{pattern},address.ilike.{pattern}")
                        .order("created_at", desc=True)
                        .limit(limit)
                        .execute()
                    ).data
                    if results:
                        results = [r for r in results if not str(r.get("name","")) .startswith("__DELETED__ ")]
                        if results:
                            return results

        # Strategy 3: client-side fuzzy scoring
        qn = norm(query_clean)
        digits = re.findall(r"\d+", qn)
        try:
            pool = (
                sb.table("properties")
                .select("id,name,address")
                .order("created_at", desc=True)
                .limit(200)
                .execute()
            ).data
        except Exception:
            pool = list_properties(limit=200)

        def score(row: Dict) -> float:
            cand = f"{row.get('name','')} {row.get('address','')}"
            cn = norm(cand)
            base = SequenceMatcher(None, qn, cn).ratio()  # 0..1
            # token overlap bonus
            qtokens = set(qn.split())
            ctokens = set(cn.split())
            if qtokens and ctokens:
                inter = len(qtokens & ctokens)
                base += 0.1 * (inter / max(1, len(qtokens)))
            # digit bonus: if query has a number present in candidate
            if digits:
                for d in digits:
                    if d in cn:
                        base += 0.1
                        break
            return base

        scored = sorted([(score(r), r) for r in (pool or [])], key=lambda x: x[0], reverse=True)
        top = [r for (s, r) in scored if s >= 0.5][:limit]
        top = [r for r in top if not str(r.get("name","")) .startswith("__DELETED__ ")]
        return top

    except Exception as e:
        import logging
        logging.error(f"Error searching properties: {e}")
        return []


# ---- Destructive operations ----
def delete_property(property_id: str, purge_docs_first: bool = True) -> Dict:
    """Soft-delete a property by UUID (safe for limited DB privileges).

    Steps:
    - Optionally purge uploaded documents (storage + links)
    - Rename property to prefix '__DELETED__ ' to hide in listings/searches
    - Return {deleted: True}
    """
    try:
        # Purge files first (best-effort)
        if purge_docs_first:
            try:
                from .docs_tools import purge_property_documents
                purge_property_documents(property_id)
            except Exception:
                pass

        # Fetch current name for traceability
        row = (
            sb.table("properties").select("id,name,address").eq("id", property_id).limit(1).execute()
        ).data
        cur_name = (row[0]["name"] if row else "") or "(sin nombre)"
        # Prefix the name to mark as deleted; keep id hint
        new_name = f"__DELETED__ {cur_name}"
        try:
            sb.table("properties").update({"name": new_name}).eq("id", property_id).execute()
        except Exception as e:
            # If update fails, fallback to hard delete (may fail due to schema owner)
            try:
                sb.table("properties").delete().eq("id", property_id).execute()
            except Exception as e2:
                import logging
                logging.error(f"Error deleting property {property_id}: {e2}")
                return {"deleted": False, "error": str(e2)}
        return {"deleted": True}
    except Exception as e:
        import logging
        logging.error(f"Error soft-deleting property {property_id}: {e}")
        return {"deleted": False, "error": str(e)}


def delete_properties(property_ids: List[str], purge_docs_first: bool = True) -> Dict:
    """Delete multiple properties (soft-delete) in sequence and return a per-id result.

    This function is resilient: it attempts all deletions and reports individual outcomes.
    It reuses delete_property for each id.
    Returns: {"results": [{"property_id": id, "deleted": bool, "error": optional}],
              "num_deleted": int}
    """
    results: List[Dict] = []
    num_deleted = 0
    for pid in (property_ids or []):
        try:
            out = delete_property(pid, purge_docs_first=purge_docs_first)
            ok = bool(out.get("deleted"))
            if ok:
                num_deleted += 1
            results.append({"property_id": pid, "deleted": ok, **({"error": out.get("error")} if out.get("error") else {})})
        except Exception as e:
            results.append({"property_id": pid, "deleted": False, "error": str(e)})
    return {"results": results, "num_deleted": num_deleted}
