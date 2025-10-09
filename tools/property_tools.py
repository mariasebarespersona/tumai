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
    return (
        sb.table("properties")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    ).data


def search_properties(query: str, limit: int = 5) -> List[Dict]:
    """Fuzzy search by name or address (case-insensitive)."""
    # Supabase PostgREST or() syntax with ilike wildcards
    pattern = f"*{query}*"
    return (
        sb.table("properties")
        .select("id,name,address")
        .or_(f"name.ilike.{pattern},address.ilike.{pattern}")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    ).data
