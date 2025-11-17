# 🛡️ Protección de Valores del Usuario

## Problema Identificado

Cuando el usuario añade valores via chat (ej: B5=1000, C5=5), estos valores se guardan correctamente en la base de datos. PERO:

**Cuando se re-importa el Excel** (upload de nuevo archivo o reload de página):
- `import_excel_from_file` lee el Excel y guarda solo los valores que vienen en el archivo
- Como el Excel original está vacío en B5 y C5, esos valores **NO se re-guardan**
- Resultado: **Los valores añadidos por el usuario se borran** ❌

## Solución Implementada

### 1. Protección en `import_excel_from_file` (`tools/numbers_tools.py`)

```python
# Antes de guardar cada celda del Excel:
existing_values = get_numbers_table_values(property_id, template_key)

for cell_addr, cell_data in cell_values.items():
    normalized_addr = str(cell_addr).upper().strip()
    
    # Si el usuario ya añadió un valor via chat:
    if normalized_addr in existing_values:
        existing_val = existing_values[normalized_addr]
        existing_val_str = existing_val.get("value", "")
        
        # PRESERVAR el valor del usuario, NO sobrescribirlo con el Excel
        if existing_val_str and existing_val_str != cell_data["value"]:
            logger.info(f"Preserving user value for {normalized_addr}: '{existing_val_str}'")
            skipped_count += 1
            continue  # ← SKIP: NO sobrescribir
    
    # Solo guardar si NO hay valor del usuario
    sb.rpc("set_numbers_table_cell", {...})
```

**Logs esperados:**
```
✅ Imported 29 cells from Excel file, preserved 2 user-added values
[import_excel] Preserving user value for B5: '1000' (Excel has '')
[import_excel] Preserving user value for C5: '5' (Excel has '')
```

### 2. Mensaje Correcto en `set_numbers_template` (`tools/registry.py`)

**Antes:**
```python
return {"values_cleared": True, "imported": False}  # ❌ Confuso
```

**Después:**
```python
return {
    "values_cleared": False,  # ✅ Correcto: NO borramos valores
    "imported": False,
    "note": "Template already exists, values preserved"
}
```

## Flujo Completo

### Escenario 1: Usuario añade valores y recarga la página
1. Usuario añade B5=1000, C5=5 via chat → ✅ Guardados en DB
2. Usuario recarga la página → Frontend auto-carga template
3. Backend auto-recarga la estructura del Excel
4. `import_excel_from_file` verifica valores existentes
5. **B5 y C5 se preservan** (no se sobrescriben con valores vacíos del Excel)
6. Resultado: **Valores del usuario intactos** ✅

### Escenario 2: Usuario añade valores y sube nuevo Excel
1. Usuario añade B5=1000, C5=5 via chat → ✅ Guardados en DB
2. Usuario sube nuevo Excel R2B (con B5 y C5 vacíos)
3. `import_excel_from_file` se ejecuta
4. Detecta que B5=1000 y C5=5 ya existen en DB
5. **Preserva estos valores** (no los sobrescribe)
6. Resultado: **Valores del usuario intactos** ✅

### Escenario 3: Usuario añade valores y dice "R2B" en el chat
1. Usuario añade B5=1000, C5=5 via chat → ✅ Guardados en DB
2. Usuario dice "R2B" → `set_numbers_template` se ejecuta
3. Template ya existe → Retorna inmediatamente
4. **NO llama a `clear_numbers`** (solo se llama si NO hay estructura)
5. Mensaje: `"values_cleared": False, "note": "Template already exists, values preserved"`
6. Resultado: **Valores del usuario intactos** ✅

## Garantía

Con estos cambios, **TODOS los valores añadidos por el usuario via chat están protegidos** y NO se borrarán al:
- ✅ Recargar la página
- ✅ Subir un nuevo Excel
- ✅ Re-seleccionar la plantilla

## Testing

Para verificar que funciona:

1. Añade valores via chat: "pon 1000 en B5" y "pon 5 en C5"
2. Verifica que están en DB:
   ```bash
   curl "http://localhost:7901/api/numbers/table-values?property_id=XXX&template_key=R2B" | grep -E "B5|C5"
   ```
3. Sube un nuevo Excel R2B (vacío)
4. Verifica de nuevo:
   ```bash
   curl "http://localhost:7901/api/numbers/table-values?property_id=XXX&template_key=R2B" | grep -E "B5|C5"
   ```
5. **Resultado esperado**: B5=1000 y C5=5 siguen ahí ✅
6. Los logs mostrarán: `Preserving user value for B5: '1000'`

