# Fix: Memoria de Conversación del Agente

## 🐛 Problema Identificado

El agente estaba perdiendo el contexto de la conversación después de cada mensaje. Esto se debía a que:

1. Los mensajes del agente no se estaban guardando de vuelta en el STATE
2. El `run_turn` no estaba añadiendo el mensaje del usuario al historial antes de invocar al agente
3. Las sesiones antiguas no tenían el campo `messages` inicializado

## ✅ Solución Implementada

### 1. Inicialización de `messages` en Sesiones

```python
def get_session(session_id: str):
    # ...
    "messages": [],  # Conversation history for agent context
    # ...
    # Ensure messages field exists in old sessions
    if "messages" not in SESSIONS[session_id]:
        SESSIONS[session_id]["messages"] = []
```

### 2. Función Helper para Añadir Mensajes

```python
def add_to_conversation(session_id: str, user_text: str, assistant_text: str):
    """Add user and assistant messages to conversation history for context."""
    from langchain_core.messages import HumanMessage, AIMessage
    STATE = get_session(session_id)
    
    if user_text:
        STATE["messages"].append(HumanMessage(content=user_text))
    if assistant_text:
        STATE["messages"].append(AIMessage(content=assistant_text))
    
    save_sessions()
```

### 3. `run_turn` Ahora Mantiene el Historial

```python
def run_turn(session_id: str, text: str = "", ...):
    STATE = get_session(session_id)
    
    # Get existing messages from STATE to maintain conversation history
    existing_messages = STATE.get("messages", [])
    
    # Add the new user message to the conversation
    from langchain_core.messages import HumanMessage
    if text:
        existing_messages.append(HumanMessage(content=text))
    
    state = {
        "messages": existing_messages,  # ← CRITICAL: Pass conversation history
        "input": text,
        "audio": audio_wav_bytes,
        "property_id": property_id or STATE.get("property_id")
    }
    
    result = agent.invoke(state, config={"configurable": {"thread_id": session_id}})
    return result
```

### 4. Guardar Mensajes Después del Agente

```python
# If no specific intent matched, use the agent
out = run_turn(session_id=session_id, text=user_text, property_id=STATE.get("property_id"))

# CRITICAL: Save the conversation messages back to STATE for persistence
if out.get("messages"):
    STATE["messages"] = out["messages"]
    save_sessions()

# Update property_id if the agent changed it
if out.get("property_id") and out["property_id"] != STATE.get("property_id"):
    STATE["property_id"] = out["property_id"]
    save_sessions()
```

## 🎯 Cómo Funciona Ahora

1. **Usuario envía mensaje** → Se añade como `HumanMessage` al historial
2. **Agente procesa** → Recibe TODO el historial de mensajes previos
3. **Agente responde** → Su respuesta se añade como `AIMessage`
4. **Se guarda todo** → El historial completo se persiste en `SESSIONS`
5. **Próximo mensaje** → El agente tiene acceso a toda la conversación anterior

## 🔄 Flujo de Memoria

```
Usuario: "Que propiedades hay?"
  ↓
[HumanMessage("Que propiedades hay?")]
  ↓
Agente: "Propiedades encontradas: - Casa Demo 7..."
  ↓
[HumanMessage("Que propiedades hay?"), AIMessage("Propiedades encontradas...")]
  ↓
Usuario: "entra en casa demo 6"
  ↓
[..., HumanMessage("entra en casa demo 6")]
  ↓
Agente: "Trabajaremos con la propiedad: Casa Demo 6..." (con contexto de mensaje anterior)
  ↓
[..., AIMessage("Trabajaremos con la propiedad...")]
```

## 📝 Notas Importantes

1. **LangGraph MemorySaver**: El agente usa `MemorySaver()` con `thread_id` para mantener estado interno
2. **Doble Persistencia**: 
   - LangGraph mantiene el estado del grafo en memoria
   - Nosotros guardamos los mensajes en `SESSIONS` para persistencia entre reinicios
3. **Session ID**: Usamos `"web-ui"` como session_id por defecto para el frontend
4. **Compatibilidad**: Sesiones antiguas sin `messages` se inicializan automáticamente

## ✅ Resultado Esperado

- ✅ El agente recuerda la conversación completa
- ✅ Puede hacer referencia a mensajes anteriores
- ✅ Mantiene contexto de la propiedad activa
- ✅ No se pierde información entre mensajes
- ✅ Funciona hasta que haya un refresh en el frontend

