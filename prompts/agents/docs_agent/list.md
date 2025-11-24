# Flujo: Listar Documentos

Cuando el usuario pide "lista documentos", "muéstrame documentos", "ver documentos", etc.

## Proceso

### 1. Llamar herramienta
```
SIEMPRE llama: list_docs(property_id)
NO respondas basándote en memoria
```

### 2. Interpretar resultado
- Si `storage_key` tiene valor → documento SUBIDO ✅
- Si `storage_key` está vacío/null → documento PENDIENTE ⏳

### 3. Formatear respuesta
```
📄 Documentos de la propiedad:

**Documentos subidos:**

**[document_group]**
- [document_subgroup]: [document_name] ✅

**Documentos pendientes:**

**[document_group]**
- [document_subgroup]: [document_name] ⏳
```

## Reglas importantes
✅ Muestra TODOS los documentos (no filtres)
✅ Agrupa por document_group
✅ Indica status con emoji (✅ subido, ⏳ pendiente)
❌ NO omitas documentos pendientes

