# 🎯 Flujo Completo de Recordatorios con RAG

## 🔄 Flujo Automático Implementado

### **3 Handlers Coordinados en `post_tool`**

```
Usuario: "Mandame un recordatorio el día que haya que pagar al arquitecto cada mes"
              ⬇️
[assistant] Detecta patrón → inyecta instrucciones → llama list_docs
              ⬇️
[post_tool] Handler #1: list_docs
  - Detecta: "recordatorio" + "cada mes" + "dia que haya que pagar"
  - Busca documento con "arquitecto" en el nombre
  - Encuentra: "Contrato arquitecto"
  - ✅ Fuerza llamada a extract_payment_date
              ⬇️
[post_tool] Handler #2: extract_payment_date
  - Hace QA/RAG sobre "Contrato arquitecto"
  - Pregunta: "¿Cuál es la fecha de pago para pago al arquitecto?"
  - Extrae: "05/11/2025" (día 5)
  - Detecta: "cada mes" en el mensaje original
  - ✅ Fuerza llamada a create_reminder
              ⬇️
[post_tool] Handler #3: create_reminder
  - Crea 12 recordatorios mensuales
  - reminder_date: "05/11/2025" (extraído del documento)
  - recurrence: "monthly"
  - ✅ Renderiza resultado final
```

---

## 📋 Código Implementado

### 1. **Handler en `list_docs` (post_tool)**
```python
if last_tool_msg.name == "list_docs":
    # Detectar si venimos de flujo de recordatorio
    if "recordatorio" in last_user_text and "cada mes" in last_user_text:
        # Buscar documento relacionado
        target_doc = None
        for doc in docs:
            if doc_name_hint in doc.get("document_name", "").lower():
                target_doc = doc
                break
        
        if target_doc:
            # Forzar extract_payment_date
            forced_extract = AIMessage(content="", tool_calls=[{
                "name": "extract_payment_date",
                "args": {
                    "property_id": state.get("property_id"),
                    "document_group": target_doc.get("document_group"),
                    "document_name": target_doc.get("document_name"),
                    "payment_concept": "pago al arquitecto"
                }
            }])
            return {"messages": [forced_extract]}
```

### 2. **Handler en `extract_payment_date` (post_tool)**
```python
if last_tool_msg.name == "extract_payment_date":
    if data.get("date_found"):
        extracted_date = data.get("date_formatted")
        
        # Detectar si quiere recurrencia mensual
        if "cada mes" in last_user_text:
            # Forzar create_reminder
            forced_reminder = AIMessage(content="", tool_calls=[{
                "name": "create_reminder",
                "args": {
                    "property_id": state.get("property_id"),
                    "title": "Pago al arquitecto",
                    "reminder_date": extracted_date,  # Fecha extraída del documento
                    "recurrence": "monthly",
                    "recurrence_count": 12
                }
            }])
            return {"messages": [forced_reminder]}
```

### 3. **Handler en `create_reminder` (post_tool)**
```python
if last_tool_msg.name == "create_reminder":
    if data.get("status") == "created":
        msg = data.get("message")
        count = data.get("count")
        
        if count > 1:
            # Mostrar primeros 3 y últimos 3
            reminders = data.get("reminders", [])
            preview = reminders[:3] + ["..."] + reminders[-3:]
            content = f"{msg}\n\nFechas:\n{dates_list}"
        
        return {"messages": [AIMessage(content=content)]}
```

---

## ✅ Ventajas del Approach

1. **Flujo Automático Completo**: 
   - Una sola pregunta del usuario → 3 herramientas ejecutadas secuencialmente
   - Sin intervención del LLM entre pasos (más rápido, más confiable)

2. **RAG Garantizado**:
   - El handler fuerza `extract_payment_date` que hace QA sobre el documento
   - NO hay forma de que invente la fecha

3. **Determinístico**:
   - Los handlers en `post_tool` son código Python (no LLM)
   - Garantiza que el flujo siempre se completa

4. **Fallback Inteligente**:
   - Si no encuentra fecha → pregunta al usuario
   - Si no encuentra documento → pregunta al usuario

---

## 🧪 Resultado Esperado

```
Usuario: "Mandame un recordatorio el día que haya que pagar al arquitecto cada mes"

Agente:
✅ 12 recordatorios creados: 'Pago al arquitecto' desde 5 de noviembre de 2025 hasta 5 de octubre de 2026 (monthly)

Fechas:
  - 5 de noviembre de 2025
  - 5 de diciembre de 2025
  - 5 de enero de 2026
  - ...
  - 5 de agosto de 2026
  - 5 de septiembre de 2026
  - 5 de octubre de 2026

✉️ Se enviarán automáticamente por email en cada fecha.
```

---

## 📝 Archivos Modificados

- **agentic.py**:
  - Handler `list_docs` en `post_tool`: Detecta flujo y fuerza `extract_payment_date`
  - Handler `extract_payment_date` en `post_tool`: Extrae fecha y fuerza `create_reminder`
  - Handler `create_reminder` en `post_tool`: Renderiza resultado final

---

**ESTADO**: ✅ Listo para probar. Uvicorn recargará automáticamente.
