# Fix: app.py Interceptaba Comandos como Preguntas

## 🔴 Problema

El usuario reportó que el agente no entiende nada. Cuando decía:

```
"Borra la propiedad que se llama 'casa'"
```

El sistema respondía con información de documentos/RAG en lugar de borrar la propiedad.

### ¿Por qué pasaba?

En `app.py` hay lógica que intercepta mensajes del usuario ANTES de que lleguen al agente:

```python
# app.py línea ~1438
question_words = ["qué", "que", "cual", "cuál", "cuando", ...]
is_question = any(w in qnorm for w in question_words)

if is_question and pid:
    # ❌ Ejecuta RAG directamente sin preguntar al agente
    result = qa_with_citations(...)
```

**El problema:** La palabra **"que"** está en la lista de palabras de pregunta.

Entonces:
- Usuario: "Borra la propiedad **que** se llama 'casa'"  
- Sistema detecta: "que" → es pregunta → ejecuta RAG  
- ❌ NUNCA llega al agente para manejar el borrado

## ✅ Solución

Agregué detección de palabras de **acción** que excluyen el tratamiento como pregunta:

```python
# Excluir si hay palabras de acción que no son preguntas
action_words = ["borra", "borrar", "elimina", "eliminar", "delete", "remove", 
                "crea", "crear", "add", "añadir", "anadir", "agrega", "agregar", 
                "sube", "subir", "upload", "pon", "poner", "set", 
                "actualiza", "actualizar", "calcula", "calcular"]
has_action = any(w in qnorm for w in action_words)

# Solo es pregunta si NO tiene palabras de acción
is_question = any(w in qnorm for w in question_words) and not is_summarize_request and not has_action
```

### Cómo funciona ahora:

```
Usuario: "Borra la propiedad que se llama 'casa'"
   ↓
Sistema detecta: "que" (palabra de pregunta) + "borra" (palabra de acción)
   ↓
has_action = True → NO es pregunta
   ↓
✅ Mensaje pasa al agente
   ↓
Agente: [Usa delete_property correctamente]
```

## 🎯 Comandos que ahora funcionan correctamente

Todos estos ahora pasan al agente en lugar de ser interceptados por RAG:

### Borrar/Eliminar
- ✅ "Borra la propiedad que se llama X"
- ✅ "Elimina esta propiedad"
- ✅ "Delete the property that is named X"

### Crear/Agregar
- ✅ "Crea una propiedad que se llame X"
- ✅ "Añade una nueva propiedad"
- ✅ "Agrega la propiedad X"

### Subir
- ✅ "Sube el documento que se llama X"
- ✅ "Upload the file that I sent"

### Actualizar/Poner
- ✅ "Pon el precio de venta que sea 50000"
- ✅ "Actualiza el valor que está en construcción"
- ✅ "Set the value that corresponds to ITP"

### Calcular
- ✅ "Calcula los números que tengo"
- ✅ "Compute the totals that we have"

## 📊 Flujo Antes vs Ahora

### ❌ Antes (Interceptado por app.py)

```
Usuario: "Borra la propiedad que se llama X"
    ↓
app.py detecta "que" → is_question = True
    ↓
app.py ejecuta RAG/qa_with_citations
    ↓
❌ Respuesta: "No aparece en los documentos. Fuentes: ..."
```

### ✅ Ahora (Pasa al agente)

```
Usuario: "Borra la propiedad que se llama X"
    ↓
app.py detecta "que" + "borra" → is_question = False
    ↓
Mensaje pasa al agente inteligente
    ↓
Agente analiza intención → delete_property
    ↓
✅ Respuesta: "¿Confirmas borrar la propiedad X?"
```

## 🔍 Problema Subyacente: Demasiada Lógica en app.py

Este fix es un **parche**, pero el problema real es más profundo:

### Problema Arquitectónico:

`app.py` tiene DEMASIADA lógica que intercepta mensajes antes de que lleguen al agente:

```python
# app.py tiene muchos if/elif que interceptan:
if _wants_list_properties(text): ...       # Regex para listar
if _wants_create_property(text): ...       # Regex para crear
if _wants_property_search(text): ...       # Regex para buscar
if _wants_uploaded_docs(text): ...         # Regex para docs
if _wants_missing_docs(text): ...          # Regex para docs faltantes
if _wants_email(text): ...                 # Regex para email
if _wants_focus_numbers(text): ...         # Regex para números
if _wants_list_numbers(text): ...          # Regex para lista números
if _wants_calc_numbers(text): ...          # Regex para calcular
if _wants_set_number(text): ...            # Regex para poner número
if is_summarize_request: ...               # Detección de resumir
if is_question: ...                        # Detección de preguntas ← ESTE FIX
# ... y muchos más
```

**Consecuencia:** El agente inteligente (que debería manejar TODAS estas cosas) casi nunca recibe los mensajes.

### Solución Ideal (Refactor Futuro):

```python
# app.py debería ser MUY simple:
def ui_chat(...):
    # 1. Procesar archivos (si hay)
    if files:
        return handle_file_upload(files)
    
    # 2. Pasar TODO lo demás al agente
    result = agent.invoke(text, property_id)
    return result
```

El agente (con herramientas) debería manejar:
- ✅ Borrar/crear/listar propiedades
- ✅ Subir/listar documentos
- ✅ Preguntas sobre documentos (RAG)
- ✅ Trabajar con números
- ✅ Enviar emails
- ✅ TODO lo demás

### Ventajas del Refactor:

1. **Más simple**: app.py <200 líneas en lugar de 1600
2. **Más robusto**: El agente maneja edge cases mejor que regex
3. **Más mantenible**: Un solo lugar para lógica de conversación
4. **Más flexible**: Fácil agregar nuevas funcionalidades
5. **Mejor UX**: El agente entiende contexto e intención mejor

## 🧪 Testing

Para verificar que el fix funciona:

```bash
# 1. Reinicia el servidor
# 2. Prueba comandos de acción con "que":

"Borra la propiedad que se llama Casa Demo"
→ ✅ Debe pedir confirmación para borrar

"Crea una propiedad que se llame Test"
→ ✅ Debe pedir nombre y dirección

"Sube el documento que mandé"
→ ✅ Debe pedir el archivo o proponer slot

"Pon el precio que corresponde a 50000"
→ ✅ Debe actualizar el número

# 3. Verifica que preguntas reales todavía funcionan:

"¿Qué documentos tengo?"
→ ✅ Debe listar documentos

"¿Cuál es el precio de venta?"
→ ✅ Debe buscar en documentos/números
```

## 📝 Próximos Pasos (Opcional)

### Quick Win (más parches):
- Agregar más action_words según se detecten problemas
- Agregar detection_words para otros flujos problemáticos

### Solución Real (refactor):
- Crear rama de refactor: `refactor/simplify-app-py`
- Mover toda la lógica de detección al agente
- Dejar app.py solo para HTTP/file handling
- Testing extensivo antes de merge

## ✅ Conclusión

Este fix resuelve el problema inmediato de comandos interceptados como preguntas.

**Pero** el sistema todavía tiene el problema arquitectónico de demasiada lógica en `app.py`. 

Para un sistema más robusto y mantenible, se recomienda el refactor completo en el futuro.

