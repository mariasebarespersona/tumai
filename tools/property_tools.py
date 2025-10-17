from __future__ import annotations
from typing import Optional, Dict, List
from .supabase_client import sb
from .utils import docs_schema, nums_schema, sum_schema


def add_property(name: str, address: str) -> Dict:
    r = sb.table("properties").insert({"name": name, "address": address}).execute()
    prop = r.data[0]
    # The DB trigger provisions the three schemas
    return {"id": prop["id"], "name": name, "address": address}


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
        return (
            sb.table("properties")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        ).data
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
        return top

    except Exception as e:
        import logging
        logging.error(f"Error searching properties: {e}")
        return []
