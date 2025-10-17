from __future__ import annotations
import io
import json
from typing import Dict, Tuple, Any, List

from .numbers_tools import get_numbers
from .supabase_client import sb
from .supabase_client import BUCKET


def _to_map(rows: list[dict]) -> Dict[str, float]:
    """Convert numbers rows into a simple {item_key: amount} map, skipping None.
    Percent fields are already stored as 0.xx according to product spec.
    """
    out: Dict[str, float] = {}
    for r in rows or []:
        k = r.get("item_key")
        amt = r.get("amount")
        if k is None:
            continue
        try:
            out[k] = float(amt) if amt is not None else None
        except Exception:
            out[k] = None
    return out


def _safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def compute_derived_from_inputs(inputs: Dict[str, float]) -> Dict[str, float | None]:
    """Compute derived metrics using provided inputs.
    Keys expected (optional if missing):
    - precio_venta, impuestos_pct, project_mgmt_fees, terrenos_coste,
      project_management_coste, acometidas, costes_construccion,
      total_pagado, terreno_urbano, terreno_rustico, superficie_m2 (optional)
    """
    precio_venta = inputs.get("precio_venta")
    impuestos_pct = inputs.get("impuestos_pct")
    project_mgmt_fees = inputs.get("project_mgmt_fees")
    terrenos_coste = inputs.get("terrenos_coste")
    project_management_coste = inputs.get("project_management_coste")
    acometidas = inputs.get("acometidas")
    costes_construccion = inputs.get("costes_construccion")
    total_pagado = inputs.get("total_pagado")
    terreno_urbano = inputs.get("terreno_urbano")
    terreno_rustico = inputs.get("terreno_rustico")
    superficie_m2 = inputs.get("superficie_m2")

    impuestos_total = None
    if impuestos_pct is not None and precio_venta is not None:
        impuestos_total = impuestos_pct * precio_venta

    def _sum(values: list[float | None]) -> float | None:
        acc = 0.0
        has = False
        for v in values:
            if v is not None:
                has = True
                acc += float(v)
        return acc if has else None

    costes_totales = _sum([
        project_mgmt_fees,
        terrenos_coste,
        project_management_coste,
        acometidas,
        costes_construccion,
    ])

    gross_margin = None
    if precio_venta is not None and costes_totales is not None:
        gross_margin = precio_venta - costes_totales

    net_profit = None
    if precio_venta is not None and costes_totales is not None and impuestos_total is not None:
        net_profit = precio_venta - costes_totales - impuestos_total

    roi_pct = _safe_div(net_profit, total_pagado)

    urbano_ratio = None
    if terreno_urbano is not None and terreno_rustico is not None:
        denom = terreno_urbano + terreno_rustico
        urbano_ratio = _safe_div(terreno_urbano, denom)

    price_per_m2 = _safe_div(precio_venta, superficie_m2)

    return {
        "impuestos_total": impuestos_total,
        "costes_totales": costes_totales,
        "gross_margin": gross_margin,
        "net_profit": net_profit,
        "roi_pct": roi_pct,
        "urbano_ratio": urbano_ratio,
        "price_per_m2": price_per_m2,
    }


def validate_anomalies(inputs: Dict[str, float], outputs: Dict[str, float | None]) -> list[str]:
    warnings: list[str] = []
    impuestos_pct = inputs.get("impuestos_pct")
    precio_venta = inputs.get("precio_venta")
    total_pagado = inputs.get("total_pagado")
    net_profit = outputs.get("net_profit")

    # impuestos_pct range
    if impuestos_pct is not None and not (0 <= impuestos_pct <= 0.25):
        warnings.append("impuestos_pct fuera de rango [0,0.25]")
    # non-negative checks (selected inputs)
    for k in [
        "precio_venta", "project_mgmt_fees", "terrenos_coste", "project_management_coste",
        "acometidas", "costes_construccion", "total_pagado", "terreno_urbano", "terreno_rustico"
    ]:
        v = inputs.get(k)
        if v is not None and v < 0:
            warnings.append(f"{k} es negativo")
    # total_pagado vs precio_venta
    if precio_venta is not None and total_pagado is not None and total_pagado > precio_venta:
        warnings.append("total_pagado > precio_venta")
    # net_profit negative
    if net_profit is not None and net_profit < 0:
        warnings.append("net_profit negativo")

    return warnings


def compute_and_log(property_id: str, triggered_by: str = "agent", trigger_type: str = "manual") -> Dict[str, Any]:
    """Compute derived metrics for a property, persist best-effort to calc_outputs and calc_log.
    Returns {inputs, outputs, anomalies}.
    """
    rows = get_numbers(property_id)
    inputs = _to_map(rows)
    outputs = compute_derived_from_inputs(inputs)
    anomalies = validate_anomalies(inputs, outputs)

    # Best-effort persistence (tables may not exist yet)
    try:
        sb.table("calc_outputs").upsert({
            "property_id": property_id,
            "outputs": outputs,
            "anomalies": anomalies,
        }, on_conflict="property_id").execute()
    except Exception:
        pass
    try:
        sb.table("calc_log").insert({
            "property_id": property_id,
            "inputs": inputs,
            "outputs": outputs,
            "anomalies": anomalies,
            "triggered_by": triggered_by,
            "trigger_type": trigger_type,
        }).execute()
    except Exception:
        pass

    return {"inputs": inputs, "outputs": outputs, "anomalies": anomalies}


def generate_numbers_excel(property_id: str) -> bytes:
    """Create an Excel workbook with Inputs, Derived, and Anomalies sheets. Returns bytes."""
    import pandas as pd
    # Compute fresh values for the export
    result = compute_and_log(property_id, triggered_by="agent", trigger_type="export")
    inputs = result["inputs"]
    outputs = result["outputs"]
    anomalies = result["anomalies"]
    # Try to include last sensitivity or what-if snapshots if present
    scenarios_df = None
    sens_df = None
    try:
        snaps = sb.table("scenario_snapshots").select("name,deltas,outputs,created_at").eq("property_id", property_id).order("created_at", desc=True).limit(50).execute().data
        if snaps:
            rows = []
            for s in snaps:
                rows.append({
                    "name": s.get("name"),
                    "deltas": s.get("deltas"),
                    "outputs": s.get("outputs"),
                    "created_at": s.get("created_at"),
                })
            scenarios_df = pd.json_normalize(rows)
            # Extract last sensitivity grid if any
            for s in snaps:
                if (s.get("name") or "").lower() == "sensitivity" and s.get("outputs", {}).get("grid"):
                    z = s["outputs"]["grid"]
                    sens_df = pd.DataFrame(z)
                    break
    except Exception:
        pass

    # Build dataframes
    df_inputs = pd.DataFrame([{"item_key": k, "amount": inputs.get(k)} for k in sorted(inputs.keys())])
    df_outputs = pd.DataFrame([{"metric": k, "value": outputs.get(k)} for k in sorted(outputs.keys())])
    df_anom = pd.DataFrame({"anomaly": anomalies}) if anomalies else pd.DataFrame(columns=["anomaly"])

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_inputs.to_excel(writer, index=False, sheet_name="Inputs")
        df_outputs.to_excel(writer, index=False, sheet_name="Derived")
        df_anom.to_excel(writer, index=False, sheet_name="Anomalies")
        if scenarios_df is not None:
            scenarios_df.to_excel(writer, index=False, sheet_name="Scenarios")
        if sens_df is not None:
            sens_df.to_excel(writer, index=False, sheet_name="SensitivityGrid")
    return buf.getvalue()


# ------------------ Scenarios & Sensitivity ------------------
def apply_deltas(base: Dict[str, float], deltas: Dict[str, float]) -> Dict[str, float]:
    """Apply multiplicative deltas to base (e.g., {precio_venta: -0.1} means -10%)."""
    out = dict(base)
    for k, pct in (deltas or {}).items():
        v = out.get(k)
        if v is None:
            continue
        try:
            out[k] = float(v) * (1.0 + float(pct))
        except Exception:
            pass
    return out


def what_if(property_id: str, deltas: Dict[str, float], name: str | None = None) -> Dict[str, Any]:
    """Compute a what-if scenario, persist snapshot best-effort, and return outputs.
    Deltas are fractional (e.g., {"precio_venta": -0.1, "costes_construccion": 0.12}).
    """
    rows = get_numbers(property_id)
    base = _to_map(rows)
    scenario_inputs = apply_deltas(base, deltas)
    outputs = compute_derived_from_inputs(scenario_inputs)
    anomalies = validate_anomalies(scenario_inputs, outputs)
    try:
        sb.table("scenario_snapshots").insert({
            "property_id": property_id,
            "name": name or "what_if",
            "deltas": deltas,
            "outputs": outputs,
        }).execute()
    except Exception:
        pass
    return {"inputs": scenario_inputs, "outputs": outputs, "anomalies": anomalies}


def sensitivity_grid(property_id: str, precio_vec: List[float], costes_vec: List[float]) -> Dict[str, Any]:
    """Build a sensitivity grid for net_profit with multiplicative vectors for precio_venta and costes_construccion.
    Vectors contain fractional changes (e.g., [-0.2,-0.1,0,0.1,0.2]).
    """
    rows = get_numbers(property_id)
    base = _to_map(rows)
    grid: List[List[float | None]] = []
    for dv in precio_vec:
        row: List[float | None] = []
        for dc in costes_vec:
            scenario = apply_deltas(base, {"precio_venta": dv, "costes_construccion": dc})
            outs = compute_derived_from_inputs(scenario)
            row.append(outs.get("net_profit"))
        grid.append(row)
    try:
        sb.table("scenario_snapshots").insert({
            "property_id": property_id,
            "name": "sensitivity",
            "deltas": {"precio_vec": precio_vec, "costes_vec": costes_vec},
            "outputs": {"grid": grid},
        }).execute()
    except Exception:
        pass
    return {"precio_vec": precio_vec, "costes_vec": costes_vec, "grid": grid}


def break_even_precio(property_id: str, tol: float = 1.0, max_iter: int = 60) -> Dict[str, Any]:
    """Solve for precio_venta such that net_profit ≈ 0 using bisection on a reasonable bracket.
    Returns {precio_venta, net_profit, iterations} or error.
    """
    rows = get_numbers(property_id)
    base = _to_map(rows)
    # Build a helper to evaluate net_profit for a given precio
    def f(precio: float) -> float | None:
        scenario = dict(base)
        scenario["precio_venta"] = precio
        outs = compute_derived_from_inputs(scenario)
        return outs.get("net_profit")

    # Find a bracket around current precio (or a default)
    p0 = base.get("precio_venta") or 100000.0
    lo = max(1.0, p0 * 0.5)
    hi = p0 * 1.5
    v_lo = f(lo)
    v_hi = f(hi)
    if v_lo is None or v_hi is None:
        return {"error": "insufficient_data"}
    # If same sign, expand a bit
    expand = 0
    while v_lo is not None and v_hi is not None and v_lo * v_hi > 0 and expand < 5:
        lo *= 0.8
        hi *= 1.2
        v_lo = f(lo)
        v_hi = f(hi)
        expand += 1
    if v_lo is None or v_hi is None:
        return {"error": "insufficient_data"}
    # Bisection
    it = 0
    root = None
    while it < max_iter:
        mid = 0.5 * (lo + hi)
        v_mid = f(mid)
        if v_mid is None:
            break
        if abs(v_mid) <= tol:
            root = mid
            break
        # Decide side
        if v_lo * v_mid <= 0:
            hi = mid
            v_hi = v_mid
        else:
            lo = mid
            v_lo = v_mid
        it += 1
    if root is None:
        root = 0.5 * (lo + hi)
    return {"precio_venta": root, "net_profit": f(root), "iterations": it}


# ------------------ Charts (Plotly PNG → Supabase) ------------------
def _save_png(property_id: str, fig, chart_type: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    import time
    import plotly.io as pio
    # Generate PNG bytes with Kaleido
    png_bytes = pio.to_image(fig, format="png", scale=2)
    key = f"charts/{property_id}/{chart_type}/{int(time.time())}.png"
    try:
        sb.storage.from_(BUCKET).upload(key, png_bytes, {"content-type": "image/png", "upsert": "true"})
        signed = sb.storage.from_(BUCKET).create_signed_url(key, 3600)
        # Cache entry (best-effort)
        try:
            sb.table("chart_cache").insert({
                "property_id": property_id,
                "chart_type": chart_type,
                "params": params or {},
                "storage_key": key,
            }).execute()
        except Exception:
            pass
        return {"storage_key": key, "signed_url": signed.get("signedURL")}
    except Exception as e:
        return {"error": str(e)}


def chart_waterfall(property_id: str) -> Dict[str, Any]:
    try:
        import plotly.graph_objects as go
    except ModuleNotFoundError:
        return {"error": "plotly_no_instalado", "hint": "Instala plotly y kaleido (pip install plotly kaleido) y reinicia el servidor."}
    rows = get_numbers(property_id)
    vals = _to_map(rows)
    precio = vals.get("precio_venta")
    buckets = {
        "Project Mgmt": vals.get("project_mgmt_fees"),
        "Terrenos": vals.get("terrenos_coste"),
        "Project Management": vals.get("project_management_coste"),
        "Acometidas": vals.get("acometidas"),
        "Construcción": vals.get("costes_construccion"),
    }
    impuestos_total = None
    if vals.get("impuestos_pct") is not None and precio is not None:
        impuestos_total = vals["impuestos_pct"] * precio

    if precio is None:
        return {"error": "precio_venta requerido"}

    measure = ["relative"] * len(buckets)
    text = []
    y = [-(buckets[k] or 0.0) for k in buckets]
    labels = list(buckets.keys())
    if impuestos_total is not None:
        labels.append("Impuestos")
        y.append(-impuestos_total)
        measure.append("relative")
    # Net profit bar
    # compute derived quickly
    outs = compute_derived_from_inputs(vals)
    net = outs.get("net_profit") or 0.0
    labels.append("Net Profit")
    y.append(net)
    measure.append("total")

    fig = go.Figure(go.Waterfall(
        name="Profit",
        orientation="v",
        measure=measure,
        x=labels,
        textposition="outside",
        y=y,
        decreasing={"marker": {"color": "#c5ac85"}},
        increasing={"marker": {"color": "#6eb55e"}},
        totals={"marker": {"color": "#3d7435"}},
    ))
    fig.update_layout(title="Precio de venta → Net Profit", showlegend=False)
    return _save_png(property_id, fig, "waterfall", {"buckets": list(buckets.keys())})


def chart_cost_stack(property_id: str) -> Dict[str, Any]:
    try:
        import plotly.graph_objects as go
    except ModuleNotFoundError:
        return {"error": "plotly_no_instalado", "hint": "Instala plotly y kaleido (pip install plotly kaleido) y reinicia el servidor."}
    rows = get_numbers(property_id)
    v = _to_map(rows)
    buckets = {
        "Project Mgmt": v.get("project_mgmt_fees"),
        "Terrenos": v.get("terrenos_coste"),
        "Project Management": v.get("project_management_coste"),
        "Acometidas": v.get("acometidas"),
        "Construcción": v.get("costes_construccion"),
    }
    total = sum([x for x in buckets.values() if x is not None]) if any(buckets.values()) else 0.0
    parts = [(k, (buckets[k] or 0.0) / total if total else 0.0) for k in buckets]

    fig = go.Figure()
    fig.add_bar(x=["Composición"], y=[p[1] for p in parts], name="%", marker_color=["#b3dfaa", "#8fcb7f", "#6eb55e", "#4f9542", "#3d7435"] * 2)
    fig.update_layout(barmode="stack", title="Composición de costes (100%)", yaxis=dict(tickformat=",.0%"))
    return _save_png(property_id, fig, "stacked_100", {})


def chart_sensitivity_heatmap(property_id: str, precio_vec: List[float], costes_vec: List[float]) -> Dict[str, Any]:
    try:
        import plotly.graph_objects as go
    except ModuleNotFoundError:
        return {"error": "plotly_no_instalado", "hint": "Instala plotly y kaleido (pip install plotly kaleido) y reinicia el servidor."}
    grid = sensitivity_grid(property_id, precio_vec, costes_vec)
    z = grid.get("grid") or []
    # UI palette: earth → neutral → green
    campo_colorscale = [
        [0.0, "#c5ac85"],   # earth (negative)
        [0.5, "#d4eece"],   # neutral light green
        [1.0, "#3d7435"],   # deep green (positive)
    ]
    fig = go.Figure(data=go.Heatmap(z=z, x=costes_vec, y=precio_vec, colorscale=campo_colorscale))
    fig.update_layout(title="Sensibilidad net_profit (precio vs construcción)", xaxis_title="Δ costes_construccion", yaxis_title="Δ precio_venta")
    return _save_png(property_id, fig, "sensitivity_heatmap", {"precio_vec": precio_vec, "costes_vec": costes_vec})




