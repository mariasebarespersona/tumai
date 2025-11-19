# 📊 Logfire Dashboard Setup - RAMA AI

Este documento contiene todas las queries SQL y configuraciones para crear un dashboard completo de observability en Logfire.

---

## 🎯 **Cómo Crear el Dashboard**

1. Ve a **Logfire → Dashboards** (sidebar izquierdo)
2. Click en **"Create Dashboard"**
3. Nombre: **"RAMA AI - Production Monitoring"**
4. Para cada gráfico abajo, click **"Add Panel"** y copia la query

---

## 📊 **Gráficos del Dashboard**

### 1️⃣ **API Request Rate (Requests por Minuto)**

**Tipo de gráfico**: Time Series (Line Chart)  
**Descripción**: Muestra el volumen de requests en tiempo real

```sql
SELECT 
  date_trunc('minute', start_time) as time,
  count(*) as requests
FROM spans
WHERE 
  span_name LIKE 'POST %' 
  OR span_name LIKE 'GET %'
  OR span_name LIKE 'PUT %'
  OR span_name LIKE 'DELETE %'
GROUP BY time
ORDER BY time DESC
LIMIT 1000
```

**Configuración:**
- X-axis: `time`
- Y-axis: `requests`
- Time range: Last 1 hour
- Refresh: 30 seconds

---

### 2️⃣ **API Status Codes Distribution**

**Tipo de gráfico**: Pie Chart  
**Descripción**: Distribución de códigos de respuesta (200, 422, 500, etc.)

```sql
SELECT 
  COALESCE(CAST(attributes['http.status_code'] AS TEXT), 'unknown') as status_code,
  count(*) as count
FROM spans
WHERE 
  (span_name LIKE 'POST %' OR span_name LIKE 'GET %')
  AND start_time > now() - interval '1 hour'
GROUP BY status_code
ORDER BY count DESC
```

**Configuración:**
- Label: `status_code`
- Value: `count`
- Colors:
  - 200 → Green
  - 422 → Orange
  - 500 → Red

---

### 3️⃣ **Top 10 Slowest Endpoints**

**Tipo de gráfico**: Bar Chart (Horizontal)  
**Descripción**: Endpoints más lentos por latency promedio

```sql
SELECT 
  span_name as endpoint,
  avg(duration) as avg_latency_ms,
  count(*) as requests,
  max(duration) as max_latency_ms
FROM spans
WHERE 
  (span_name LIKE 'POST %' OR span_name LIKE 'GET %')
  AND start_time > now() - interval '1 hour'
GROUP BY endpoint
ORDER BY avg_latency_ms DESC
LIMIT 10
```

**Configuración:**
- X-axis: `avg_latency_ms`
- Y-axis: `endpoint`
- Tooltip: Include `requests` and `max_latency_ms`

---

### 4️⃣ **Error Rate Over Time**

**Tipo de gráfico**: Time Series (Area Chart)  
**Descripción**: Porcentaje de errores (4xx + 5xx) por minuto

```sql
SELECT 
  date_trunc('minute', start_time) as time,
  count(*) FILTER (WHERE CAST(attributes['http.status_code'] AS INTEGER) >= 400) as errors,
  count(*) as total,
  ROUND(
    100.0 * count(*) FILTER (WHERE CAST(attributes['http.status_code'] AS INTEGER) >= 400) / NULLIF(count(*), 0),
    2
  ) as error_rate_pct
FROM spans
WHERE 
  (span_name LIKE 'POST %' OR span_name LIKE 'GET %')
  AND start_time > now() - interval '1 hour'
GROUP BY time
ORDER BY time DESC
LIMIT 1000
```

**Configuración:**
- X-axis: `time`
- Y-axis: `error_rate_pct`
- Color: Red/Orange gradient
- Alert threshold: 5% (línea roja)

---

### 5️⃣ **P95 Latency by Endpoint**

**Tipo de gráfico**: Table  
**Descripción**: Latency percentiles por endpoint

```sql
SELECT 
  span_name as endpoint,
  count(*) as requests,
  ROUND(avg(duration), 0) as avg_ms,
  ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY duration), 0) as p50_ms,
  ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY duration), 0) as p95_ms,
  ROUND(percentile_cont(0.99) WITHIN GROUP (ORDER BY duration), 0) as p99_ms,
  max(duration) as max_ms
FROM spans
WHERE 
  (span_name LIKE 'POST %' OR span_name LIKE 'GET %')
  AND start_time > now() - interval '1 hour'
GROUP BY endpoint
ORDER BY p95_ms DESC
LIMIT 20
```

**Configuración:**
- Format columns as milliseconds
- Highlight P95 > 2000ms in orange
- Highlight P99 > 5000ms in red

---

### 6️⃣ **LLM Calls per Minute**

**Tipo de gráfico**: Time Series (Line Chart)  
**Descripción**: Volumen de llamadas a OpenAI

```sql
SELECT 
  date_trunc('minute', start_time) as time,
  count(*) as llm_calls
FROM spans
WHERE 
  span_name = 'ChatOpenAI.invoke'
  AND start_time > now() - interval '1 hour'
GROUP BY time
ORDER BY time DESC
LIMIT 1000
```

**Configuración:**
- X-axis: `time`
- Y-axis: `llm_calls`
- Color: Purple/Blue

---

### 7️⃣ **LLM Usage by Model**

**Tipo de gráfico**: Stacked Bar Chart  
**Descripción**: Distribución de calls por modelo (gpt-4o vs gpt-4o-mini)

```sql
SELECT 
  date_trunc('5 minutes', start_time) as time,
  COALESCE(attributes['llm.request.model'], 'unknown') as model,
  count(*) as calls
FROM spans
WHERE 
  span_name = 'ChatOpenAI.invoke'
  AND start_time > now() - interval '1 hour'
GROUP BY time, model
ORDER BY time DESC, calls DESC
LIMIT 1000
```

**Configuración:**
- X-axis: `time`
- Y-axis: `calls` (stacked)
- Group by: `model`
- Colors:
  - gpt-4o → Blue
  - gpt-4o-mini → Light Blue

---

### 8️⃣ **LLM Token Usage Over Time**

**Tipo de gráfico**: Time Series (Area Chart, Stacked)  
**Descripción**: Tokens consumidos (input + output) por minuto

```sql
SELECT 
  date_trunc('5 minutes', start_time) as time,
  sum(COALESCE(CAST(attributes['llm.usage.prompt_tokens'] AS INTEGER), 0)) as input_tokens,
  sum(COALESCE(CAST(attributes['llm.usage.completion_tokens'] AS INTEGER), 0)) as output_tokens,
  sum(
    COALESCE(CAST(attributes['llm.usage.prompt_tokens'] AS INTEGER), 0) +
    COALESCE(CAST(attributes['llm.usage.completion_tokens'] AS INTEGER), 0)
  ) as total_tokens
FROM spans
WHERE 
  span_name = 'ChatOpenAI.invoke'
  AND start_time > now() - interval '1 hour'
GROUP BY time
ORDER BY time DESC
LIMIT 1000
```

**Configuración:**
- X-axis: `time`
- Y-axis: `input_tokens` (green), `output_tokens` (orange)
- Stack: Yes
- Format: Number with commas

---

### 9️⃣ **LLM Cost by Model (Last Hour)**

**Tipo de gráfico**: Table  
**Descripción**: Costo detallado por modelo OpenAI

```sql
SELECT 
  COALESCE(attributes['llm.request.model'], 'unknown') as model,
  count(*) as calls,
  sum(COALESCE(CAST(attributes['llm.usage.prompt_tokens'] AS INTEGER), 0)) as prompt_tokens,
  sum(COALESCE(CAST(attributes['llm.usage.completion_tokens'] AS INTEGER), 0)) as completion_tokens,
  sum(
    COALESCE(CAST(attributes['llm.usage.prompt_tokens'] AS INTEGER), 0) +
    COALESCE(CAST(attributes['llm.usage.completion_tokens'] AS INTEGER), 0)
  ) as total_tokens,
  CASE 
    WHEN attributes['llm.request.model'] = 'gpt-4o' THEN
      ROUND(
        (sum(COALESCE(CAST(attributes['llm.usage.prompt_tokens'] AS INTEGER), 0)) * 0.0025 / 1000) +
        (sum(COALESCE(CAST(attributes['llm.usage.completion_tokens'] AS INTEGER), 0)) * 0.01 / 1000),
        4
      )
    WHEN attributes['llm.request.model'] = 'gpt-4o-mini' THEN
      ROUND(
        (sum(COALESCE(CAST(attributes['llm.usage.prompt_tokens'] AS INTEGER), 0)) * 0.00015 / 1000) +
        (sum(COALESCE(CAST(attributes['llm.usage.completion_tokens'] AS INTEGER), 0)) * 0.0006 / 1000),
        4
      )
    ELSE 0
  END as cost_usd
FROM spans
WHERE 
  span_name = 'ChatOpenAI.invoke'
  AND start_time > now() - interval '1 hour'
GROUP BY model
ORDER BY cost_usd DESC
```

**Configuración:**
- Format `cost_usd` as currency ($)
- Format tokens with commas
- Bold the cost column

---

### 🔟 **LLM Cost Over Time (Cumulative)**

**Tipo de gráfico**: Time Series (Line Chart)  
**Descripción**: Gasto acumulado en OpenAI por hora

```sql
SELECT 
  date_trunc('hour', start_time) as time,
  sum(
    CASE 
      WHEN attributes['llm.request.model'] = 'gpt-4o' THEN
        (COALESCE(CAST(attributes['llm.usage.prompt_tokens'] AS INTEGER), 0) * 0.0025 / 1000) +
        (COALESCE(CAST(attributes['llm.usage.completion_tokens'] AS INTEGER), 0) * 0.01 / 1000)
      WHEN attributes['llm.request.model'] = 'gpt-4o-mini' THEN
        (COALESCE(CAST(attributes['llm.usage.prompt_tokens'] AS INTEGER), 0) * 0.00015 / 1000) +
        (COALESCE(CAST(attributes['llm.usage.completion_tokens'] AS INTEGER), 0) * 0.0006 / 1000)
      ELSE 0
    END
  ) as cost_usd
FROM spans
WHERE 
  span_name = 'ChatOpenAI.invoke'
  AND start_time > now() - interval '24 hours'
GROUP BY time
ORDER BY time DESC
```

**Configuración:**
- X-axis: `time`
- Y-axis: `cost_usd`
- Format: Currency ($)
- Color: Green

---

### 1️⃣1️⃣ **Agent Performance Comparison**

**Tipo de gráfico**: Table  
**Descripción**: Comparación de performance entre agentes especializados

```sql
SELECT 
  COALESCE(attributes['agent'], 'MainAgent') as agent_name,
  count(DISTINCT attributes['property_id']) as properties_handled,
  count(*) as total_calls,
  ROUND(avg(duration), 0) as avg_latency_ms,
  count(*) FILTER (WHERE attributes['action'] = 'complete') as completed,
  count(*) FILTER (WHERE attributes['action'] = 'redirect') as redirected,
  count(*) FILTER (WHERE attributes['action'] = 'error') as errors,
  ROUND(
    100.0 * count(*) FILTER (WHERE attributes['action'] = 'complete') / NULLIF(count(*), 0),
    1
  ) as success_rate_pct
FROM spans
WHERE 
  span_name LIKE '%Agent.run'
  AND start_time > now() - interval '1 hour'
GROUP BY agent_name
ORDER BY total_calls DESC
```

**Configuración:**
- Format `success_rate_pct` as percentage
- Highlight errors > 0 in red
- Highlight success_rate < 90% in orange

---

### 1️⃣2️⃣ **Router Decision Breakdown**

**Tipo de gráfico**: Pie Chart  
**Descripción**: A qué agente rutea el router más frecuentemente

```sql
SELECT 
  COALESCE(attributes['intent'], 'unknown') as intent,
  count(*) as count
FROM spans
WHERE 
  span_name = 'route_decision'
  AND start_time > now() - interval '1 hour'
GROUP BY intent
ORDER BY count DESC
LIMIT 10
```

**Configuración:**
- Label: `intent`
- Value: `count`
- Show percentages

---

### 1️⃣3️⃣ **Supabase Operations**

**Tipo de gráfico**: Time Series (Stacked Area)  
**Descripción**: Operaciones a la base de datos

```sql
SELECT 
  date_trunc('5 minutes', start_time) as time,
  CASE 
    WHEN span_name LIKE '%insert%' THEN 'INSERT'
    WHEN span_name LIKE '%update%' THEN 'UPDATE'
    WHEN span_name LIKE '%select%' THEN 'SELECT'
    WHEN span_name LIKE '%delete%' THEN 'DELETE'
    ELSE 'OTHER'
  END as operation_type,
  count(*) as operations
FROM spans
WHERE 
  span_name LIKE 'supabase%'
  AND start_time > now() - interval '1 hour'
GROUP BY time, operation_type
ORDER BY time DESC
LIMIT 1000
```

**Configuración:**
- X-axis: `time`
- Y-axis: `operations` (stacked)
- Group by: `operation_type`

---

### 1️⃣4️⃣ **Email Sending Activity**

**Tipo de gráfico**: Stat Panel (Single Number)  
**Descripción**: Total de emails enviados en la última hora

```sql
SELECT 
  count(*) as emails_sent
FROM spans
WHERE 
  span_name = 'email_sent'
  AND start_time > now() - interval '1 hour'
```

**Configuración:**
- Display as big number
- Icon: ✉️
- Color: Blue

---

### 1️⃣5️⃣ **Numbers Table Operations**

**Tipo de gráfico**: Time Series (Bar Chart)  
**Descripción**: Actividad en la tabla de números R2B

```sql
SELECT 
  date_trunc('5 minutes', start_time) as time,
  count(*) FILTER (WHERE span_name = 'numbers_cell_updated') as cell_updates,
  count(*) FILTER (WHERE span_name LIKE '%import%template%') as template_imports,
  count(*) FILTER (WHERE span_name LIKE '%export%') as exports
FROM spans
WHERE 
  (span_name = 'numbers_cell_updated' 
   OR span_name LIKE '%import%template%'
   OR span_name LIKE '%export%')
  AND start_time > now() - interval '1 hour'
GROUP BY time
ORDER BY time DESC
LIMIT 1000
```

**Configuración:**
- X-axis: `time`
- Y-axis: Multiple series
- Legend: `cell_updates`, `template_imports`, `exports`

---

## 🎨 **Layout del Dashboard**

Organiza los paneles en este orden (de arriba a abajo, izquierda a derecha):

```
┌────────────────────────────────────────────────────┐
│  🎯 API Request Rate (full width)                  │
├─────────────────────┬──────────────────────────────┤
│  Status Codes       │  Error Rate Over Time        │
│  (pie chart)        │  (area chart)                │
├─────────────────────┴──────────────────────────────┤
│  Top 10 Slowest Endpoints (full width)             │
├─────────────────────┬──────────────────────────────┤
│  P95 Latency Table  │  Agent Performance Table     │
├─────────────────────┴──────────────────────────────┤
│  🤖 LLM Calls per Minute (full width)              │
├─────────────────────┬──────────────────────────────┤
│  LLM by Model       │  Router Decision Breakdown   │
│  (stacked bar)      │  (pie chart)                 │
├─────────────────────┴──────────────────────────────┤
│  Token Usage Over Time (full width, stacked area)  │
├─────────────────────┬──────────────────────────────┤
│  LLM Cost Table     │  LLM Cost Over Time          │
├─────────────────────┼──────────────────────────────┤
│  Emails Sent        │  Numbers Table Ops           │
│  (stat)             │  (bar chart)                 │
└─────────────────────┴──────────────────────────────┘
```

---

## 🔔 **Alertas Recomendadas**

Después de crear el dashboard, configura estas alertas:

### Alert 1: High Error Rate
```sql
SELECT 
  ROUND(
    100.0 * count(*) FILTER (WHERE CAST(attributes['http.status_code'] AS INTEGER) >= 400) / NULLIF(count(*), 0),
    2
  ) as error_rate_pct
FROM spans
WHERE 
  (span_name LIKE 'POST %' OR span_name LIKE 'GET %')
  AND start_time > now() - interval '5 minutes'
```
**Condition**: `error_rate_pct > 5`  
**Action**: Send email / Slack notification

### Alert 2: High LLM Cost
```sql
SELECT 
  sum(
    CASE 
      WHEN attributes['llm.request.model'] = 'gpt-4o' THEN
        (COALESCE(CAST(attributes['llm.usage.prompt_tokens'] AS INTEGER), 0) * 0.0025 / 1000) +
        (COALESCE(CAST(attributes['llm.usage.completion_tokens'] AS INTEGER), 0) * 0.01 / 1000)
      WHEN attributes['llm.request.model'] = 'gpt-4o-mini' THEN
        (COALESCE(CAST(attributes['llm.usage.prompt_tokens'] AS INTEGER), 0) * 0.00015 / 1000) +
        (COALESCE(CAST(attributes['llm.usage.completion_tokens'] AS INTEGER), 0) * 0.0006 / 1000)
      ELSE 0
    END
  ) as cost_usd
FROM spans
WHERE 
  span_name = 'ChatOpenAI.invoke'
  AND start_time > now() - interval '1 hour'
```
**Condition**: `cost_usd > 10`  
**Action**: Send email notification

### Alert 3: High P95 Latency
```sql
SELECT 
  ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY duration), 0) as p95_ms
FROM spans
WHERE 
  (span_name LIKE 'POST %' OR span_name LIKE 'GET %')
  AND start_time > now() - interval '5 minutes'
```
**Condition**: `p95_ms > 3000`  
**Action**: Slack notification

---

## 🧪 **Testing del Dashboard**

Después de crear el dashboard:

1. **Genera tráfico de prueba**:
```bash
# Hacer varias requests
for i in {1..10}; do
  curl -X POST http://localhost:7901/ui_chat \
    -H "Content-Type: application/json" \
    -d "{\"user_input\": \"test $i\", \"session_id\": \"test\"}"
  sleep 1
done
```

2. **Verifica que todos los gráficos muestran datos**
3. **Ajusta los time ranges** si es necesario (1h, 6h, 24h)
4. **Configura auto-refresh** a 30 segundos

---

## 📝 **Notas Importantes**

### Sobre los Atributos de Logfire

Logfire puede usar diferentes nombres para los atributos dependiendo de la versión. Si una query no funciona, ajusta:

**En vez de:**
```sql
attributes['llm.request.model']
```

**Prueba:**
```sql
attributes['gen_ai.request.model']
-- o --
attributes.llm.request.model
-- o --
attributes->>'llm.request.model'
```

### Pricing de OpenAI (Actualizado Nov 2024)

Las queries usan estos precios:
- **gpt-4o**: $2.50 input / $10 output (per 1M tokens)
- **gpt-4o-mini**: $0.15 input / $0.60 output (per 1M tokens)

Si OpenAI cambia precios, actualiza los valores en las queries 9 y 10.

---

## 🚀 **Próximos Pasos**

1. Crear el dashboard con las queries de arriba
2. Ajustar time ranges según tu necesidad
3. Configurar alertas
4. Compartir el dashboard con tu equipo (Logfire permite compartir URLs)

---

¡Dashboard listo para producción! 🎉

