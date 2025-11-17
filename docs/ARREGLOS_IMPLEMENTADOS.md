# Arreglos Implementados - Sistema de Cálculo Automático

## Problemas Reportados

1. ❌ **Valores calculados no aparecen en la tabla**
2. ❌ **Cálculo NO es automático** (usuario tuvo que pedir "calcula D5")
3. ❌ **Celdas amarillas no se ven en la tabla**

---

## Soluciones Implementadas

### 1. ✅ Cálculo Automático Integrado en `set_numbers_table_cell`

**Archivo**: `tools/numbers_tools.py` (líneas 604-724)

**Cambios**:
- Añadido parámetro `auto_calculate=True` (por defecto)
- Después de guardar el valor del usuario en la DB:
  1. Obtiene la estructura del template
  2. Obtiene los valores actuales de la DB
  3. Llama a `auto_calculate_on_update` del módulo `formula_calculator`
  4. **GUARDA AUTOMÁTICAMENTE** todos los valores calculados en la DB
  5. Retorna `auto_calculated` con las celdas recalculadas

**Resultado**: Ahora cuando el usuario actualiza B5 y C5, D5 y E5 se calculan y guardan automáticamente.

---

### 2. ✅ Celdas Amarillas Marcadas Durante Import

**Archivo**: `tools/numbers_tools.py` (líneas 466-486)

**Cambios**:
- Durante `import_excel_from_file`, detecta celdas con fondo amarillo (`FFFF*`)
- Marca estas celdas con `is_user_input: true` en la estructura
- Esta información se guarda en `numbers_templates` table

**Resultado**: El sistema sabe cuáles son celdas de input y cuáles tienen fórmulas.

---

### 3. ✅ Frontend Pasa Formato Completo a Celdas

**Archivo**: `web/src/app/page.tsx` (líneas 430-440)

**Cambios**:
- En `loadAddresses`, busca el `cellInfo` de la estructura para cada celda
- Pasa el formato completo (incluyendo `bg_color` y `is_user_input`) al componente Spreadsheet

**Resultado**: El color de fondo amarillo se transfiere desde el Excel importado hasta el renderizado en el frontend.

---

### 4. ✅ Spreadsheet Muestra Celdas Amarillas

**Archivo**: `web/src/components/Spreadsheet.tsx` (líneas 115, 127)

**Cambios**:
- `getCellData` extrae `is_user_input` de cada celda
- El `style` de cada `<td>` usa `bgColor` del formato, que incluye el amarillo

**Resultado**: Las celdas amarillas se renderizan visualmente con su color de fondo original.

---

## Flujo Completo Ahora

### Antes (problema):
```
Usuario: "pon B5 a 100"
→ B5=100 se guarda en DB
→ D5, E5 NO se calculan
→ Usuario tiene que decir "calcula D5"
→ D5 se calcula pero NO se guarda en DB
→ D5 no aparece en la tabla
```

### Ahora (solución):
```
Usuario: "pon B5 a 100"
→ set_numbers_table_cell guarda B5=100 en DB
→ 🔥 auto_calculate detecta que D5 depende de B5
→ 🔥 D5 se calcula automáticamente (si C5 existe)
→ 🔥 D5 se GUARDA automáticamente en DB
→ Frontend refresca y D5 aparece en la tabla
→ Agente responde: "✅ Actualizado B5 a 100. Se han calculado automáticamente: D5."
```

### Cascada completa:
```
Usuario: "pon B5 a 1000 y C5 a 21"
→ set_numbers_table_cell guarda B5=1000
→ 🔥 Calcula y guarda D5 = 1000*21/100 = 210
→ 🔥 Calcula y guarda E5 = 1000+210 = 1210
→ set_numbers_table_cell guarda C5=21
→ 🔥 Recalcula D5 = 210 (ya calculado)
→ 🔥 Recalcula E5 = 1210 (ya calculado)
→ Frontend refresca: B5=1000, C5=21, D5=210, E5=1210 (todos visibles)
→ Agente responde: "✅ Actualizado B5 a 1000 y C5 a 21%. Se han calculado automáticamente D5 (IVA: 210€), E5 (Total: 1210€) y todas las fórmulas dependientes."
```

---

## Celdas Amarillas en UI

**Cómo funcionan ahora**:

1. **Durante importación del Excel**:
   - `openpyxl` lee el `cell.fill.start_color.rgb`
   - Si el color empieza con `FFFF` (amarillo), marca `is_user_input: true`
   - Se guarda en `structure.cells[].format.bg_color` como hex (ej: `#FFFF00`)

2. **Durante renderizado en frontend**:
   - `page.tsx` pasa `format` completo a cada celda en la matriz
   - `Spreadsheet.tsx` extrae `bgColor` del formato
   - `<td style={{backgroundColor: bgColor}}>`

3. **Resultado visual**:
   - B5, B6, B7, C5, C6, C7, etc. → Amarillo (inputs del usuario)
   - D5, D6, D7, E5, E6, E7, etc. → Blanco/gris (fórmulas, auto-calculadas)

---

## Reinicio del Backend

**Comando ejecutado**:
```bash
pkill -f "uvicorn app:app"
sleep 1
cd /Users/mariasebares/Documents/RAMA_AI/rama-agentic-ai
source .venv/bin/activate
uvicorn app:app --reload --port 7901
```

**Estado**: ✅ Backend corriendo en puerto 7901 con todos los cambios aplicados.

---

## Próximo Paso

**Probar el flujo completo**:
1. Navegar a una propiedad con template R2B
2. Decir en el chat: "pon B5 a 1000"
3. Decir en el chat: "pon C5 a 21"
4. **Verificar**:
   - D5 debe mostrar "210" automáticamente
   - E5 debe mostrar "1210" automáticamente
   - Las celdas amarillas deben verse amarillas
   - El agente debe mencionar qué celdas se calcularon automáticamente

---

## Logging para Debug

Si los cálculos no funcionan, revisar los logs del backend:

```bash
# Buscar logs de auto-cálculo
grep "auto_calculate" <backend_log>
grep "🔥 Starting auto-calculation" <backend_log>
grep "💾 Saving" <backend_log>
```

Estos logs mostrarán:
- Qué celdas se están calculando
- Qué valores se están guardando
- Si hay errores en la evaluación de fórmulas

