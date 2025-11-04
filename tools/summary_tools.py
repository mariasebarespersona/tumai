from __future__ import annotations
from typing import Dict, List, Optional, Any, Tuple
from .supabase_client import sb
from .utils import nums_schema, docs_schema, sum_schema

def get_summary_spec(property_id: str) -> List[Dict]:
    schema = sum_schema(property_id)
    sb.postgrest.schema = schema
    return (sb.table("summary_spec").select("*")
            .eq("property_id", property_id).execute()).data

def upsert_summary_value(property_id: str, item_key: str, amount: float, provenance: Dict) -> Dict:
    schema = sum_schema(property_id)
    sb.postgrest.schema = schema
    (sb.table("summary_values")
      .upsert({"property_id": property_id, "item_key": item_key, "amount": amount, "provenance": provenance},
              on_conflict="property_id,item_key").execute())
    return {"item_key": item_key, "amount": amount}

# -------- helpers for compute_summary --------
def _get_number(property_id: str, key: str) -> Optional[float]:
    schema = nums_schema(property_id)
    sb.postgrest.schema = schema
    data = (sb.table("line_items").select("amount")
            .eq("property_id", property_id).eq("item_key", key).limit(1).execute()).data
    v = data[0]["amount"] if data else None
    return float(v) if v is not None else None

def _extract_from_meta(meta: Dict[str, Any], selector: str) -> Optional[float]:
    """selector supports 'a|b|c' alternatives and dotted paths like 'totals.gross'."""
    if not selector:
        return None
    alts = selector.split("|")
    for alt in alts:
        cur = meta
        ok = True
        for part in alt.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok:
            try:
                return float(str(cur).replace(",", ""))
            except Exception:
                continue
    return None

def _get_docs_values(property_id: str, group: str, subgroup: str, name: str, selector: str) -> List[Tuple[str, Optional[float]]]:
    # Use RPC to avoid PGRST205 schema cache issues
    all_docs = sb.rpc("list_property_documents", {"p_id": property_id}).execute().data or []
    rows = [
        d for d in all_docs
        if d.get("document_group") == group
        and (d.get("document_subgroup") or "") == (subgroup or "")
        and (name == "*" or d.get("document_name") == name)
    ]
    out: List[Tuple[str, Optional[float]]] = []
    for r in rows:
        val = _extract_from_meta(r.get("metadata") or {}, selector)
        out.append((r["document_name"], val))
    return out

import ast, operator
_ALLOWED = {
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Mod,
    ast.Load, ast.Expr, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant, ast.Name, ast.Expression,
}
def _safe_eval(expr: str, variables: Dict[str, float]) -> float:
    node = ast.parse(expr, mode="eval")
    for n in ast.walk(node):
        if type(n) not in _ALLOWED:
            raise ValueError(f"Illegal expression node: {type(n).__name__}")
        if isinstance(n, ast.Name) and n.id not in variables:
            variables[n.id] = 0.0
    code = compile(node, "<expr>", "eval")
    return float(eval(code, {"__builtins__": {}}, variables))

def compute_summary(property_id: str, only_items: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Reads summary_spec and writes summary_values.
    Supports sources: 'numbers', 'documents', 'formula'
    Aggregations: for documents: 'sum'|'latest'|'value' (first non-null).
    """
    spec = get_summary_spec(property_id)
    if only_items:
        spec = [s for s in spec if s["item_key"] in only_items]

    results: Dict[str, float] = {}
    provenance: Dict[str, Any] = {}

    # 1) numbers & documents first
    for s in spec:
        source = s.get("source")
        key = s["item_key"]
        if source == "numbers":
            val = _get_number(property_id, s["selector"]["item_key"])
            if val is not None:
                results[key] = val
                provenance[key] = {"source": "numbers", "item_key": s["selector"]["item_key"]}
        elif source == "documents":
            sel = s.get("selector") or {}
            group = sel.get("group", "")
            subgroup = sel.get("subgroup", "")
            name = sel.get("name", "*")
            json_key = sel.get("json_key", "")
            vals = _get_docs_values(property_id, group, subgroup, name, json_key)
            agg = (s.get("aggregation") or "value").lower()
            numbers = [v for (_n, v) in vals if isinstance(v, (int, float)) and v is not None]
            if numbers:
                if agg == "sum":
                    out = float(sum(numbers))
                elif agg == "latest":
                    out = float(numbers[-1])
                else:
                    out = float(numbers[0])
                results[key] = out
                provenance[key] = {"source": "documents", "matched": vals, "aggregation": agg}
        else:
            # formula handled later
            continue

    # 2) formulas (may depend on previous results)
    for s in spec:
        if s.get("source") == "formula":
            key = s["item_key"]
            expr = s.get("expression") or ""
            try:
                val = _safe_eval(expr, results.copy())
                results[key] = float(val)
                provenance[key] = {"source": "formula", "expression": expr, "inputs": {k: results.get(k) for k in results}}
            except Exception as e:
                provenance[key] = {"source": "formula", "error": str(e), "expression": expr}

    # 3) upsert into summary_values
    for k, v in results.items():
        upsert_summary_value(property_id, k, v, provenance.get(k, {}))

    return {"computed": results, "provenance": provenance}
