# 🔍 Logs para Monitorear

Cuando añadas un valor via chat (por ejemplo, "pon 1000 en B5"), busca estos logs:

## 1. Auto-cálculo iniciado:
```
[set_numbers_table_cell] 🔥 Starting auto-calculation for B5
[auto_calculate_on_update] Starting auto-calculation for B5 = 1000
```

## 2. Dependency graph construido:
```
[build_dependency_graph] Found X cells with formulas
[build_dependency_graph] Built dependency graph with X cells
```

Si muestra `Found 0 cells with formulas` → **PROBLEMA**: Las fórmulas no se inyectaron en la estructura.

## 3. Celdas afectadas encontradas:
```
[get_affected_cells] Cell C5 was updated
[get_affected_cells] Found X affected cells: ['D5', 'E5', ...]
```

Si muestra `Found 0 affected cells` → **PROBLEMA**: El dependency graph no se construyó correctamente o no hay dependencias.

## 4. Cálculos realizados:
```
[recalculate_formulas] Calculated D5 = 210.0 (formula: =B5*C5/100)
[recalculate_formulas] Calculated E5 = 1210.0 (formula: =B5+D5)
```

Si no aparecen estos logs → **PROBLEMA**: Las fórmulas no se evaluaron correctamente.

## 5. Guardado en DB:
```
💾 Saving X auto-calculated cells to DB
✅ Saved calculated value: D5 = 210
✅ Saved calculated value: E5 = 1210
```

## 6. Confirmación final:
```
✅ Auto-calculated and saved X cells: ['D5', 'E5', ...]
```

---

## Para monitorear en tiempo real:
```bash
tail -f /tmp/rama_backend.log | grep -E "auto.*calc|formula|dependency|affected"
```

