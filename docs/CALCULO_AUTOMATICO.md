# Sistema de Cálculo Automático de Fórmulas - Numbers Table Framework

## Resumen

El sistema Numbers Table ahora incluye **cálculo automático en cascada** de fórmulas. Cuando el usuario actualiza una celda amarilla (input), todas las fórmulas dependientes se recalculan automáticamente, incluyendo fórmulas que dependen de otras fórmulas.

---

## Arquitectura

### 1. Identificación de Celdas

Durante la importación del Excel (`import_excel_from_file`):

- **Celdas amarillas** (fondo `FFFF*`): Se marcan como `is_user_input: true`
  - Ejemplos: B5, B6, B7, B8, B11, C5, C6, C7, C8, B19-B21, B25-B28
  - Son los inputs del usuario (valores base para los cálculos)

- **Celdas con fórmulas**: Se guardan con su fórmula original (ej: `=B5*C5/100`)
  - Ejemplos: D5-D8 (IVA €), E5-E8 (Total IVA), B10 (Beneficio bruto), B12, B13, B14, B15, B18, B29
  - Se calculan automáticamente cuando cambian las celdas de las que dependen

### 2. Módulo de Cálculo (`tools/formula_calculator.py`)

El módulo proporciona las siguientes funciones:

- **`parse_cell_references(formula)`**: Extrae todas las referencias a celdas de una fórmula
  - Input: `"=B5*C5/100"`
  - Output: `{"B5", "C5"}`

- **`evaluate_formula(formula, cell_values)`**: Evalúa una fórmula usando los valores actuales
  - Input: `"=B5*C5/100"`, `{"B5": 1000, "C5": 21}`
  - Output: `210.0`

- **`build_dependency_graph(structure)`**: Construye un grafo de dependencias
  - Output: `{"D5": {"B5", "C5"}, "E5": {"B5", "D5"}}`

- **`get_affected_cells(updated_cell, dependencies)`**: Obtiene todas las celdas afectadas por un cambio
  - Input: `"B5"`, dependencies graph
  - Output: `["D5", "E5", "B10", "B12", "B13", "B14", "B15", "B18"]`

- **`recalculate_formulas(updated_cells, structure, current_values)`**: Recalcula todas las fórmulas en orden
  - Hace múltiples pasadas para manejar fórmulas en cascada
  - Redondea a 2 decimales para valores monetarios

- **`auto_calculate_on_update(property_id, template_key, updated_cell, new_value, structure, current_values)`**: Función principal
  - Entry point para el cálculo automático
  - Llamada automáticamente por `set_numbers_table_cell`

### 3. Modificación de `set_numbers_table_cell`

La función ahora incluye:

1. **Parámetro `auto_calculate=True`** (por defecto)
2. Después de guardar el valor del usuario en la DB:
   - Obtiene la estructura del template
   - Obtiene los valores actuales de la DB
   - Llama a `auto_calculate_on_update`
   - Guarda todos los valores calculados en la DB
3. Retorna:
   ```python
   {
       "ok": True,
       "cell_address": "B5",
       "value": "1000",
       "auto_calculated": {
           "D5": 210.0,
           "E5": 1210.0,
           "B10": ...,
           ...
       },
       "auto_calculated_count": 7
   }
   ```

---

## Ejemplo de Cascada

### Paso a paso:

1. **Usuario actualiza B5=1000**
   - Se guarda B5 en DB
   - Se detectan celdas dependientes: D5, E5, B10, B12, B13, B14, B15, B18
   - Se calculan:
     - D5 = B5*C5/100 (si C5 existe, sino None)
     - E5 = B5+D5 (si D5 se calculó)
     - B10 = B6-B7-B8 (si existen)
     - ... y así sucesivamente

2. **Usuario actualiza C5=21**
   - Se guarda C5 en DB
   - Se recalculan:
     - D5 = 1000*21/100 = **210**
     - E5 = 1000+210 = **1210**
     - Todas las fórmulas que dependen de D5 o E5

3. **Múltiples pasadas**
   - El sistema hace hasta 10 iteraciones para resolver fórmulas que dependen de otras fórmulas
   - Ejemplo: B15 depende de B12 y B14, que a su vez dependen de B10 y B13
   - Todas se resuelven en el orden correcto

---

## Fórmulas Soportadas

### Operadores Básicos
- `+`, `-`, `*`, `/`, `()`

### Funciones Excel
- **`IF(condition, value_if_true, value_if_false)`**
  - Ejemplo: `=IF(C8>0, B8*C8/100, 0)`
  - Se convierte a Python: `((B8*C8/100) if (C8>0) else (0))`

### Fórmulas R2B Específicas

| Celda | Fórmula | Descripción |
|-------|---------|-------------|
| D5-D8 | `=B[row]*C[row]/100` | IVA en euros |
| E5-E8 | `=B[row]+D[row]` | Total con IVA |
| B10 | `=B6-B7-B8` | Beneficio bruto venta terrenos |
| B12 | `=B10+B11` | Total ingresos brutos |
| B13 | `=B12*0.25` | Impuestos 25% |
| B14 | `=B13` | Impuestos (€) |
| B15 | `=B12-B14` | Beneficio neto |
| B18 | `=B15` | Referencia a Bº neto |
| B29 | `=B25+B26+B27+B28` | Total coste comprador |

---

## Frontend (Spreadsheet.tsx)

- Ya está configurado para leer `format.bg_color` de cada celda
- Las celdas amarillas se renderizarán automáticamente con su color de fondo
- No requiere cambios adicionales

---

## System Prompt

Se ha actualizado `agentic.py` para informar al agente sobre:

1. **Celdas amarillas**: El usuario solo debe rellenar estas
2. **Celdas con fórmulas**: Se calculan automáticamente, NO pedirle al usuario que las calcule manualmente
3. **Confirmación con auto_calculated**: El agente debe mencionar qué celdas se calcularon automáticamente
4. **Ejemplos few-shot**: Incluyen casos de cálculo en cascada

---

## Uso desde el Chat

### Ejemplo 1: Actualizar una celda
```
Usuario: "pon B5 a 1000"
Agente: ✅ Actualizado B5 a 1000. Se han calculado automáticamente: D5, E5, B10, B12, B13, B14, B15.
```

### Ejemplo 2: Actualizar múltiples celdas
```
Usuario: "pon B5 a 1000 y C5 a 21"
Agente: ✅ Actualizado B5 a 1000 y C5 a 21%. Se han calculado automáticamente D5 (IVA: 210€), E5 (Total: 1210€) y todas las fórmulas dependientes.
```

### Ejemplo 3: Completar toda la sección Bº RAMA
```
Usuario: "pon B6 a 200000, B7 a 50000, B8 a 30000, C6 a 21, C7 a 21, C8 a 0"
Agente: ✅ Actualizado todos los valores. Se han calculado automáticamente:
- D6 (IVA): 42,000€
- D7 (IVA): 10,500€
- D8 (IVA): 0€
- E6 (Total): 242,000€
- E7 (Total): 60,500€
- E8 (Total): 30,000€
- B10 (Beneficio bruto): 120,000€
- B12 (Total ingresos): 120,000€ (asumiendo B11=0)
- B13-B15 (Impuestos y beneficio neto)
```

---

## Limitaciones y Consideraciones

1. **Fórmulas circulares**: No soportadas (el cálculo se detendría después de 10 iteraciones)
2. **Funciones Excel avanzadas**: Solo soporta `IF` por ahora (fácilmente extensible)
3. **Referencias a otras hojas**: No soportadas
4. **Referencias a rangos**: No soportadas (ej: `SUM(B5:B10)`)
5. **Valores no numéricos**: Se manejan como 0 o se ignoran
6. **Precisión**: Los valores se redondean a 2 decimales (apropiado para moneda)

---

## Próximos Pasos (Futuro)

1. Soporte para funciones Excel adicionales: `SUM`, `AVERAGE`, `MAX`, `MIN`, `ROUND`
2. Validación de tipos (asegurar que porcentajes sean 0-100, importes sean positivos, etc.)
3. Notificaciones en tiempo real cuando se recalculan fórmulas (SSE/WebSocket)
4. Exportación con fórmulas intactas (actualmente solo valores)
5. Validación de fórmulas circulares con mensaje de error específico

