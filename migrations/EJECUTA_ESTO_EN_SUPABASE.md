# 🚨 ACCIÓN REQUERIDA: Ejecutar Migración SQL

## ❌ Problema Actual
El dashboard de evaluaciones muestra **N/A** en todas las métricas porque **faltan 5 columnas en la tabla `agent_feedback`**.

```
🎯 Precisión Tools: N/A
📝 Calidad: N/A  
✅ Éxito: N/A
```

---

## ✅ Solución: 3 Pasos Simples

### **Paso 1: Abrir Supabase SQL Editor**

1. Ve a: https://supabase.com/dashboard/project/tqqvgaiueheiqtqmbpjh/sql/new
2. Si te pide login, usa tus credenciales de Supabase
3. Deberías ver una pantalla con un editor de SQL

### **Paso 2: Copiar y Pegar este SQL**

Selecciona TODO el SQL de abajo y cópialo:

```sql
-- Add evaluation score columns
ALTER TABLE public.agent_feedback 
ADD COLUMN IF NOT EXISTS tool_selection_score FLOAT,
ADD COLUMN IF NOT EXISTS response_quality_score FLOAT,
ADD COLUMN IF NOT EXISTS task_success_score FLOAT,
ADD COLUMN IF NOT EXISTS eval_reasoning JSONB,
ADD COLUMN IF NOT EXISTS eval_timestamp TIMESTAMPTZ;

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_agent_feedback_eval_timestamp 
ON public.agent_feedback (eval_timestamp DESC NULLS LAST);

-- Verify columns were added (this will show the result)
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_schema = 'public' 
  AND table_name = 'agent_feedback'
  AND column_name IN ('tool_selection_score', 'response_quality_score', 'task_success_score', 'eval_reasoning', 'eval_timestamp')
ORDER BY column_name;
```

### **Paso 3: Ejecutar (RUN)**

1. Pega el SQL en el editor
2. Haz click en el botón verde **"RUN"** (o presiona `Cmd + Enter`)
3. Deberías ver un resultado como este:

```
column_name              | data_type         | is_nullable
-------------------------|-------------------|-------------
eval_reasoning           | jsonb             | YES
eval_timestamp           | timestamp         | YES
response_quality_score   | double precision  | YES
task_success_score       | double precision  | YES
tool_selection_score     | double precision  | YES

✅ Success. 5 rows returned.
```

---

## 🎉 Verificar que Funcionó

### Automáticamente:

Después de ejecutar el SQL, el sistema empezará a guardar evaluaciones automáticamente cuando des feedback (👍/👎).

### Manual (Verificación Inmediata):

1. **Refresca el dashboard**: http://localhost:3000/dashboard/evals
2. **Da un nuevo feedback**: Ve al chat y haz click en 👍 en una respuesta
3. **Espera 5 segundos** (el pipeline tarda ~3-5 seg en evaluar)
4. **Refresca el dashboard de nuevo**
5. **Deberías ver**:
   - 🎯 Precisión Tools: 1.0 (o 0.X)
   - 📝 Calidad: 0.X - 1.0
   - ✅ Éxito: (depende de la tarea)

---

## 🔍 Troubleshooting

### "Table agent_feedback doesn't exist"

Si ves este error, primero crea la tabla ejecutando:

```sql
CREATE TABLE IF NOT EXISTS public.agent_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    user_id TEXT,
    property_id UUID,
    agent_name TEXT,
    user_input TEXT NOT NULL,
    agent_response TEXT NOT NULL,
    feedback_type TEXT NOT NULL, -- 'thumbs_up' or 'thumbs_down'
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Y luego ejecuta el SQL de arriba para agregar las columnas.

### "Permission denied"

Si no tienes permisos para ejecutar SQL:
1. Verifica que estés logueado en Supabase
2. Verifica que estés en el proyecto correcto (rama-agentic-ai)
3. Si el problema persiste, contacta al admin del proyecto

---

## 📞 ¿Necesitas Ayuda?

Si después de ejecutar el SQL el dashboard sigue mostrando N/A:

1. Comparte una captura del resultado del SQL en Supabase
2. Comparte los logs del backend (últimas 20 líneas)
3. Comparte una captura del dashboard

---

## ✅ Checklist

- [ ] He abierto Supabase SQL Editor
- [ ] He copiado y pegado el SQL completo
- [ ] He hecho click en RUN
- [ ] He visto el resultado mostrando 5 columnas
- [ ] He refrescado el dashboard
- [ ] He dado un nuevo feedback 👍 en el chat
- [ ] El dashboard ahora muestra las métricas (no más N/A)

---

**Tiempo estimado**: 2 minutos ⏱️

**Dificultad**: Muy fácil (solo copiar/pegar y click) ✨

