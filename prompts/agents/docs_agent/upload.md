# Flujo: Subir Documento

Cuando el usuario sube un archivo o pide "sube este documento"

## Proceso

### 1. Identificar destino
Pregunta al usuario si no está claro:
- ¿A qué contrato/categoría pertenece?
- ¿Es una factura? (si sí, asociarla a un contrato)

### 2. Subir
```
Llama: upload_and_link(
  property_id,
  document_group,
  document_subgroup,
  document_name,
  file_data
)
```

### 3. Verificar
```
SIEMPRE después de subir:
Llama: list_docs(property_id)
Verifica que el documento aparece con storage_key
```

### 4. Confirmar
- Si tiene storage_key: "✅ Documento subido y guardado: [nombre]"
- Si NO tiene storage_key: "⚠️ Problema guardando el documento"

