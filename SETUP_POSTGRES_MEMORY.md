# 🔧 Setup PostgreSQL Memory para RAMA AI

## ✅ Paso 1: Completado
- ✅ Instalado `langgraph-checkpoint-postgres`
- ✅ Actualizado `agentic.py` para usar PostgresSaver

## 📝 Paso 2: Añadir DATABASE_URL a .env

### Obtener la Contraseña de Supabase:

1. Ve a tu dashboard de Supabase: https://supabase.com/dashboard
2. Selecciona tu proyecto: `tqqvgaiueheiqtqmbpjh`
3. Ve a **Settings** (⚙️) → **Database**
4. Busca la sección **Connection string**
5. Copia la contraseña (o usa "Reset database password" si no la tienes)

### Añadir al .env:

Abre el archivo `.env` y añade esta línea (reemplaza `[TU-CONTRASEÑA]` con tu contraseña real):

```bash
DATABASE_URL=postgresql://postgres:[TU-CONTRASEÑA]@db.tqqvgaiueheiqtqmbpjh.supabase.co:5432/postgres
```

**Ejemplo:**
```bash
DATABASE_URL=postgresql://postgres:mi_contraseña_super_secreta@db.tqqvgaiueheiqtqmbpjh.supabase.co:5432/postgres
```

## 🚀 Paso 3: Reiniciar el Backend

Después de añadir DATABASE_URL:

```bash
# Detener el backend actual
pkill -f "python.*app.py"

# Iniciar de nuevo
python3 app.py
```

Deberías ver este mensaje:
```
✅ Using PostgreSQL checkpointer for persistent memory
✅ Database: db.tqqvgaiueheiqtqmbpjh.supabase.co:5432/postgres
```

## 🎯 ¿Qué hace esto?

### Tablas Creadas Automáticamente:

PostgresSaver creará estas tablas en tu Supabase:

1. **`checkpoints`**: Guarda el estado completo de cada conversación
   - `thread_id`: ID de la sesión (ej: "web-ui")
   - `checkpoint_id`: ID único del checkpoint
   - `parent_checkpoint_id`: Para navegación histórica
   - `checkpoint`: Estado serializado del agente
   - `metadata`: Información adicional

2. **`checkpoint_writes`**: Guarda escrituras intermedias
   - Para estados parciales durante la ejecución
   - Útil para debugging y rollback

### Beneficios:

- ✅ **Persistencia real**: Las conversaciones sobreviven reinicios del servidor
- ✅ **Escalabilidad**: Múltiples instancias pueden compartir el mismo estado
- ✅ **Backups**: Supabase hace backups automáticos
- ✅ **Auditoría**: Puedes consultar el historial con SQL
- ✅ **Rollback**: Puedes volver a estados anteriores

## 🧪 Probar que Funciona:

1. **Inicia una conversación**:
   - "Que propiedades hay?"
   - "entra en casa demo 6"

2. **Reinicia el backend**:
   ```bash
   pkill -f "python.*app.py"
   python3 app.py
   ```

3. **Continúa la conversación**:
   - "que documentos he subido ya?"
   - El agente debería recordar que estás en Casa Demo 6

## 🔍 Verificar en Supabase:

Puedes ver las conversaciones guardadas ejecutando este SQL en Supabase:

```sql
-- Ver todas las sesiones activas
SELECT 
    thread_id,
    checkpoint_id,
    created_at,
    metadata
FROM checkpoints
ORDER BY created_at DESC
LIMIT 10;

-- Ver el contenido de una sesión específica
SELECT 
    thread_id,
    checkpoint_id,
    checkpoint->>'messages' as messages
FROM checkpoints
WHERE thread_id = 'web-ui'
ORDER BY created_at DESC
LIMIT 1;
```

## ⚠️ Troubleshooting:

### Error: "could not connect to server"
- Verifica que la contraseña sea correcta
- Verifica que el proyecto de Supabase esté activo
- Verifica que no haya firewall bloqueando el puerto 5432

### Error: "permission denied for schema public"
- Usa el usuario `postgres` (no `anon`)
- Verifica que la contraseña sea la del usuario `postgres`

### El agente sigue sin recordar
- Verifica que veas el mensaje "✅ Using PostgreSQL checkpointer"
- Verifica que `thread_id` sea consistente ("web-ui" por defecto)
- Revisa los logs para ver si hay errores de conexión

## 📚 Recursos:

- [LangGraph Checkpointers Docs](https://langchain-ai.github.io/langgraph/reference/checkpoints/)
- [Supabase Database Docs](https://supabase.com/docs/guides/database)
- [PostgreSQL Connection Strings](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)

---

**¿Necesitas ayuda?** Revisa los logs del backend para ver mensajes de error específicos.

