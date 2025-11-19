# ⚡ Logfire Dashboard - Configuración Rápida (Copy-Paste)

Este documento tiene las configuraciones exactas para cada panel. **Copia y pega** directamente en Logfire.

---

## 🎯 **Panel 1: API Request Rate**

**Query:**
```sql
SELECT date_trunc('minute', start_timestamp) as time, count(*) as requests GROUP BY 1 ORDER BY 1 DESC LIMIT 1000
```

**Configuración:**
- Title: `API Request Rate`
- Type: `Time Series` o `Line Chart`
- X-axis: `time`
- Y-axis: `requests`
- Time range: Last 1 hour

---

## 🎯 **Panel 2: LLM Calls per Minute**

**Query:**
```sql
SELECT date_trunc('minute', start_timestamp) as time, count(*) as llm_calls WHERE span_name LIKE '%openai%' OR span_name LIKE '%ChatOpenAI%' GROUP BY 1 ORDER BY 1 DESC LIMIT 1000
```

**Configuración:**
- Title: `LLM Calls per Minute`
- Type: `Time Series`
- X-axis: `time`
- Y-axis: `llm_calls`
- Color: Purple/Blue

---

## 🎯 **Panel 3: Total Requests (Stat)**

**Query:**
```sql
SELECT count(*) as total
```

**Configuración:**
- Title: `Total Requests`
- Type: `Stat` o `Single Stat`
- Value field: `total`
- Format: Number

---

## 🎯 **Panel 4: Status Codes Distribution**

**Query:**
```sql
SELECT COALESCE(CAST(attributes['http.status_code'] AS TEXT), 'unknown') as status, count(*) as count GROUP BY 1 ORDER BY 2 DESC
```

**Configuración:**
- Title: `Status Codes`
- Type: `Pie Chart`
- Label field: `status`
- Value field: `count`

---

## 🎯 **Panel 5: Error Rate**

**Query:**
```sql
SELECT date_trunc('minute', start_timestamp) as time, (count(*) FILTER (WHERE CAST(attributes['http.status_code'] AS INTEGER) >= 400) * 100.0 / count(*)) as error_rate GROUP BY 1 ORDER BY 1 DESC LIMIT 1000
```

**Configuración:**
- Title: `Error Rate %`
- Type: `Time Series` o `Area Chart`
- X-axis: `time`
- Y-axis: `error_rate`
- Color: Red/Orange

---

## 🎯 **Panel 6: Top Endpoints**

**Query:**
```sql
SELECT span_name as endpoint, count(*) as count, ROUND(avg(duration), 0) as avg_ms GROUP BY 1 ORDER BY 2 DESC LIMIT 10
```

**Configuración:**
- Title: `Top 10 Endpoints`
- Type: `Table`
- Columns: `endpoint`, `count`, `avg_ms`

---

## 🎯 **Panel 7: LLM Token Usage**

**Query:**
```sql
SELECT date_trunc('5 minutes', start_timestamp) as time, sum(CAST(COALESCE(attributes['llm.usage.prompt_tokens'], attributes['gen_ai.usage.prompt_tokens'], '0') AS INTEGER)) as input_tokens, sum(CAST(COALESCE(attributes['llm.usage.completion_tokens'], attributes['gen_ai.usage.completion_tokens'], '0') AS INTEGER)) as output_tokens WHERE span_name LIKE '%openai%' GROUP BY 1 ORDER BY 1 DESC LIMIT 1000
```

**Configuración:**
- Title: `Token Usage (Input vs Output)`
- Type: `Stacked Area Chart`
- X-axis: `time`
- Y-axis: `input_tokens` (green), `output_tokens` (orange)

---

## 🎯 **Panel 8: LLM Cost (Last Hour)**

**Query:**
```sql
SELECT COALESCE(attributes['llm.request.model'], 'unknown') as model, count(*) as calls, sum(CAST(COALESCE(attributes['llm.usage.prompt_tokens'], '0') AS INTEGER)) as prompt_tokens, sum(CAST(COALESCE(attributes['llm.usage.completion_tokens'], '0') AS INTEGER)) as completion_tokens, CASE WHEN attributes['llm.request.model'] = 'gpt-4o' THEN ROUND((sum(CAST(COALESCE(attributes['llm.usage.prompt_tokens'], '0') AS INTEGER)) * 0.0025 / 1000) + (sum(CAST(COALESCE(attributes['llm.usage.completion_tokens'], '0') AS INTEGER)) * 0.01 / 1000), 4) WHEN attributes['llm.request.model'] = 'gpt-4o-mini' THEN ROUND((sum(CAST(COALESCE(attributes['llm.usage.prompt_tokens'], '0') AS INTEGER)) * 0.00015 / 1000) + (sum(CAST(COALESCE(attributes['llm.usage.completion_tokens'], '0') AS INTEGER)) * 0.0006 / 1000), 4) ELSE 0 END as cost_usd WHERE span_name LIKE '%openai%' GROUP BY 1 ORDER BY 5 DESC
```

**Configuración:**
- Title: `LLM Cost by Model`
- Type: `Table`
- Columns: `model`, `calls`, `prompt_tokens`, `completion_tokens`, `cost_usd`
- Format `cost_usd`: Currency ($)

---

## 🎯 **Panel 9: Agent Performance**

**Query:**
```sql
SELECT COALESCE(attributes['agent'], 'MainAgent') as agent, count(*) as calls, ROUND(avg(duration), 0) as avg_ms, count(*) FILTER (WHERE attributes['action'] = 'complete') as completed, count(*) FILTER (WHERE attributes['action'] = 'error') as errors GROUP BY 1 ORDER BY 2 DESC
```

**Configuración:**
- Title: `Agent Performance`
- Type: `Table`
- Columns: `agent`, `calls`, `avg_ms`, `completed`, `errors`

---

## 🎯 **Panel 10: Emails Sent**

**Query:**
```sql
SELECT count(*) as total WHERE span_name LIKE '%email%' OR attributes['to'] IS NOT NULL
```

**Configuración:**
- Title: `Emails Sent`
- Type: `Stat`
- Value field: `total`
- Icon: ✉️

---

## 📝 **Queries Alternativas (Si hay errores)**

### Si `start_timestamp` no existe, usa:
```sql
-- Reemplaza start_timestamp por:
timestamp
-- o
start_time
```

### Si `FILTER` no funciona, usa:
```sql
-- Reemplaza:
count(*) FILTER (WHERE condition)
-- Por:
sum(CASE WHEN condition THEN 1 ELSE 0 END)
```

### Si `attributes['field']` no funciona, prueba:
```sql
-- Reemplaza:
attributes['llm.request.model']
-- Por:
attributes.llm.request.model
-- o
get_json_object(attributes, '$.llm.request.model')
```

---

## ⚡ **Método Rápido: Crear los 3 Más Importantes**

Si solo quieres empezar rápido, crea estos 3:

### **1. Request Rate**
```sql
SELECT date_trunc('minute', start_timestamp) as time, count(*) as requests GROUP BY 1 ORDER BY 1 DESC LIMIT 1000
```
Type: Time Series

### **2. LLM Calls**
```sql
SELECT date_trunc('minute', start_timestamp) as time, count(*) as llm_calls WHERE span_name LIKE '%openai%' GROUP BY 1 ORDER BY 1 DESC LIMIT 1000
```
Type: Time Series

### **3. Total Count**
```sql
SELECT count(*) as total
```
Type: Stat

---

## 🧪 **Testing: Generar Datos**

```bash
cd /Users/mariasebares/Documents/RAMA_AI/rama-agentic-ai

# Generar tráfico
for i in {1..20}; do
  curl -X POST http://localhost:7901/ui_chat \
    -H "Content-Type: application/json" \
    -d "{\"user_input\": \"test $i\", \"session_id\": \"dashboard\"}"
  sleep 2
done
```

---

## 💡 **Tips para Crear Paneles Rápido**

1. **Abre Logfire** → Dashboards → New Dashboard
2. **Para cada panel**:
   - Click "Add Panel"
   - Copia la query de arriba
   - Pégala en el query editor
   - Selecciona el tipo de visualización
   - Configura X/Y axis
   - Save
3. **Repite** para cada uno

**Tiempo estimado**: 15-20 minutos para crear los 10 paneles

---

## 📋 **Checklist**

- [ ] Panel 1: API Request Rate (5 min)
- [ ] Panel 2: LLM Calls (3 min)
- [ ] Panel 3: Total Requests (2 min)
- [ ] Panel 4: Status Codes (3 min)
- [ ] Panel 5: Error Rate (3 min)
- [ ] Panel 6: Top Endpoints (2 min)
- [ ] Panel 7: Token Usage (3 min)
- [ ] Panel 8: LLM Cost (3 min)
- [ ] Panel 9: Agent Performance (3 min)
- [ ] Panel 10: Emails Sent (2 min)

**Total**: ~30 minutos para un dashboard completo 🚀

