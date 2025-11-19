# 🔥 Logfire Observability Setup

Logfire proporciona **observability completa** de tu aplicación RAMA AI, incluyendo:
- 🌐 **API Monitoring**: Todas las requests de FastAPI
- 🤖 **LLM Tracking**: OpenAI calls con tokens, cost, prompts completos
- ⚡ **Tracing**: Request flows completos (API → Agent → Tools → LLM)
- 💰 **Cost Analytics**: Cuánto gastas en OpenAI por endpoint/agente

---

## 1️⃣ Setup Inicial (5 minutos)

### Paso 1: Crear cuenta en Logfire

1. Ve a **https://logfire.pydantic.dev**
2. Sign up (gratis - 100K spans/mes incluidos)
3. Crea un proyecto: **"rama-ai-backend"**
4. Copia tu **Write Token**

### Paso 2: Configurar en tu app

Añade el token a tu `.env`:

```bash
# Logfire Observability
LOGFIRE_TOKEN=your_token_aqui_xxxxx
ENVIRONMENT=development
```

### Paso 3: Reiniciar backend

```bash
pkill -f "uvicorn app:app"
cd /Users/mariasebares/Documents/RAMA_AI/rama-agentic-ai
.venv/bin/uvicorn app:app --reload --port 7901
```

¡Listo! Los datos empezarán a fluir automáticamente.

---

## 2️⃣ Qué Verás en Logfire

### 🌐 **API Requests Tab**

Verás **todas las requests** a tu API:

```
GET  /api/properties/{id}/numbers/values     200  245ms
POST /ui_chat                                 200  1.8s
GET  /api/numbers/template-structure          200  120ms
POST /api/numbers/import-template             200  3.2s
```

**Para cada request puedes ver:**
- ✅ **Status code** (200, 422, 500)
- ⏱️ **Latency** (response time)
- 📊 **Request/Response bodies** (click en la request)
- 🔍 **Traceback completo** si hay error
- 🧵 **Trace completo**: qué herramientas se llamaron, qué LLMs se usaron

**Ejemplo de trace:**
```
POST /ui_chat (1.8s)
  ├─ Router.route() (50ms) → decision: "numbers"
  ├─ NumbersAgent.run() (1.7s)
  │   ├─ ChatOpenAI.invoke() (1.2s) ← **LLM CALL**
  │   │   ├─ Model: gpt-4o
  │   │   ├─ Tokens: 450 input + 120 output = 570 total
  │   │   ├─ Cost: $0.0023
  │   │   └─ Prompt: "Eres NumbersAgent..." (full text)
  │   └─ set_numbers_table_cell() (500ms)
  │       └─ Supabase RPC call
  └─ Response generated
```

---

### 🤖 **LLM Calls Tab**

Verás **todos los LLM calls** con detalles completos:

**Columnas:**
- 🕐 **Timestamp**: Cuándo se hizo la llamada
- 🤖 **Model**: gpt-4o, gpt-4o-mini, etc.
- 🎯 **Agent/Context**: MainAgent, NumbersAgent, PropertyAgent
- 📊 **Tokens**: Input + Output + Total
- 💰 **Cost**: En USD (calculado automáticamente)
- ⏱️ **Duration**: Cuánto tardó la llamada

**Ejemplo:**
```
[14:23:45] gpt-4o | NumbersAgent | 450→120=570 tokens | $0.0023 | 1.2s
[14:23:42] gpt-4o | MainAgent     | 320→80=400 tokens  | $0.0016 | 0.8s
[14:23:40] gpt-4o | Router        | 150→30=180 tokens  | $0.0007 | 0.3s
```

**Click en una llamada para ver:**
- 📝 **Prompt completo** (system + user messages)
- 💬 **Respuesta completa** del LLM
- 🛠️ **Tool calls** si los hubo
- 🧵 **Request parent** que la triggeró

---

### 💰 **Cost Analytics**

Dashboard automático con:

**Por Modelo:**
```
gpt-4o:       $2.45  (15K tokens)  - 45 calls
gpt-4o-mini:  $0.12  (8K tokens)   - 120 calls
```

**Por Agente:**
```
MainAgent:     $1.80  (12K tokens)  - 30 calls
NumbersAgent:  $0.50  (4K tokens)   - 8 calls
PropertyAgent: $0.27  (2K tokens)   - 7 calls
```

**Por Endpoint:**
```
/ui_chat:                      $2.10
/api/numbers/set-cell-value:   $0.35
/api/properties/list:          $0.12
```

**Timeline:**
- Gráfico de costo por hora/día
- Picos de uso
- Cost per request promedio

---

### 📊 **Performance Metrics**

**Latency Percentiles:**
```
P50: 850ms
P95: 2.1s
P99: 4.5s
```

**Error Rate:**
```
200: 95%
422: 3%
500: 2%
```

**Slowest Endpoints:**
```
POST /api/numbers/import-template  → 3.2s avg
POST /ui_chat                      → 1.8s avg
GET  /api/numbers/template-struct  → 120ms avg
```

---

### 🐛 **Error Debugging**

Cuando hay un error, Logfire te muestra:

**1. Request completa:**
```json
{
  "user_input": "Pon el valor 5000 en B5",
  "session_id": "casa-demo-12",
  "property_id": "prop-uuid-xxx"
}
```

**2. Traceback completo:**
```python
Traceback:
  File "tools/numbers_tools.py", line 234
    raise ValueError(f"Cell {address} not found")
ValueError: Cell B5 not found in template
```

**3. Context:**
- Qué agente estaba ejecutando
- Qué herramienta falló
- Qué LLM se había llamado antes

**4. Previous successful calls:**
- Para comparar qué cambió
- Reproducir el error

---

## 3️⃣ Queries Útiles en Logfire

Logfire tiene un **query builder** poderoso:

### Ver todos los errores de hoy
```
status_code >= 400
```

### LLM calls más caros
```
span_name = "ChatOpenAI.invoke"
ORDER BY cost DESC
LIMIT 20
```

### Requests lentas (>2s)
```
duration_ms > 2000
```

### Uso por property
```
attributes.property_id = "casa-demo-12"
```

### Cuánto gasté hoy en NumbersAgent
```
attributes.agent = "NumbersAgent"
AND timestamp > today
SUM(cost)
```

---

## 4️⃣ Alertas (Opcional)

Puedes configurar alertas en Logfire:

**Ejemplo: Error rate > 5%**
```
IF error_rate > 0.05 THEN
  send_slack_notification()
```

**Ejemplo: LLM cost > $10/hora**
```
IF hourly_llm_cost > 10 THEN
  send_email_alert()
```

**Ejemplo: Latency P95 > 3s**
```
IF p95_latency > 3000 THEN
  page_on_call()
```

---

## 5️⃣ Dashboards Custom

Puedes crear dashboards custom en Logfire:

**Ejemplo: Numbers Table Dashboard**
- Total de tablas creadas hoy
- Promedio de celdas por tabla
- Tiempo promedio de import
- Errores de fórmulas

**Ejemplo: Agent Performance**
- Cuál agente se usa más
- Cuál es más caro
- Cuál es más lento
- Cuál tiene más errores

---

## 6️⃣ Comparación con Métrica Custom

| Feature | Custom Metrics | Logfire |
|---------|---------------|---------|
| Setup time | 2 días | 5 minutos |
| API monitoring | ❌ Manual | ✅ Automático |
| LLM tracking | ❌ Manual | ✅ Automático |
| Prompt viewing | ❌ | ✅ Full text |
| Cost calc | ❌ Manual | ✅ Automático |
| Error traces | ❌ | ✅ Full stack |
| Alerts | ❌ | ✅ Built-in |
| Dashboards | 🟡 Custom code | ✅ No-code |
| Queries | ❌ | ✅ SQL-like |
| Retention | 1 hour | 30 days free |
| Cost | Free | $0 (100K spans) |

---

## 7️⃣ Pro Tips

### 1. Añadir contexto custom a spans

Puedes enriquecer los spans con metadata:

```python
import logfire

with logfire.span("import_excel_template", property_id=property_id, template_name="R2B"):
    # ... tu código ...
    logfire.info(f"Imported {total_cells} cells")
```

Esto aparecerá en Logfire y podrás filtrar por `property_id`, `template_name`, etc.

### 2. Samplear requests largas

Si tienes mucho tráfico, puedes samplear:

```python
logfire.configure(
    token=os.getenv("LOGFIRE_TOKEN"),
    service_name="rama-ai-backend",
    sampling_rate=0.1  # Solo loguea 10% de requests normales
)
```

Pero **todos los errores siempre se loguean**.

### 3. Filtrar datos sensibles

Si tienes datos sensibles en prompts:

```python
logfire.instrument_openai(
    suppress_other_instrumentation=False,
    capture_statement=False  # No loguea SQL statements completos
)
```

---

## 8️⃣ Troubleshooting

### No veo datos en Logfire

1. ✅ Verifica que `LOGFIRE_TOKEN` esté en `.env`
2. ✅ Reinicia el backend
3. ✅ Haz una request a `/ui_chat`
4. ✅ Check logs: `tail -f logs/backend.log` (debe decir "Logfire configured")

### Veo API calls pero no LLM calls

- Verifica que `logfire.instrument_openai()` se llame **antes** de importar `ChatOpenAI`
- Check que estés usando `ChatOpenAI` de `langchain_openai` (no `openai` directo)

### Cost no aparece

- Logfire calcula cost automáticamente para modelos OpenAI
- Si usas otro provider (Anthropic, etc.), el cost no se calcula automáticamente

---

## 🎉 ¡Ya está!

Ahora tienes **observability profesional** en tu app sin escribir código custom de métricas. Logfire se encarga de todo:
- ✅ Loguea automáticamente todas las requests
- ✅ Loguea automáticamente todas las LLM calls
- ✅ Calcula automáticamente costs
- ✅ Genera automáticamente dashboards
- ✅ Permite queries avanzados
- ✅ Alertas configurables

**Siguiente paso:** Abre https://logfire.pydantic.dev y explora tus datos 🚀

