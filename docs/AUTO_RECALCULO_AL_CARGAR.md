# Auto-Recálculo de Fórmulas al Cargar

## Problema Resuelto

**Antes**: Cuando el usuario volvía a entrar en una plantilla que ya tenía valores (B5=100, C5=10), las celdas con fórmulas (D5) estaban vacías porque el auto-cálculo solo se activaba al **actualizar** un valor, no al **cargar** la plantilla.

**Ahora**: El sistema auto-recalcula TODAS las fórmulas cuando:
1. El usuario abre una plantilla que ya tiene valores
2. El usuario recarga la página con una plantilla activa
3. Después de cada actualización de celda (cascada)

---

## Implementación

### 1. Nuevo Módulo: `tools/numbers_recalculate.py`

**Funciones principales**:

#### `recalculate_all_formulas(property_id, template_key, structure, current_values)`
- Encuentra TODAS las celdas con fórmulas
- Obtiene TODAS las celdas que tienen valores (inputs del usuario)
- Trata todos los valores existentes como "actualizados" para forzar el recálculo
- Usa el sistema de cascada para calcular en el orden correcto

#### `save_calculated_values(property_id, template_key, calculated, structure)`
- Guarda todos los valores calculados en la base de datos
- Usa el RPC `set_numbers_table_cell` para cada celda

#### `recalculate_and_save(property_id, template_key)`
- Entry point principal
- Obtiene estructura y valores actuales
- Recalcula todas las fórmulas
- Guarda en la DB
- Retorna resultado con celdas calculadas

---

### 2. Nuevo Endpoint: `POST /api/numbers/recalculate`

**Archivo**: `app.py` (líneas 2308-2332)

**Parámetros**:
- `property_id` (FormData)
- `template_key` (FormData)

**Retorna**:
```json
{
  "ok": true,
  "calculated": {
    "D5": 10.0,
    "E5": 110.0,
    "B10": 50.0,
    ...
  },
  "saved_count": 7,
  "message": "Se han calculado automáticamente 7 celdas: D5, E5, B10, B12, B13"
}
```

---

### 3. Frontend: Auto-Recálculo al Cargar

**Archivo**: `web/src/app/page.tsx` (líneas 469-524)

**Nueva función**: `autoRecalculateFormulas()`
- Se llama automáticamente después de cargar la tabla
- Hace un POST a `/api/numbers/recalculate`
- Si hay fórmulas calculadas, recarga la tabla para mostrarlas

**Flujo**:
```
Usuario abre plantilla con B5=100, C5=10
  ↓
loadAddresses() carga estructura y valores
  ↓
autoRecalculateFormulas() detecta que D5 se puede calcular
  ↓
Backend calcula D5 = 100*10/100 = 10
  ↓
Backend guarda D5=10 en DB
  ↓
Frontend recarga tabla
  ↓
D5 aparece con valor 10
```

---

## Casos de Uso

### Caso 1: Abrir plantilla con valores existentes

**Escenario**: 
- El usuario cerró la app con B5=100, C5=10
- D5 estaba vacío (no se había calculado antes)

**Resultado con el nuevo sistema**:
1. Usuario abre la plantilla R2B
2. Sistema carga B5=100, C5=10
3. **AUTO-RECALCULA**: D5 = 100*10/100 = 10
4. D5 aparece automáticamente en la tabla

---

### Caso 2: Insertar nuevo valor

**Escenario**:
- La tabla tiene B5=100
- El usuario actualiza C5=10

**Resultado**:
1. Usuario escribe "pon C5 a 10"
2. Backend guarda C5=10
3. **AUTO-CALCULA (cascada)**: D5, E5, B10, B12, B13, B14, B15
4. Todos los valores aparecen automáticamente
5. Agente responde: "✅ Actualizado C5 a 10. Se han calculado automáticamente: D5, E5, B10, B12, B13, B14, B15."

---

### Caso 3: Completar todos los inputs

**Escenario**:
- El usuario completa todas las celdas amarillas: B5, B6, B7, B8, B11, C5, C6, C7, C8

**Resultado**:
- Todas las fórmulas se calculan automáticamente:
  - D5, D6, D7, D8 (IVA en €)
  - E5, E6, E7, E8 (Total con IVA)
  - B10 (Beneficio bruto)
  - B12 (Total ingresos brutos)
  - B13, B14 (Impuestos)
  - B15 (Beneficio neto)
  - B18 (Referencia a Bº neto)

---

## Ventajas

1. **Experiencia del usuario mejorada**: No necesita "calcular manualmente" ni recargar
2. **Consistencia de datos**: Todas las fórmulas siempre están actualizadas
3. **Transparencia**: El agente informa qué celdas se calcularon automáticamente
4. **Eficiencia**: El cálculo en cascada evita cálculos redundantes

---

## Logging para Debug

**Buscar en logs del backend**:
```bash
grep "recalculate_all_formulas" <log_file>
grep "🔄 Auto-recalculating" <log_file>
grep "✅ Formulas recalculated" <log_file>
```

**Logs esperados**:
```
INFO:tools.numbers_recalculate:[recalculate_all_formulas] Starting full recalculation...
INFO:tools.numbers_recalculate:[recalculate_all_formulas] Found 15 cells with formulas
INFO:tools.numbers_recalculate:[recalculate_all_formulas] Found 8 cells with values: ['B5', 'C5', 'B6', ...]
INFO:tools.numbers_recalculate:[recalculate_all_formulas] Successfully calculated 7 formulas: ['D5', 'E5', 'B10', ...]
INFO:tools.numbers_recalculate:[save_calculated_values] ✅ Saved 7/7 calculated values
```

---

## Próximos Pasos (Opcional)

1. **Botón manual "Recalcular"**: Por si el usuario quiere forzar un recálculo
2. **Indicador visual**: Mostrar qué celdas están calculadas vs inputs del usuario
3. **Validación de fórmulas**: Detectar y notificar si una fórmula no puede calcularse por falta de valores
4. **Cache de cálculos**: Evitar recalcular si los valores no han cambiado

