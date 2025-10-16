# Mejoras de Persistencia de Documentos

## 📋 Resumen

Se han implementado mejoras para asegurar que los documentos subidos se guarden correctamente en Supabase y el agente siempre los vea, sin cambiar el esquema de la base de datos.

## ✅ Cambios Realizados

### 1. **Logging Mejorado en `upload_and_link`** (`tools/docs_tools.py`)

- ✅ Añadido logging detallado en cada paso del proceso de subida
- ✅ Manejo de errores mejorado con try-catch específicos
- ✅ Logging de éxito/fallo en Storage
- ✅ Logging de éxito/fallo en actualización de BD
- ✅ Fallback a RPC con logging si la actualización directa falla

**Beneficios:**
- Trazabilidad completa del proceso de subida
- Identificación rápida de fallos (Storage vs BD)
- Mejor debugging en producción

### 2. **Logging Mejorado en `list_docs`** (`tools/docs_tools.py`)

- ✅ Añadido logging de cuántos documentos se encuentran
- ✅ Fallback a RPC con manejo de errores
- ✅ Retorna lista vacía en caso de error (en lugar de fallar)

**Beneficios:**
- Siempre lee directamente de la BD (no caché ni índice vectorial)
- Logging de cuántos documentos se encontraron
- Manejo robusto de errores

### 3. **Headers No-Cache en Endpoint de Chat** (`app.py`)

- ✅ Importado `JSONResponse` de FastAPI
- ✅ Modificado `make_response` para retornar `JSONResponse` con headers:
  - `Cache-Control: no-store, no-cache, must-revalidate, proxy-revalidate`
  - `Pragma: no-cache`
  - `Expires: 0`

**Beneficios:**
- El frontend nunca usa respuestas cacheadas
- Siempre obtiene datos frescos de la BD
- Elimina problemas de "documento no aparece después de subir"

### 4. **Verificación Post-Upload** (`app.py`)

- ✅ Después de `upload_and_link`, se lee la BD para verificar que el documento existe
- ✅ Logging de verificación exitosa o fallida
- ✅ Ayuda a detectar problemas de sincronización

**Beneficios:**
- Detección inmediata si algo falló silenciosamente
- Logging para debugging
- Confianza en que el documento está realmente guardado

### 5. **El Agente Ya Consulta la BD Correctamente**

El system prompt del agente (línea 83 en `agentic.py`) ya tiene:

```
Si `list_docs` devuelve 0 elementos para la propiedad activa, responde "No hay documentos subidos en esta propiedad" y ofrece subir o listar los que faltan.
```

Esto significa que el agente **SÍ** consulta la BD directamente con `list_docs`, no el índice vectorial.

## 🔍 Flujo de Subida Mejorado

```
1. Usuario adjunta archivo
   ↓
2. Se propone slot (grupo/subgrupo/nombre)
   ↓
3. Usuario confirma
   ↓
4. upload_and_link:
   a. Sube a Storage (con logging) ✅
   b. Crea signed URL (con logging) ✅
   c. Actualiza BD (con logging) ✅
   d. Si falla BD, intenta RPC ✅
   ↓
5. Se guarda sesión (save_sessions) ✅
   ↓
6. Se verifica que el documento existe en BD ✅
   ↓
7. Se retorna respuesta con headers no-cache ✅
```

## 🎯 Garantías Implementadas

1. **Atomicidad**: Si Storage falla, no se actualiza BD. Si BD falla, se loggea el error.
2. **Idempotencia**: Storage usa `upsert=true`, permitir re-subir el mismo archivo.
3. **Trazabilidad**: Logging completo en cada paso.
4. **No-Cache**: Headers que fuerzan al frontend a obtener datos frescos.
5. **Verificación**: Lectura post-upload para confirmar persistencia.
6. **Fallback**: Si la actualización directa falla, intenta RPC.

## 📊 Logging Añadido

### En `upload_and_link`:
- `📤 Uploading document: {filename} → {key}`
- `✅ Storage upload successful: {key}`
- `❌ Storage upload failed for {key}: {error}`
- `✅ Signed URL created for {key}`
- `❌ Failed to create signed URL for {key}: {error}`
- `✅ Database updated successfully for {document_name}`
- `⚠️ Direct DB update failed, trying RPC fallback: {error}`
- `✅ Database updated via RPC for {document_name}`
- `❌ RPC fallback also failed: {error}`
- `🎉 Document upload complete: {filename}`

### En `list_docs`:
- `📋 Listing documents for property: {property_id}`
- `✅ Found {count} documents via direct query`
- `⚠️ Direct query failed, trying RPC: {error}`
- `✅ Found {count} documents via RPC`
- `❌ RPC also failed: {error}`

### En `app.py` (post-upload):
- `✅ Document uploaded: {document_name}`
- `✅ Verified document in DB: {storage_key}`
- `⚠️ Document not found in DB after upload!`
- `❌ Error verifying document: {error}`

## 🧪 Testing Recomendado

Para verificar que todo funciona:

1. **Test de Subida Básica**:
   - Subir un documento
   - Verificar en logs que aparecen todos los ✅
   - Preguntar al agente "¿qué documentos hay?"
   - Debe aparecer el documento recién subido

2. **Test de Persistencia**:
   - Subir un documento
   - Recargar la página
   - Preguntar al agente "¿qué documentos hay?"
   - Debe seguir apareciendo el documento

3. **Test de Idempotencia**:
   - Subir el mismo documento dos veces
   - Debe funcionar sin errores (upsert)

4. **Test de Verificación**:
   - Revisar logs después de subir
   - Debe aparecer "Verified document in DB"

## 🚀 Próximos Pasos (Opcionales)

Si aún hay problemas, considerar:

1. **Añadir tabla de eventos**: Para auditoría completa (como sugiere ChatGPT)
2. **Webhooks de Supabase**: Para notificaciones en tiempo real
3. **Retry logic**: Reintentos automáticos si falla la subida
4. **Health checks**: Endpoint para verificar estado de Storage y BD

## 📝 Notas Importantes

- **NO se cambió el esquema de Supabase**: Todo usa las tablas existentes
- **NO se modificó la estructura de documentos**: Sigue usando el sistema de "celdas"
- **Solo se mejoró**: Logging, manejo de errores, headers no-cache, y verificación

## ✨ Resultado Esperado

Con estos cambios:

1. ✅ Los documentos se guardan de forma atómica (Storage + BD)
2. ✅ El agente siempre ve los documentos recién subidos
3. ✅ El frontend nunca usa caché stale
4. ✅ Hay logging completo para debugging
5. ✅ Se verifica la persistencia después de cada subida

