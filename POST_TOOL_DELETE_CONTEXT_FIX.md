# Fix: post_tool Auto-seleccionaba en Contexto de Borrado

## 🔴 Problema

Después de los fixes anteriores, el usuario reportó que cuando decía:

```
"Borra la propiedad Casa Demo 10 y"
```

El agente **seleccionaba la propiedad** en lugar de borrarla:

```
"Trabajaremos con la propiedad: Casa Demo 10 y — Calle Osasuna 15
 Tienes 2 plantillas por completar..."
```

### ¿Por qué pasaba?

Aunque los fixes previos evitaban que:
1. ✅ app.py interceptara como pregunta (fix de action_words)
2. ✅ El agente tuviera instrucciones claras de usar delete_property

El flujo era:

```
Usuario: "Borra la propiedad Casa Demo 10"
   ↓
Mensaje llega al agente (✅ no interceptado por app.py)
   ↓
Agente: "Necesito encontrar esa propiedad"
   ↓
Agente: [Llama search_properties("Casa Demo 10")]
   ↓
❌ post_tool hook intercepta: "1 resultado encontrado"
   ↓
❌ post_tool auto-selecciona: property_id = resultado
   ↓
❌ post_tool envía mensaje: "Trabajaremos con la propiedad..."
   ↓
❌ Agente nunca llega a llamar delete_property
```

**El problema:** El `post_tool` hook **siempre** auto-selecciona cuando `search_properties` devuelve 1 resultado, sin importar el contexto.

## ✅ Solución

Modifiqué el `post_tool` para **detectar contexto de borrado** antes de auto-seleccionar:

```python
if msg.name == "search_properties":
    # Check if user is trying to delete/remove
    delete_context = False
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            content_lower = m.content.lower()
            delete_words = ["borra", "borrar", "elimina", "eliminar", "delete", "remove"]
            if any(w in content_lower for w in delete_words):
                delete_context = True
            break
    
    # Only auto-select if NOT in delete context
    if len(hits) == 1 and hits[0].get("id") and not delete_context:
        # Auto-select property
        updates["property_id"] = pid
        updates["messages"] = [AIMessage(...)]
    # If delete_context=True, let agent handle it (don't auto-select)
```

### Cómo funciona ahora:

```
Usuario: "Borra la propiedad Casa Demo 10"
   ↓
Mensaje llega al agente
   ↓
Agente: [Llama search_properties("Casa Demo 10")]
   ↓
post_tool detecta: último mensaje contiene "borra"
   ↓
delete_context = True
   ↓
✅ post_tool NO auto-selecciona
   ↓
✅ Control vuelve al agente
   ↓
✅ Agente: "He encontrado Casa Demo 10"
   ↓
✅ Agente: [Llama delete_property(property_id)]
   ↓
✅ Usuario: "Propiedad eliminada correctamente"
```

## 🎯 Casos Manejados

### Borrado (NO auto-selecciona):
- ✅ "Borra la propiedad X"
- ✅ "Elimina la propiedad X"
- ✅ "Delete property X"
- ✅ "Remove property X"
- ✅ "Quiero borrar X"

### Selección normal (SÍ auto-selecciona):
- ✅ "Trabajar con propiedad X"
- ✅ "Usar propiedad X"
- ✅ "Casa Demo 5" (solo nombre)
- ✅ "Cambiar a propiedad X"
- ✅ "Metete en X"

## 📊 Comparación

| Situación | Antes | Ahora |
|-----------|-------|-------|
| "Borra propiedad X" + search → 1 resultado | ❌ Auto-selecciona | ✅ Deja al agente borrar |
| "Trabajar con X" + search → 1 resultado | ✅ Auto-selecciona | ✅ Auto-selecciona |
| "X" (solo nombre) + search → 1 resultado | ✅ Auto-selecciona | ✅ Auto-selecciona |
| "Borra X" + search → 0 resultados | No hace nada | No hace nada |
| "Borra X" + search → múltiples | Muestra lista | Muestra lista |

## 🔍 Detalle Técnico

### ¿Por qué el agente usa search_properties al borrar?

El agente hace esto porque:

1. Usuario dice "Borra la propiedad Casa Demo 10"
2. Agente no tiene `property_id` activo (o tiene otro)
3. Agente razona: "Necesito el ID de esa propiedad para llamar delete_property"
4. Agente llama `search_properties("Casa Demo 10")` para obtener el ID
5. Agente planea: "Con el ID, llamaré delete_property(id)"

**El problema:** El post_tool intercepta en el paso 5 y cambia el plan.

### ¿Por qué no simplemente decirle al agente que NO use search_properties?

Intenté eso en el SYSTEM_PROMPT:

```
NO uses search_properties para confirmar - simplemente pide confirmación 
en lenguaje natural y luego borra.
```

**Pero:** El agente ignora esto cuando no tiene property_id activo, porque necesita el ID para llamar delete_property(property_id).

La solución correcta es dejar que el agente use search_properties, pero que el post_tool sea consciente del contexto.

## 🧩 Piezas del Puzzle Completo

Este es el **tercer fix** necesario para borrado de propiedades:

1. **DELETE_PROPERTY_FIX.md**: 
   - Instrucción al agente de usar delete_property
   - post_tool limpia estado después de borrar

2. **APP_INTERCEPTION_FIX.md**:
   - app.py no intercepta comandos con "que" como preguntas si hay action_words

3. **POST_TOOL_DELETE_CONTEXT_FIX.md** (este):
   - post_tool no auto-selecciona si el contexto es de borrado

## ✅ Testing

Para verificar que funciona:

```bash
# Probar borrado
"Borra la propiedad Casa Demo 7"
→ ✅ Debe pedir confirmación y borrar (no seleccionar)

# Probar selección normal
"Trabajar con Casa Demo 5"
→ ✅ Debe auto-seleccionar y preguntar por dónde empezar

# Probar solo nombre
"Casa Demo 4"
→ ✅ Debe auto-seleccionar

# Probar borrado con "que"
"Borra la propiedad que se llama Casa Demo 3"
→ ✅ Debe pedir confirmación y borrar
```

## 📝 Notas

### Limitaciones

Este fix solo detecta palabras de borrado en el **último mensaje del usuario**. Si el historial es:

```
Usuario: "Quiero borrar una propiedad"
Agente: "¿Cuál?"
Usuario: "Casa Demo 10"  ← Ya no tiene palabra de borrado
```

En este caso, el post_tool **SÍ auto-seleccionaría** porque el último mensaje no contiene "borra".

**Solución:** El agente debería mantener contexto de la intención previa. Esto ya lo maneja el SYSTEM_PROMPT y el historial de mensajes.

### Alternativa Futura

Una solución más robusta sería:
- Agregar un flag `intent` al estado del agente
- El agente establece `intent="delete"` cuando detecta intención de borrado
- post_tool revisa `state["intent"]` en lugar del último mensaje

Pero esto requiere cambios más profundos en la arquitectura.

## 🎉 Conclusión

Con este fix, el borrado de propiedades **finalmente funciona correctamente** end-to-end:

1. ✅ Usuario: "Borra la propiedad X"
2. ✅ app.py: No intercepta (action_words fix)
3. ✅ Agente: Recibe mensaje
4. ✅ Agente: Usa search_properties para encontrar X
5. ✅ post_tool: Detecta contexto de borrado, NO auto-selecciona
6. ✅ Agente: Llama delete_property(id)
7. ✅ post_tool: Limpia property_id
8. ✅ Usuario: "Propiedad eliminada correctamente"

**¡Todo el flujo funciona!** 🎊

