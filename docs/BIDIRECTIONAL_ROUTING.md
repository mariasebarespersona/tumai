# 🔄 Bidirectional Agent Routing

## Problema Actual

**Flujo actual (unidireccional)**:
```
User → Router → Agent → Response
```

**Limitación**: Si un agente detecta que la petición está fuera de su scope, no puede redireccionar dinámicamente.

**Ejemplo problemático**:
```
User: "pon B5 en 1000 y luego envía la plantilla por email"
Router → NumbersAgent (detecta "pon B5")
NumbersAgent: Ejecuta set_cell → ¿Y ahora qué con el email?
```

---

## Solución: Routing Bidireccional

### 🏗️ Nueva Arquitectura

```
┌──────────────────────────────────────────────────────────────┐
│                         USER INPUT                            │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
                 ┌───────────────┐
                 │    ROUTER     │◄─────┐
                 │  (Orchestrator)│      │
                 └───────┬───────┘      │
                         │              │
         ┌───────────────┼──────────────┤ (can redirect)
         │               │              │              │
         ▼               ▼              ▼              ▼
  ┌──────────┐    ┌──────────┐  ┌──────────┐  ┌──────────┐
  │Property  │    │Numbers   │  │ Docs     │  │  Main    │
  │ Agent    │    │ Agent    │  │ Agent    │  │  Agent   │
  └────┬─────┘    └────┬─────┘  └────┬─────┘  └────┬─────┘
       │               │              │              │
       └───────────────┴──────────────┴──────────────┘
                       │
                       ▼
               ┌───────────────┐
               │ SHARED TOOLS  │
               └───────────────┘
```

**Clave**: Los agentes pueden devolver `{"action": "redirect", "to_agent": "DocsAgent", "reason": "..."}` y el router lo maneja.

---

## 🎯 Casos de Uso

### 1️⃣ **Redirección Simple**
```
User: "pon B5 en 1000 y luego envía por email"

1. Router → NumbersAgent (detecta "pon B5")
2. NumbersAgent ejecuta set_cell
3. NumbersAgent detecta "envía por email" → REDIRECT
   return {"action": "redirect", "to_agent": "DocsAgent", "context": {...}}
4. Router → DocsAgent (con contexto de números actualizados)
5. DocsAgent envía email con plantilla actualizada
```

### 2️⃣ **Escalado a MainAgent**
```
User: "crea una propiedad y sube el contrato y calcula B5"

1. Router → PropertyAgent (detecta "crea propiedad")
2. PropertyAgent detecta multi-dominio → ESCALATE
   return {"action": "escalate", "reason": "multi_domain_task"}
3. Router → MainAgent (puede manejar múltiples dominios)
4. MainAgent coordina: Property → Docs → Numbers
```

### 3️⃣ **Colaboración Entre Agentes**
```
User: "envía el resumen con los números de la propiedad actual"

1. Router → MainAgent (tarea compleja)
2. MainAgent llama a PropertyAgent.get_current()
3. MainAgent llama a NumbersAgent.get_values()
4. MainAgent genera resumen y llama a DocsAgent.send_email()
```

---

## 🔧 Implementación

### BaseAgent - Con Soporte de Redirección

```python
class BaseAgent:
    def run(self, user_input: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Run agent with support for redirection."""
        try:
            # Check if out of scope
            if self.is_out_of_scope(user_input):
                return {
                    "action": "redirect",
                    "to_agent": self.suggest_agent(user_input),
                    "reason": "out_of_scope",
                    "original_input": user_input
                }
            
            # Check if multi-domain task
            if self.is_multi_domain(user_input):
                return {
                    "action": "escalate",
                    "reason": "multi_domain_task",
                    "original_input": user_input
                }
            
            # Normal execution
            response = self._execute(user_input, context)
            
            # Check if response suggests another action
            if self.needs_followup(response):
                return {
                    "action": "chain",
                    "current_response": response,
                    "next_agent": self.suggest_next_agent(response),
                    "next_input": self.extract_followup(user_input)
                }
            
            return {
                "action": "complete",
                "response": response
            }
        
        except Exception as e:
            return {
                "action": "error",
                "error": str(e),
                "fallback_to": "MainAgent"
            }
    
    def is_out_of_scope(self, text: str) -> bool:
        """Check if request is out of this agent's scope."""
        raise NotImplementedError
    
    def suggest_agent(self, text: str) -> str:
        """Suggest which agent should handle this request."""
        raise NotImplementedError
```

### Router - Con Manejo de Redirección

```python
class OrchestrationRouter:
    """Router with bidirectional agent communication."""
    
    def __init__(self):
        self.agents = {
            "PropertyAgent": PropertyAgent(),
            "NumbersAgent": NumbersAgent(),
            "DocsAgent": DocsAgent(),
            "MainAgent": MainAgent()
        }
        self.max_redirects = 3  # Prevent infinite loops
    
    async def route_and_execute(self, user_input: str, context: Optional[Dict] = None) -> Dict:
        """Route to agent and handle redirections."""
        redirect_count = 0
        current_input = user_input
        current_agent_name = None
        responses = []
        
        while redirect_count < self.max_redirects:
            # Route to agent
            routing = await self.decide(current_input, context)
            current_agent_name = routing["target_agent"]
            agent = self.agents[current_agent_name]
            
            logger.info(f"[router] Executing {current_agent_name} (redirect #{redirect_count})")
            
            # Execute agent
            result = agent.run(current_input, context)
            
            # Handle different actions
            if result["action"] == "complete":
                responses.append(result["response"])
                return {
                    "success": True,
                    "responses": responses,
                    "final_agent": current_agent_name,
                    "redirects": redirect_count
                }
            
            elif result["action"] == "redirect":
                logger.info(f"[router] Redirecting from {current_agent_name} to {result['to_agent']}")
                responses.append(f"[Redirigiendo a {result['to_agent']}...]")
                current_agent_name = result["to_agent"]
                redirect_count += 1
                # Continue loop
            
            elif result["action"] == "escalate":
                logger.warning(f"[router] Escalating from {current_agent_name} to MainAgent")
                responses.append(f"[Escalando a MainAgent para tarea compleja...]")
                current_agent_name = "MainAgent"
                redirect_count += 1
                # Continue loop
            
            elif result["action"] == "chain":
                responses.append(result["current_response"])
                current_input = result["next_input"]
                current_agent_name = result["next_agent"]
                redirect_count += 1
                # Continue loop
            
            elif result["action"] == "error":
                logger.error(f"[router] Error in {current_agent_name}: {result['error']}")
                # Fallback to MainAgent
                current_agent_name = result.get("fallback_to", "MainAgent")
                redirect_count += 1
                # Continue loop
        
        # Max redirects reached
        logger.error(f"[router] Max redirects ({self.max_redirects}) reached, falling back to MainAgent")
        main_result = self.agents["MainAgent"].run(user_input, context)
        responses.append(main_result["response"])
        
        return {
            "success": True,
            "responses": responses,
            "final_agent": "MainAgent",
            "redirects": redirect_count,
            "fallback": True
        }
```

---

## 📋 Ejemplos Prácticos

### Ejemplo 1: Redirección Automática

**Input**: `"pon B5 en 1000 y envía por email"`

**Flujo**:
1. **Router** → NumbersAgent (detecta "pon B5")
2. **NumbersAgent**:
   - Ejecuta `set_numbers_table_cell(B5, 1000)`
   - Detecta "envía por email" en el input
   - Retorna: `{"action": "redirect", "to_agent": "DocsAgent"}`
3. **Router** → DocsAgent (con contexto de números actualizados)
4. **DocsAgent**:
   - Llama `send_numbers_table_email()`
   - Retorna: `{"action": "complete", "response": "✅ Email enviado"}`

**Output**: 
```
✅ He actualizado B5=1000. Calculando D5=..., E5=...
[Redirigiendo a DocsAgent...]
✅ He enviado la plantilla R2B por email a [email].
```

---

### Ejemplo 2: Escalado a MainAgent

**Input**: `"crea casa demo 20, sube el contrato y pon B5 en 500000"`

**Flujo**:
1. **Router** → PropertyAgent (detecta "crea")
2. **PropertyAgent**:
   - Detecta múltiples dominios (property + docs + numbers)
   - Retorna: `{"action": "escalate", "reason": "multi_domain_task"}`
3. **Router** → MainAgent
4. **MainAgent**:
   - Coordina: 
     - `PropertyAgent.add_property()`
     - `DocsAgent.upload_and_link()`
     - `NumbersAgent.set_cell()`
   - Retorna: `{"action": "complete", "response": "✅ Todo completado"}`

**Output**:
```
[Escalando a MainAgent para tarea compleja...]
✅ He creado 'Casa Demo 20', subido el contrato y actualizado B5=500000.
```

---

### Ejemplo 3: Detección de Out-of-Scope

**Input** (a NumbersAgent): `"lista mis propiedades"`

**Flujo**:
1. **NumbersAgent**:
   - Detecta que "lista propiedades" no es su responsabilidad
   - Retorna: `{"action": "redirect", "to_agent": "PropertyAgent"}`
2. **Router** → PropertyAgent
3. **PropertyAgent**:
   - Ejecuta `list_properties()`
   - Retorna: `{"action": "complete", "response": "Tienes 5 propiedades..."}`

**Output**:
```
[Redirigiendo a PropertyAgent...]
Tienes 5 propiedades: Casa Demo 12, Villa Málaga, ...
```

---

## 🎯 Beneficios

✅ **Flexibilidad**: Agentes pueden redirigir dinámicamente  
✅ **Robustez**: Mejor manejo de errores con fallback  
✅ **UX fluida**: Usuario no necesita reformular la pregunta  
✅ **Escalabilidad**: Fácil añadir nuevos agentes  
✅ **Observable**: Cada redirección se loguea  

---

## 🔒 Seguridad

### Prevención de Loops Infinitos
```python
self.max_redirects = 3  # Máximo 3 redirecciones
```

### Validación de Agentes
```python
if target_agent not in self.agents:
    logger.error(f"Invalid agent: {target_agent}, falling back to MainAgent")
    target_agent = "MainAgent"
```

---

## 📊 Métricas Adicionales

```python
# Track redirection patterns
metrics.log_event("router.redirect", {
    "from_agent": current_agent,
    "to_agent": target_agent,
    "reason": redirect_reason
})

# Track escalations
metrics.log_event("router.escalate", {
    "from_agent": current_agent,
    "reason": escalate_reason
})

# Track chains
metrics.log_event("router.chain", {
    "agents": [agent1, agent2, agent3],
    "total_latency_ms": total_time
})
```

---

## 🚀 Implementación Gradual

### Phase 1: Basic Redirection (Now) ✅
- Agents can return `{"action": "redirect"}`
- Router handles simple redirections

### Phase 2: Escalation (Next)
- Agents can escalate to MainAgent
- MainAgent coordinates multi-domain tasks

### Phase 3: Chaining (Future)
- Agents can chain actions
- Router manages complex workflows

---

## 📝 Decisión de Diseño

**¿Por qué bidireccional es mejor?**

| Aspecto | Unidireccional | Bidireccional |
|---------|---------------|---------------|
| **Flexibilidad** | Router decide 1 vez | Agentes pueden redireccionar |
| **Errores** | Usuario re-formula | Sistema auto-corrige |
| **Tareas complejas** | Difícil | Escalado a MainAgent |
| **UX** | 2-3 mensajes | 1 mensaje fluido |
| **Código** | Más simple | Más potente |

**Recomendación**: Implementar bidireccional con límite de redirects (max 3) para balance entre flexibilidad y simplicidad.

---

**Next Step**: Implementar `OrchestrationRouter` con soporte bidireccional.

