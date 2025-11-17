# Solución: Fórmulas No Se Guardaron

## Problema Identificado

Al revisar la estructura almacenada en la base de datos, TODAS las celdas tienen `"formula": null`:

```json
{
  "address": "D5",
  "formula": null,
  "value": ""
}
```

Los logs del backend confirmaron:
```
[recalculate_all_formulas] Found 0 cells with formulas
```

## Causa Raíz

El código de importación usaba `load_workbook(file_bytes, data_only=True)`, que solo lee los **valores calculados** de las celdas, NO las fórmulas.

## Fix Aplicado

**Archivo**: `tools/numbers_tools.py` (línea 360)

**Antes**:
```python
wb = load_workbook(BytesIO(file_bytes), data_only=True)
```

**Después**:
```python
# CRITICAL: data_only=False to read formulas, not just values
wb = load_workbook(BytesIO(file_bytes), data_only=False)
```

## Qué Hace Este Cambio

- **`data_only=True`**: Solo lee valores, ignora fórmulas
- **`data_only=False`**: Lee fórmulas y las preserva en la estructura

Con `data_only=False`, cuando una celda tiene `=B5*C5/100`, `openpyxl` guarda:
- `cell.value` = `"=B5*C5/100"` (la fórmula como string)
- `cell.data_type` = `'f'` (formula)

## Próximos Pasos

1. **Re-importar el Excel**:
   - Sube el Excel R2B de nuevo
   - Ahora las fórmulas se guardarán correctamente

2. **Verificar**:
   - Después de subir, verifica en los logs: `Found X cells with formulas` (X > 0)
   - Deberías ver algo como: `Found 15 cells with formulas: ['D5', 'D6', 'D7', ...]`

3. **Auto-cálculo funcionará**:
   - Una vez que las fórmulas estén guardadas, el auto-cálculo funcionará
   - Cuando tengas B5=100 y C5=10, D5 se calculará automáticamente

## Alternativa Si No Funciona

Si el Excel que subes NO tiene fórmulas (fue exportado solo con valores), necesitas:

1. **Opción A**: Usar el Excel original que SÍ tiene las fórmulas (no una copia)

2. **Opción B**: Insertar manualmente las fórmulas en el Excel antes de subir

3. **Opción C**: Crear las fórmulas programáticamente durante la importación (más complejo)

## Cómo Verificar si Tu Excel Tiene Fórmulas

Abre el Excel en Microsoft Excel / LibreOffice:
1. Haz click en celda D5
2. Mira la barra de fórmulas arriba
3. **Debería mostrar**: `=B5*C5/100`
4. **Si muestra solo un número**: NO tiene fórmulas, solo valores

## Logging Para Verificar

Después de re-importar, busca en los logs:
```bash
tail -f /tmp/rama_backend.log | grep "formula\|import_excel_from_file"
```

Deberías ver:
```
INFO:tools.numbers_tools:Starting Excel import from file...
...
DEBUG: Cell D5 has formula: =B5*C5/100
DEBUG: Cell E5 has formula: =B5+D5
...
INFO: Saved structure with 15 formulas
```

