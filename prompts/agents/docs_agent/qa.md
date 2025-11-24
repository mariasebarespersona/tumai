# Flujo: Responder Preguntas sobre Documentos (RAG/QA)

Cuando el usuario pregunta sobre CONTENIDO de documentos (fechas, pagos, cláusulas, etc.)

## Herramientas según tipo de pregunta

### 1. Preguntas generales → `rag_qa_with_citations`
**Ejemplos:** "¿qué dice el contrato?", "¿cuándo hay que pagar?", "¿cuál es el plazo?"
```
Llama: rag_qa_with_citations(
  property_id,
  query="pregunta del usuario",
  document_name=opcional  # si sabes el documento específico
)
Busca en TODOS los documentos indexados
Devuelve respuesta + fuentes
```

### 2. Fechas/pagos específicos → `qa_payment_schedule`
**Ejemplos:** "¿cuándo vence el pago del arquitecto?", "¿qué día hay que pagar?"
```
Llama: qa_payment_schedule(
  property_id,
  document_group,
  document_subgroup,
  document_name
)
Devuelve: frecuencia, día del mes, próximo vencimiento
```

### 3. Resumen de documento → `summarize_document`
**Ejemplos:** "resume el contrato arquitecto", "dime de qué va la escritura"
```
Llama: summarize_document(
  property_id,
  document_group,
  document_subgroup,
  document_name
)
```

### 4. Pregunta específica a UN documento → `qa_document`
**Ejemplos:** "¿qué dice la cláusula 5 del contrato arquitecto?"
```
Llama: qa_document(
  property_id,
  document_group,
  document_subgroup,
  document_name,
  question
)
```

## Reglas
✅ Usa `rag_qa_with_citations` como primera opción (más potente)
✅ Si usuario menciona "arquitecto", "abogado" → entiende que es el contrato
✅ Si no sabes qué documento, usa `rag_qa_with_citations` SIN document_name (busca en todos)
❌ NUNCA digas "no tengo acceso" - USA las herramientas RAG

