# 🔧 Fix: Extracción de Fechas para Recordatorios

## 🐛 Problema Identificado

Cuando el usuario decía:
```
"Mandame un recordatorio el día que haya que pagar al arquitecto cada mes"
```

El agente:
- ✅ Detectaba correctamente "cada mes" → `recurrence="monthly"`
- ✅ Creaba 12 recordatorios
- ❌ **Pero usaba fecha incorrecta (día 11) en lugar de extraer del documento (día 5)**

**Causa raíz**: El agente NO estaba llamando a `extract_payment_date` para leer el documento y extraer la fecha correcta. Estaba inventando la fecha.

## ✅ Solución Implementada

### 1. **Guarda en `assistant()` con Inyección de Instrucciones**
Cuando detecta el patrón `"recordatorio" + "cada mes" + "dia que haya que pagar"`:
- Inyecta un `SystemMessage` con instrucciones **paso a paso** OBLIGATORIAS
- Le dice al LLM exactamente qué herramientas llamar y en qué orden
- **NO fuerza la llamada**, deja que el LLM ejecute el flujo completo

```python
# Inyectar instrucción clara para que el LLM haga el flujo correcto
msgs.append(SystemMessage(content=f"""⚠️ FLUJO OBLIGATORIO PARA RECORDATORIO MENSUAL:

1. Llama list_docs(property_id="{state['property_id']}")
2. Identifica el documento relacionado con '{doc_name_hint}' (busca en nombre o grupo)
3. CRÍTICO: Llama extract_payment_date con:
   - property_id: "{state['property_id']}"
   - document_group, document_subgroup, document_name del documento encontrado
   - payment_concept: "{payment_concept}"
4. Usa la fecha extraída para create_reminder:
   - reminder_date: (fecha extraída de extract_payment_date)
   - recurrence: "monthly"
   - recurrence_count: 12
   
NO uses fechas inventadas. USA extract_payment_date SIEMPRE."""))
```

### 2. **SYSTEM_PROMPT Mejorado**
Agregué sección explícita con ejemplos de ❌ MAL vs ✅ BIEN:

```markdown
FLUJO: RECORDATORIOS (NUEVO)
- **🚨 OBLIGATORIO: EXTRACCIÓN DE FECHAS DE DOCUMENTOS 🚨**
  * Si el usuario dice "el día que haya que pagar X" o "cuando haya que pagar X":
    1. **PASO 1**: Llama `list_docs` para encontrar el documento relevante
    2. **PASO 2 (CRÍTICO)**: Llama `extract_payment_date` con document info
    3. **PASO 3**: La herramienta hace RAG/QA sobre el documento
    4. **PASO 4**: Usa la fecha extraída en `create_reminder`

- **EJEMPLOS OBLIGATORIOS**:
  * ❌ **MAL**: crear recordatorio con fecha inventada (día 11)
  * ✅ **BIEN**: list_docs → extract_payment_date → create_reminder con fecha extraída (día 5)
```

## 🎯 Flujo Esperado Ahora

```
Usuario: "Mandame un recordatorio el día que haya que pagar al arquitecto cada mes"

Agente (paso a paso):
1. 🔍 Detecta: "recordatorio" + "cada mes" + "dia que haya que pagar"
2. 💉 Inyecta SystemMessage con flujo obligatorio
3. 📋 Llama list_docs → encuentra "Contrato arquitecto"
4. 🔎 Llama extract_payment_date:
   - property_id: <current>
   - document_group: "Administrativos"
   - document_subgroup: "Contratos"
   - document_name: "Contrato arquitecto"
   - payment_concept: "pago al arquitecto"
5. 📄 extract_payment_date hace QA sobre el documento:
   - Pregunta: "¿Cuál es la fecha de pago para pago al arquitecto?"
   - RAG/QA lee el contenido
   - Encuentra: "El pago se realizará el día 5 de cada mes"
   - Extrae: "día 5"
6. ✅ Llama create_reminder:
   - reminder_date: "día 5"
   - recurrence: "monthly"
   - recurrence_count: 12
7. 🎉 Responde: "✅ 12 recordatorios creados: 'Pago al arquitecto' desde 5 de enero de 2025 hasta 5 de diciembre de 2025"
```

## 🧪 Cómo Probar

1. **Asegúrate de tener el documento subido**:
   ```
   "Contrato arquitecto" con texto: "El pago se realizará el día 5 de cada mes"
   ```

2. **Pregunta primero**:
   ```
   Usuario: "¿Qué día hay que pagar al arquitecto?"
   Agente: "El día 5 de cada mes" (para confirmar que el documento está bien)
   ```

3. **Crea el recordatorio**:
   ```
   Usuario: "Mandame un recordatorio el día que haya que pagar al arquitecto cada mes"
   Agente: [Debe hacer RAG y usar día 5, NO día 11]
   ```

## 📝 Archivos Modificados

- **agentic.py**:
  - Nueva guarda en `assistant()` que detecta el patrón e inyecta instrucciones
  - SYSTEM_PROMPT mejorado con sección "FLUJO: RECORDATORIOS"
  - Ejemplos explícitos de ❌ MAL vs ✅ BIEN

## 🎯 Estado

- ✅ Guarda implementada
- ✅ Prompt mejorado con ejemplos
- ✅ Instrucciones paso a paso inyectadas
- ⏳ **PENDIENTE**: Probar en el chat real

---

**NOTA**: El servidor Uvicorn recargará automáticamente. Prueba de nuevo y debería funcionar correctamente ahora.
