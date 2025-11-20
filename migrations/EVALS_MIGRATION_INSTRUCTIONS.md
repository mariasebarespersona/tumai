# 🔧 Migración de Evaluaciones - Instrucciones

## ❌ Problema Actual

El dashboard de evaluaciones muestra `N/A` en las métricas de **Precisión Tools**, **Calidad**, y **Éxito** porque faltan las columnas necesarias en la tabla `agent_feedback`.

Error en los logs:
```
Could not find the 'eval_reasoning' column of 'agent_feedback' in the schema cache
```

---

## ✅ Solución: Ejecutar Migración SQL

### Paso 1: Ir a Supabase SQL Editor

1. Ve a https://supabase.com/dashboard
2. Selecciona tu proyecto: **rama-agentic-ai**
3. En el menú izquierdo, haz click en **SQL Editor**
4. Click en **New Query** (botón verde)

### Paso 2: Ejecutar el Script de Migración

Copia y pega **TODO** el contenido del archivo:
```
migrations/add_eval_columns_to_feedback.sql
```

O copia directamente este SQL:

```sql
-- Add evaluation score columns
ALTER TABLE public.agent_feedback 
ADD COLUMN IF NOT EXISTS tool_selection_score FLOAT,
ADD COLUMN IF NOT EXISTS response_quality_score FLOAT,
ADD COLUMN IF NOT EXISTS task_success_score FLOAT,
ADD COLUMN IF NOT EXISTS eval_reasoning JSONB,
ADD COLUMN IF NOT EXISTS eval_timestamp TIMESTAMPTZ;

-- Create index for faster queries on eval_timestamp
CREATE INDEX IF NOT EXISTS idx_agent_feedback_eval_timestamp 
ON public.agent_feedback (eval_timestamp DESC NULLS LAST);

-- Verify columns were added
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public' 
  AND table_name = 'agent_feedback'
  AND column_name IN ('tool_selection_score', 'response_quality_score', 'task_success_score', 'eval_reasoning', 'eval_timestamp')
ORDER BY ordinal_position;
```

### Paso 3: Ejecutar

Haz click en **Run** (o presiona `Cmd + Enter`)

Deberías ver un resultado mostrando las 5 columnas nuevas:
```
column_name              | data_type         | is_nullable
-------------------------|-------------------|-------------
tool_selection_score     | double precision  | YES
response_quality_score   | double precision  | YES
task_success_score       | double precision  | YES
eval_reasoning           | jsonb             | YES
eval_timestamp           | timestamp         | YES
```

---

## 🧪 Paso 4: Verificar que Funciona

### 4.1 Dar Feedback a una Respuesta del Agente

1. Ve al chat: http://localhost:3000
2. Haz una pregunta al agente (ej: "muéstrame las propiedades")
3. Cuando el agente responda, haz click en **👍** (thumbs up)

### 4.2 Verificar Logs del Backend

En los logs deberías ver:
```
✅ [eval_pipeline] Evaluation complete for feedback <feedback_id>
```

**NO** deberías ver este error:
```
❌ Could not find the 'eval_reasoning' column
```

### 4.3 Verificar el Dashboard

1. Ve al dashboard de evaluaciones: http://localhost:3000/dashboard/evals
2. Selecciona **Últimas 24h** en el dropdown
3. Deberías ver:
   - **Satisfacción**: 100% (o el % correspondiente)
   - **Precisión Tools**: 0.X - 1.0 (ya no "N/A")
   - **Calidad**: 0.X - 1.0 (ya no "N/A")
   - **Éxito**: Depende de las tareas verificables

---

## 🔍 Verificación Adicional (Opcional)

Ejecuta esta query en Supabase SQL Editor para ver los datos guardados:

```sql
SELECT 
    id,
    agent_name,
    feedback_type,
    tool_selection_score,
    response_quality_score,
    task_success_score,
    eval_timestamp,
    created_at
FROM public.agent_feedback
WHERE eval_timestamp IS NOT NULL
ORDER BY created_at DESC
LIMIT 10;
```

Deberías ver filas con valores en `tool_selection_score` y `response_quality_score`.

---

## ❓ Troubleshooting

### Problema: "Table agent_feedback doesn't exist"

**Solución**: Primero ejecuta la migración que crea la tabla:
```
migrations/2025-01-21_agent_feedback.sql
```

### Problema: Todavía veo N/A en el dashboard

**Posibles causas**:
1. **No has dado feedback aún** → Da click en 👍 o 👎 en una respuesta del agente
2. **El backend no se ha reiniciado** → Reinicia el backend con `pkill -9 -f "python.*app.py" && python3 app.py`
3. **Cache del navegador** → Refresca la página con `Cmd + Shift + R` (Mac) o `Ctrl + Shift + R` (Windows)
4. **Las evaluaciones no se ejecutaron** → Revisa los logs del backend para confirmar que el pipeline se ejecuta sin errores

---

## ✅ Checklist

- [ ] He ejecutado el SQL en Supabase SQL Editor
- [ ] He verificado que las 5 columnas se crearon correctamente
- [ ] He reiniciado el backend (si estaba corriendo)
- [ ] He dado feedback (👍 o 👎) a una respuesta del agente
- [ ] He verificado los logs del backend (no hay errores de columnas faltantes)
- [ ] El dashboard muestra las métricas correctamente (no más N/A)

---

Si sigues teniendo problemas después de seguir estos pasos, comparte los logs del backend y una captura del dashboard.

