# 📥 Cómo Importar el Dashboard de Logfire

Este documento explica cómo importar el dashboard completo de RAMA AI en Logfire usando el archivo JSON.

---

## 📂 **Archivo JSON**

El dashboard completo está en: `docs/logfire-dashboard.json`

---

## 🚀 **Método 1: Importar Dashboard Completo (Recomendado)**

### **Paso 1: Abre Logfire**
```
https://logfire-eu.pydantic.dev/mariasebarespersona/rama-ai
```

### **Paso 2: Ve a Dashboards**
- Click en **"Dashboards"** (sidebar izquierdo)

### **Paso 3: Importar**
- Click en el botón **"Import"** o **"+"**
- Busca la opción **"Import from JSON"**

### **Paso 4: Pega el JSON**
1. Abre el archivo `docs/logfire-dashboard.json`
2. Copia TODO el contenido
3. Pégalo en el campo de importación de Logfire
4. Click **"Import"** o **"Load"**

### **Paso 5: Verificar**
- El dashboard debería aparecer con todos los 14 paneles
- Si no ves datos inmediatamente, genera tráfico o ajusta el time range a "Last 24 hours"

---

## 🔧 **Método 2: Crear Manualmente (Si Import no está disponible)**

Si Logfire no tiene opción de importar JSON, puedes crear cada panel manualmente:

### **Panel 1: API Request Rate**
```json
{
  "title": "API Request Rate (Requests por Minuto)",
  "type": "timeseries",
  "query": "SELECT date_trunc('minute', start_timestamp) as time, count(*) as requests GROUP BY 1 ORDER BY 1 DESC LIMIT 1000",
  "xAxis": "time",
  "yAxis": "requests"
}
```

### **Panel 2: API Status Codes**
```json
{
  "title": "API Status Codes",
  "type": "pie",
  "query": "SELECT COALESCE(CAST(attributes['http.status_code'] AS TEXT), 'unknown') as status_code, count(*) as count GROUP BY 1 ORDER BY 2 DESC",
  "labelField": "status_code",
  "valueField": "count"
}
```

... y así sucesivamente para cada panel (ver `logfire-dashboard.json` para queries completas)

---

## ⚠️ **Posibles Ajustes Necesarios**

Dependiendo de tu versión de Logfire, puede que necesites ajustar:

### **1. Nombres de Columnas**

Si ves errores de "column not found", ajusta:

**Timestamp:**
- `start_timestamp` → puede ser `start_time` o `timestamp`

**Atributos:**
- `attributes['llm.request.model']` → puede ser `attributes['gen_ai.request.model']`
- `attributes['http.status_code']` → puede estar en otro path

**Cómo verificar:**
1. Ve a **Live** en Logfire
2. Click en cualquier evento
3. Mira los nombres de campos exactos

### **2. Funciones SQL**

Si una función no funciona, prueba alternativas:

**percentile_cont:**
```sql
-- Original
ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY duration), 0)

-- Alternativa 1
ROUND(percentile(duration, 0.95), 0)

-- Alternativa 2
approx_percentile(duration, 0.95)
```

**FILTER:**
```sql
-- Original
count(*) FILTER (WHERE condition)

-- Alternativa
sum(CASE WHEN condition THEN 1 ELSE 0 END)
```

---

## 🧪 **Generar Datos de Prueba**

Después de importar, genera tráfico para ver datos:

```bash
cd /Users/mariasebares/Documents/RAMA_AI/rama-agentic-ai

# Generar 20 requests de prueba
for i in {1..20}; do
  echo "Request $i..."
  curl -X POST http://localhost:7901/ui_chat \
    -H "Content-Type: application/json" \
    -d "{\"user_input\": \"test request $i\", \"session_id\": \"test-dashboard\"}"
  sleep 2
done

echo "✅ Datos generados! Refresca tu dashboard en Logfire"
```

---

## 📊 **Qué Verás en el Dashboard**

### **Sección 1: API Monitoring (5 paneles)**
1. ✅ Request Rate - Línea temporal de tráfico
2. ✅ Status Codes - Pie chart de respuestas
3. ✅ Error Rate - Porcentaje de errores
4. ✅ Slowest Endpoints - Tabla de latencia
5. ✅ P95 Latency - Percentiles por endpoint

### **Sección 2: Agent Performance (2 paneles)**
6. ✅ Agent Performance - Tabla comparativa
7. ✅ Router Decisions - Pie chart de routing

### **Sección 3: LLM Tracking (5 paneles)**
8. ✅ LLM Calls - Volumen por minuto
9. ✅ LLM by Model - Stacked bar de modelos
10. ✅ Token Usage - Área de tokens input/output
11. ✅ LLM Cost Table - Tabla de costos
12. ✅ LLM Cost Over Time - Línea de gasto

### **Sección 4: Business Metrics (2 paneles)**
13. ✅ Emails Sent - Stat number
14. ✅ Numbers Table Ops - Bar chart de actividad

---

## 🎨 **Layout del Dashboard**

```
┌────────────────────────────────────────────────────────────┐
│  1. API Request Rate (full width)                          │
├──────────────────────────┬─────────────────────────────────┤
│  2. Status Codes (pie)   │  3. Error Rate (area)          │
├──────────────────────────┴─────────────────────────────────┤
│  4. Top 10 Slowest Endpoints (table, full width)           │
├──────────────────────────┬─────────────────────────────────┤
│  5. P95 Latency (table)  │  6. Agent Performance (table)  │
├──────────────────────────┴─────────────────────────────────┤
│  7. LLM Calls per Minute (full width)                      │
├──────────────────────────┬─────────────────────────────────┤
│  8. LLM by Model (stack) │  9. Router Decisions (pie)     │
├──────────────────────────┴─────────────────────────────────┤
│  10. Token Usage Over Time (stacked area, full width)      │
├──────────────────────────┬─────────────────────────────────┤
│  11. LLM Cost Table      │  12. LLM Cost Over Time        │
├────────┬─────────────────┴─────────────────────────────────┤
│ 13.    │  14. Numbers Table Operations (bar chart)         │
│ Emails │                                                     │
└────────┴─────────────────────────────────────────────────────┘
```

---

## ⚙️ **Configuración Recomendada**

Después de importar, configura:

### **Time Range:**
- Default: **Last 1 hour**
- Para debugging: Cambiar a "Last 24 hours"

### **Auto Refresh:**
- API panels: **30 seconds**
- LLM panels: **1 minute**
- Cost panels: **5 minutes**

### **Alertas (Opcional):**

1. **High Error Rate (>5%)**
   - Panel: Error Rate Over Time
   - Condition: `error_rate_pct > 5`
   - Action: Email/Slack notification

2. **High LLM Cost (>$10/hora)**
   - Panel: LLM Cost Over Time
   - Condition: `cost_usd > 10`
   - Action: Email notification

3. **High P95 Latency (>3s)**
   - Panel: P95 Latency
   - Condition: `p95_ms > 3000`
   - Action: Slack notification

---

## 🐛 **Troubleshooting**

### **Error: "table not found" o "column not found"**

**Solución**: Las queries usan nombres estándar de OpenTelemetry, pero Logfire puede usar nombres diferentes.

1. Ve a **Live** en Logfire
2. Click en cualquier evento
3. Anota los nombres exactos de:
   - Timestamp field (`start_timestamp`, `start_time`, o `timestamp`)
   - Span name field (`span_name` o `name`)
   - Attributes structure

4. Edita cada panel y ajusta los nombres de columnas

### **No veo datos en el dashboard**

**Posibles causas:**

1. **No hay datos en Logfire**
   - Ve a Live y verifica que hay eventos
   - Genera tráfico con el script de arriba

2. **Time range incorrecto**
   - Cambia de "Last 1 hour" a "Last 24 hours"

3. **Query está filtrada muy específicamente**
   - Simplifica los WHERE clauses
   - Ejemplo: quita `WHERE span_name LIKE '%ChatOpenAI%'`

### **Algunos paneles funcionan, otros no**

**Solución**: Los paneles que no funcionan probablemente usan:
- Funciones SQL no soportadas → Cambiar por equivalentes
- Campos que no existen → Ajustar nombres

---

## 📝 **Notas Importantes**

### **Sobre los Precios de OpenAI**

Las queries de costo usan estos precios (Nov 2024):
- **gpt-4o**: $2.50 input / $10 output (per 1M tokens)
- **gpt-4o-mini**: $0.15 input / $0.60 output (per 1M tokens)

Si OpenAI cambia precios, edita los paneles 11 y 12.

### **Sobre los Atributos**

Logfire puede usar dos naming conventions:
- `attributes['llm.request.model']` → OpenAI naming
- `attributes['gen_ai.request.model']` → OpenTelemetry naming

Las queries intentan ambos con `COALESCE()`.

---

## 🎉 **¡Listo!**

Después de importar y ajustar (si es necesario), tendrás un dashboard de producción completo con:

✅ Monitoring de API en tiempo real  
✅ Tracking de LLM calls y costos  
✅ Performance de agentes especializados  
✅ Métricas de negocio  

**Todo sin escribir código custom** 🚀

---

## 📚 **Recursos Adicionales**

- `docs/LOGFIRE_SETUP.md` → Setup inicial de Logfire
- `docs/LOGFIRE_DASHBOARD_SETUP.md` → Queries SQL detalladas
- `docs/logfire-dashboard.json` → JSON completo del dashboard

---

## 💬 **¿Necesitas Ayuda?**

Si encuentras errores:
1. Copia el mensaje de error
2. Dime qué panel está fallando
3. Muéstrame un evento de ejemplo de Live

¡Y lo ajustamos! 🔧

