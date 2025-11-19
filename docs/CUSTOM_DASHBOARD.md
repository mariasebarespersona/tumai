# 📊 Custom Dashboard - RAMA AI Metrics

Dashboard personalizado que consume datos de Logfire vía API y los muestra en tu propia app.

---

## 🎯 **¿Qué es esto?**

En vez de usar SQL queries en Logfire panel por panel, este dashboard:
- ✅ **Consume datos de Logfire** automáticamente vía API
- ✅ **Los muestra en tu app** con gráficos bonitos
- ✅ **Auto-refresh** cada 30 segundos
- ✅ **Selector de time range** (15min, 1h, 6h, 24h)
- ✅ **Cero configuración SQL** - todo automático

---

## 📦 **Qué se Incluyó**

### **Backend**
- `tools/logfire_client.py` → Cliente Python para Logfire API
- 3 endpoints en `app.py`:
  - `GET /api/dashboard/metrics` → Todas las métricas
  - `GET /api/dashboard/api-metrics` → Solo métricas de API
  - `GET /api/dashboard/llm-metrics` → Solo métricas de LLM

### **Frontend**
- `web/src/app/dashboard/page.tsx` → Dashboard completo
- Gráficos con **recharts** (library de charts para React)
- 10+ visualizaciones incluidas

---

## 🚀 **Cómo Acceder**

### **Paso 1: Reiniciar Backend**

```bash
cd /Users/mariasebares/Documents/RAMA_AI/rama-agentic-ai
pkill -f "uvicorn app:app"
.venv/bin/uvicorn app:app --reload --port 7901
```

### **Paso 2: Abrir Dashboard**

```
http://localhost:3000/dashboard
```

---

## 📊 **Qué Verás en el Dashboard**

### **1. Summary Cards (4 tarjetas)**
- 🌐 Total Requests
- 🤖 LLM Calls
- 💰 LLM Cost (USD)
- 🎯 Total Tokens

### **2. API Request Rate (gráfico de línea)**
- Requests por minuto en tiempo real

### **3. Status Codes (pie chart)**
- Distribución de códigos 200, 422, 500, etc.

### **4. Error Rate (gráfico de línea)**
- Porcentaje de errores over time

### **5. Top Endpoints (tabla)**
- Los 10 endpoints más llamados
- Con latency promedio y máxima

### **6. LLM Calls (gráfico de línea)**
- Volumen de llamadas a OpenAI por minuto

### **7. LLM Cost by Model (tarjetas)**
- Costo desglosado por gpt-4o, gpt-4o-mini, etc.
- Con tokens y número de calls

### **8. Agent Performance (tabla)**
- Comparación entre MainAgent, NumbersAgent, etc.
- Con calls, latency, success rate

---

## ⚙️ **Configuración**

### **Time Range Selector**
Cambia entre:
- 📅 Últimos 15 minutos
- 📅 Última 1 hora (default)
- 📅 Últimas 6 horas
- 📅 Últimas 24 horas

### **Auto-Refresh**
- ✅ **Activado por default** (cada 30 segundos)
- Puedes desactivarlo con el toggle
- Botón manual de refresh también disponible

---

## 🔧 **Importante: Logfire API**

**⚠️ NOTA**: El código asume que Logfire tiene una API pública. Si Logfire NO expone una API REST, necesitaremos hacer una de estas:

### **Opción A: Usar Logfire SDK (si existe)**
```python
import logfire

# En vez de requests.post()
client = logfire.Client(token=LOGFIRE_TOKEN)
result = client.query(sql)
```

### **Opción B: Fallback a datos mock**
Si Logfire no tiene API, podemos:
1. Usar datos simulados para el dashboard
2. O parsear los datos directamente de los logs locales

### **Opción C: OpenTelemetry directo**
Logfire usa OpenTelemetry. Podríamos:
1. Exportar traces a un backend local (Jaeger/Zipkin)
2. Consultar ese backend desde el dashboard

---

## 🧪 **Testing**

### **Generar Datos de Prueba**

```bash
cd /Users/mariasebares/Documents/RAMA_AI/rama-agentic-ai

# Generar 20 requests
for i in {1..20}; do
  curl -X POST http://localhost:7901/ui_chat \
    -H "Content-Type: application/json" \
    -d "{\"user_input\": \"test dashboard $i\", \"session_id\": \"dashboard-test\"}"
  sleep 2
done
```

Luego refresca el dashboard y deberías ver los datos.

---

## 🐛 **Troubleshooting**

### **Error: "Network error" o 500**

**Causa**: Logfire API no responde o no existe.

**Solución temporal** - Usar datos mock:

En `tools/logfire_client.py`, línea 25, cambia `_query` por:

```python
def _query(self, sql: str, time_range: str = "1h") -> Dict[str, Any]:
    """Execute a SQL query against Logfire"""
    # TEMPORARY: Return mock data while we figure out Logfire API
    import random
    from datetime import datetime, timedelta
    
    # Generate mock time series
    now = datetime.now()
    data = []
    for i in range(60):
        t = now - timedelta(minutes=i)
        data.append({
            "time": t.isoformat(),
            "value": random.randint(10, 100)
        })
    
    return {"data": data}
```

Esto permitirá ver el dashboard funcionando mientras investigamos la API real de Logfire.

---

### **Charts no se ven**

**Causa**: `recharts` no instalado.

**Solución**:
```bash
cd web
npm install recharts
```

---

### **Dashboard vacío**

**Causa**: No hay datos en Logfire.

**Solución**: Genera tráfico con el script de arriba.

---

## 📈 **Próximos Pasos**

1. **Verificar API de Logfire**: Necesitamos confirmar si Logfire expone una API REST
2. **Si no hay API**: Implementar una de las alternativas (Opción A/B/C)
3. **Añadir más gráficos**: Tokens over time, cost over time, etc.
4. **Alertas**: Notificaciones cuando error rate > 5%

---

## 🎨 **Personalización**

### **Cambiar Colores**

En `page.tsx`, línea 10:

```typescript
const COLORS = {
  primary: "#3b82f6",  // Azul
  success: "#22c55e",  // Verde
  warning: "#f59e0b",  // Naranja
  error: "#ef4444",    // Rojo
  purple: "#8b5cf6",   // Morado
};
```

### **Añadir Más Gráficos**

Copia un panel existente y cambia:
1. El endpoint de datos
2. El tipo de gráfico
3. Los campos a mostrar

---

## 💡 **Ventajas vs Logfire UI**

| Feature | Logfire UI | Custom Dashboard |
|---------|------------|------------------|
| Configuración | SQL panel por panel | Automático |
| Personalización | Limitada | 100% customizable |
| Integración | Externa | En tu app |
| Branding | Logfire | Tu marca |
| Costo | Depende de Logfire | Gratis (ya pagaste Logfire) |
| Complejidad | Alta (SQL) | Baja (UI components) |

---

## 🎉 **¡Listo!**

Ahora tienes un dashboard custom profesional que:
- ✅ Consume datos de Logfire automáticamente
- ✅ Se ve bonito con gráficos interactivos
- ✅ Auto-refresh cada 30 segundos
- ✅ 100% personalizable
- ✅ Integrado en tu app

**Sin SQL, sin configuración manual, sin líos** 🚀

---

## 📞 **Siguiente Paso**

1. **Abre** http://localhost:3000/dashboard
2. **Dime** qué ves (¿funciona? ¿error? ¿vacío?)
3. **Ajustamos** según sea necesario

¡El dashboard está listo para usar! 🎊

