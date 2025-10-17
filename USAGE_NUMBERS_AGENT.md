Numbers Agent – Usage Guide

Scope
- Operates strictly on the active property’s numbers framework.
- NEVER invents numbers; only computes from current inputs.

Quick chat commands (in numbers mode)
- "listar esquema" → shows plantilla + actions
- "calcular" → recompute derived metrics and validate anomalies
- "what if precio de venta -10% y construcción +12%" → scenario
- "break-even de precio" → solve precio_venta for net_profit≈0
- "waterfall" / "composición de costes" / "sensibilidad" → charts
- "envíalo por email" → sends Excel (.xlsx) with inputs/derived/anomalies and recent scenarios/sensitivity grid

Derived metrics
- impuestos_total = impuestos_pct * precio_venta
- costes_totales = project_mgmt_fees + terrenos_coste + project_management_coste + acometidas + costes_construccion
- gross_margin = precio_venta - costes_totales
- net_profit = precio_venta - costes_totales - impuestos_total
- roi_pct = net_profit / total_pagado
- urbano_ratio = terreno_urbano / (terreno_urbano + terreno_rustico)
- price_per_m2 = precio_venta / superficie_m2 (when present)

Validations/guardrails
- impuestos_pct ∈ [0, 0.25]
- non-negative numeric fields
- total_pagado > precio_venta flagged
- net_profit < 0 flagged

REST endpoints (Python backend)
- POST /numbers/compute (Form: property_id)
- GET  /numbers/excel?property_id=...
- POST /numbers/what_if (Form: property_id, deltas_json)
- POST /numbers/sensitivity (Form: property_id, precio_vec_json, costes_vec_json)
- POST /numbers/break_even (Form: property_id, tol)
- POST /numbers/chart/waterfall (Form: property_id)
- POST /numbers/chart/stack (Form: property_id)
- POST /numbers/chart/sensitivity (Form: property_id, precio_vec_json, costes_vec_json)

Storage & persistence
- Charts: Supabase Storage at charts/{property_id}/{chart_type}/{timestamp}.png (signed URLs)
- Tables (public): calc_outputs, calc_log, scenario_snapshots, chart_cache (see DATABASE_DDL_GUIDE.md)


