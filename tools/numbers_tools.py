from __future__ import annotations
from typing import Dict, List
from .supabase_client import sb
from .utils import nums_schema

def set_number(property_id: str, item_key: str, amount: float) -> Dict:
    schema = nums_schema(property_id)
    sb.postgrest.schema = schema
    (sb.table("line_items")
      .update({"amount": amount})
      .eq("property_id", property_id)
      .eq("item_key", item_key)
      .execute())
    return {"item_key": item_key, "amount": amount}

def get_numbers(property_id: str) -> List[Dict]:
    schema = nums_schema(property_id)
    sb.postgrest.schema = schema
    return (sb.table("line_items")
             .select("group_name,item_key,item_label,is_percent,amount,updated_at")
             .eq("property_id", property_id)
             .execute()).data

def calc_numbers(property_id: str) -> List[Dict]:
    schema = nums_schema(property_id)
    sb.postgrest.schema = schema
    # call the schema-local function
    return sb.rpc(f"{schema}.calc").execute().data  # PostgREST allows schema-qualified RPC
