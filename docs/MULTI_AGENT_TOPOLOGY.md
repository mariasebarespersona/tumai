# 🏗️ Multi-Agent Topology - Diseño

## Arquitectura General

```
┌─────────────────────────────────────────────────────────────┐
│                         USER INPUT                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │   ROUTER/CLASSIFIER  │
            │  (Intent Detection)  │
            └──────────┬───────────┘
                       │
         ┌─────────────┼──────────────┬──────────────┐
         │             │              │              │
         ▼             ▼              ▼              ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │Property  │  │Numbers   │  │ Docs     │  │  Main    │
  │ Agent    │  │ Agent    │  │ Agent    │  │  Agent   │
  └──────────┘  └──────────┘  └──────────┘  └──────────┘
       │             │              │              │
       └─────────────┴──────────────┴──────────────┘
                      │
                      ▼
              ┌───────────────┐
              │  SHARED TOOLS │
              └───────────────┘
```

---

## Agentes Especializados

### 1️⃣ **PropertyAgent** 
**Responsabilidad**: Gestión de propiedades (CRUD)

**Intents que maneja**:
- `create_property` - Crear nueva propiedad
- `switch_property` - Cambiar de propiedad actual
- `list_properties` - Listar propiedades
- `delete_property` - Eliminar propiedad

**Tools exclusivos**:
- `add_property_tool`
- `set_current_property_tool`
- `list_properties_tool`
- `delete_property_tool`
- `find_property_tool`

**Prompt especializado**:
```markdown
Eres un asistente especializado en gestión de propiedades.
Tu única responsabilidad es ayudar al usuario a:
- Crear nuevas propiedades
- Cambiar entre propiedades
- Listar propiedades existentes
- Eliminar propiedades

NO manejes números, documentos u otras operaciones.
Si el usuario pide algo fuera de tu scope, responde:
"Para eso necesitas otro servicio. ¿Puedo ayudarte con alguna propiedad?"
```

**Benefit**: 
- Latencia reducida (solo carga tools de propiedades)
- Contexto más claro (no se confunde con números/docs)

---

### 2️⃣ **NumbersAgent**
**Responsabilidad**: Operaciones con Numbers Table (R2B)

**Intents que maneja**:
- `numbers_select_template` - Seleccionar plantilla R2B
- `numbers_update` - Actualizar valor de celda
- `numbers_clear` - Borrar valor de celda
- `numbers_export` - Exportar a Excel
- `numbers_delete` - Eliminar plantilla
- `numbers_send_email` - Enviar por email

**Tools exclusivos**:
- `set_numbers_template_tool`
- `set_numbers_table_cell_tool`
- `clear_numbers_table_cell_tool`
- `export_numbers_table_tool`
- `delete_numbers_template_tool`
- `send_numbers_table_email_tool`

**Prompt especializado**:
```markdown
Eres un experto en gestión de plantillas de Números (R2B).
Tu especialidad es:
- Seleccionar y gestionar plantillas R2B
- Actualizar valores en celdas (B5, C5, etc.)
- Calcular automáticamente fórmulas en cascada
- Exportar y enviar por email

Recuerda:
- SIEMPRE que el usuario actualice B5, C5, etc., se calculan automáticamente D5, E5, etc.
- NO pidas confirmación para set_numbers_table_cell
- Las celdas amarillas son inputs del usuario
```

**Benefit**:
- Contexto enfocado en R2B (no se confunde con docs)
- Respuestas más rápidas (menos tools = menos overhead)

---

### 3️⃣ **DocsAgent**
**Responsabilidad**: Gestión de documentos (upload, email)

**Intents que maneja**:
- `docs_upload` - Subir documento
- `docs_send_email` - Enviar documento por email
- `docs_list` - Listar documentos
- `docs_list_facturas` - Listar facturas asociadas

**Tools exclusivos**:
- `upload_and_link_tool`
- `send_email_tool`
- `list_docs_tool`
- `list_related_facturas_tool`
- `signed_url_for_tool`

**Prompt especializado**:
```markdown
Eres un asistente especializado en gestión de documentos.
Tu trabajo es:
- Subir documentos a la propiedad actual
- Enviar documentos por email con links seguros
- Listar documentos y facturas asociadas
- Generar URLs firmadas para acceso seguro

Cuando envíes emails:
1. SIEMPRE usa signed_url_for_tool para generar el link
2. Incluye el link en el cuerpo del email
3. Confirma el envío al usuario
```

**Benefit**:
- Especializado en docs (no se confunde con números)
- Manejo de signed URLs más seguro

---

### 4️⃣ **MainAgent** (Orquestador)
**Responsabilidad**: Fallback + conversación general

**Intents que maneja**:
- `general_conversation` - Preguntas generales
- `help` - Ayuda
- `summarize` - Resúmenes
- `ambiguous` - Intents ambiguos (confidence < threshold)

**Tools**:
- Todos los tools (acceso completo para casos complejos)

**Prompt**:
```markdown
Eres el asistente principal de RAMA.
Manejas conversaciones generales y casos que otros agentes no pueden resolver.

Si detectas que la petición es específica de:
- Propiedades → Sugiere usar el PropertyAgent
- Números → Sugiere usar el NumbersAgent
- Documentos → Sugiere usar el DocsAgent

Para queries complejas que involucran múltiples áreas, manéjalas tú mismo.
```

**Benefit**:
- Safety net (siempre hay un fallback)
- Maneja casos complejos multi-dominio

---

## Reglas de Routing

### Confidence Thresholds

```python
CONFIDENCE_THRESHOLDS = {
    "property_intents": 0.75,    # Más bajo (cambiar propiedad es común)
    "numbers_intents": 0.80,     # Medio (acciones específicas)
    "docs_intents": 0.85,        # Más alto (emails son críticos)
    "general_fallback": 0.0      # Siempre acepta
}
```

### Routing Logic

```python
def route_request(intent: str, confidence: float) -> str:
    """Route to specialized agent based on intent and confidence."""
    
    # High confidence routes
    if confidence >= CONFIDENCE_THRESHOLDS.get(intent_category(intent), 0.9):
        if intent in PROPERTY_INTENTS:
            return "PropertyAgent"
        elif intent in NUMBERS_INTENTS:
            return "NumbersAgent"
        elif intent in DOCS_INTENTS:
            return "DocsAgent"
    
    # Low confidence or complex -> MainAgent
    return "MainAgent"
```

### Fallback Strategy

1. **Confidence < threshold** → MainAgent + warning
2. **Agent fails** → Retry with MainAgent + log error
3. **Unknown intent** → MainAgent + "No entiendo, ¿puedes ser más específico?"

---

## Intent → Agent Mapping

| Intent Category | Agent | Example Phrases |
|----------------|-------|-----------------|
| `create_property` | PropertyAgent | "crea propiedad casa demo 20" |
| `switch_property` | PropertyAgent | "cambia a villa málaga" |
| `numbers_update` | NumbersAgent | "pon B5 en 1000" |
| `numbers_export` | NumbersAgent | "exporta la plantilla R2B" |
| `docs_upload` | DocsAgent | "sube este contrato" |
| `docs_send_email` | DocsAgent | "manda factura por email" |
| `general_help` | MainAgent | "¿qué puedes hacer?" |
| `ambiguous` | MainAgent | "necesito ayuda" |

---

## Latency Optimization

### Before Multi-Agent (Current)
```
Request → LangGraph → Load ALL tools (50+) → Process → Response
Average: ~5-8s
```

### After Multi-Agent (Target)
```
Request → Router → Specialized Agent → Load ONLY relevant tools (5-10) → Response
Target: ~3-5s (-30% to -40%)
```

### Key Optimizations
1. **Fewer tools loaded** → Menos overhead en LLM context
2. **Smaller prompts** → Menos tokens procesados
3. **Focused context** → Mejor accuracy, menos hallucinations
4. **Parallel routing** → Router puede ejecutar en paralelo con MainAgent

---

## Error Handling

### Agent-Specific Errors

```python
class AgentError(Exception):
    """Base exception for agent errors."""
    pass

class PropertyAgentError(AgentError):
    """Property agent specific error."""
    pass

# Error recovery flow:
try:
    result = property_agent.run(input)
except PropertyAgentError as e:
    logger.warning(f"PropertyAgent failed: {e}, routing to MainAgent")
    result = main_agent.run(input)  # Fallback
```

---

## Monitoring & Metrics

### New Metrics to Track

```python
# Agent-specific metrics
metrics.log_event("agent.property.invoked")
metrics.log_event("agent.numbers.invoked")
metrics.log_event("agent.docs.invoked")
metrics.log_event("agent.main.fallback")

# Routing metrics
metrics.log_event("router.confidence.high")  # >= threshold
metrics.log_event("router.confidence.low")   # < threshold
metrics.log_event("router.fallback_triggered")

# Performance
metrics.record_latency("agent.property.latency_ms", duration)
```

### Dashboard Additions

- 📊 **Agent Usage Distribution** (pie chart)
- ⚡ **Latency by Agent** (bar chart)
- 🔄 **Fallback Rate** (% of requests that use MainAgent)
- 🎯 **Routing Accuracy** (% of requests correctly routed)

---

## Implementation Plan

### Phase 1: Agent Skeletons (Day 1)
- ✅ Create `agents/property_agent.py`
- ✅ Create `agents/numbers_agent.py`
- ✅ Create `agents/docs_agent.py`
- ✅ Create `agents/main_agent.py`

### Phase 2: Prompts & Tools (Day 2)
- ✅ Write specialized prompts for each agent
- ✅ Map tools to agents
- ✅ Create tool subsets for each agent

### Phase 3: Router Update (Day 3)
- ✅ Update `router/scaffold.py` for active routing
- ✅ Implement confidence thresholds
- ✅ Add fallback logic

### Phase 4: Integration (Day 4)
- ✅ Update `app.py` to use multi-agent system
- ✅ Wire up routing + agents
- ✅ Add metrics for each agent

### Phase 5: Testing & Optimization (Day 5)
- ✅ Write tests for each agent
- ✅ Measure latency improvements
- ✅ Optimize routing rules based on data
- ✅ Document and deploy

---

## Success Metrics

✅ **Latency**: -30% average response time  
✅ **Accuracy**: >95% correct routing  
✅ **Fallback Rate**: <10% of requests  
✅ **User Satisfaction**: No increase in errors  

---

**Next Step**: Implement Phase 1 - Agent Skeletons

