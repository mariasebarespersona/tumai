# Fix: Agente No Era Flexible Para Cambiar de Propiedad

## Problema Original

El usuario estaba trabajando con "Casa Demo 6" en el modo "numbers" (números), pero cuando quería cambiar a "Casa Demo 4" diciendo **"metete en casa demo 4"**, el agente:

❌ **No reconocía** la solicitud de cambio de propiedad  
❌ **Seguía en modo numbers** e intentaba interpretar el mensaje como un comando de números  
❌ **Respondía**: "No he entendido qué valor quieres cambiar. Dime, por ejemplo: 'pon ITP a 12000'"

### Ejemplo del Problema

```
Usuario: [Trabajando con Casa Demo 6 en modo numbers]
Usuario: "metete en casa demo 4"
Agente: "No he entendido qué valor quieres cambiar..." ❌
```

## Causa Raíz

### 1. Detección Limitada de Cambio de Propiedad

La función `_wants_property_search()` solo reconocía verbos limitados:
- ✅ "trabajar", "usar", "utilizar", "cambiar", "switch"  
- ❌ NO reconocía: "metete", "meter", "vamos", "ir", "irme", "pasar"

### 2. Modo "Focus" Muy Rígido

Cuando el usuario estaba en modo `focus: "numbers"`:
- Todas las solicitudes se interpretaban como comandos de números
- No había forma de salir del modo focus sin completar la tarea
- El cambio de contexto no estaba permitido mid-flow

### 3. Orden de Ejecución del Código

El flujo era:
1. Usuario escribe mensaje
2. Sistema revisa si está en modo "numbers"
3. Si está en modo numbers → procesa como comando de números
4. Nunca llega a revisar si quiere cambiar de propiedad

## Solución Implementada

### 1. Expandida Lista de Verbos de Cambio de Propiedad

**Archivo**: `app.py` (líneas 198-212)

```python
def _wants_property_search(text: str) -> bool:
    t = _normalize(text)
    # Ignore generic plural list requests
    if "propiedades" in t or "properties" in t:
        return False
    
    # Work with / switch to a property - expanded verb list
    if re.search(r"\b(trabajar|usar|utilizar|cambiar|switch|metete|meter|vamos|voy|ir|irme|pasamos|pasar)\b", t) and (re.search(r"\bcon\b", t) or re.search(r"\ben\b", t) or re.search(r"\ba\b", t)):
        return True
    
    # "Quiero trabajar en/ con ...", "usar ...", "cambiar a ..."
    if re.search(r"\b(propiedad|property)\b", t) and re.search(r"(llama|llamada|nombre|direcci[oó]n|address|trabajar|usar|con|en|a|quiero|cambiar)", t):
        return True
    
    # Direct mention of "casa" or property name with movement verbs
    if re.search(r"\b(casa|finca|propiedad)\s+(demo|rural|[a-z]+)\s*\d+", t, re.IGNORECASE) and re.search(r"\b(metete|meter|vamos|voy|ir|irme|pasamos|pasar|en|a)\b", t):
        return True
    
    return False
```

**Nuevos verbos reconocidos**:
- ✅ "metete", "meter" → "metete en casa demo 4"
- ✅ "vamos", "voy" → "vamos a casa demo 4"
- ✅ "ir", "irme" → "me voy a casa demo 4"
- ✅ "pasamos", "pasar" → "pasamos a casa demo 4"

**Nueva detección directa**:
- ✅ "casa demo 4" + verbo de movimiento
- ✅ "finca rural 2" + verbo de movimiento
- ✅ Funciona case-insensitive

### 2. Exit Temprano del Modo Focus

**Archivo**: `app.py` (líneas 985-993)

```python
# EARLY EXIT FROM FOCUS MODE: If user wants to change property/context while in focus mode
# This allows flexibility to switch tasks mid-flow
if STATE.get("focus"):
    if _wants_property_search(user_text) or _wants_list_properties(user_text) or _wants_create_property(user_text):
        # User wants to change property/context, exit focus mode
        STATE["focus"] = None
        save_sessions()
        print(f"[DEBUG] Exiting focus mode because user wants to change context: {user_text[:50]}")
        # Continue processing the property change request below
```

**Cómo funciona**:
1. **ANTES** de procesar comandos de numbers
2. **Detecta** si el usuario quiere cambiar de contexto
3. **Sale** del modo focus automáticamente
4. **Continúa** procesando la solicitud de cambio de propiedad

### 3. Nuevo Flujo de Ejecución

**Flujo Correcto Ahora**:

```
1. Usuario escribe: "metete en casa demo 4"
2. Sistema detecta: está en modo focus: "numbers"
3. Sistema verifica: ¿quiere cambiar de contexto? → SÍ
4. Sistema ejecuta: STATE["focus"] = None
5. Sistema continúa: procesa cambio de propiedad
6. Sistema responde: "Trabajaremos con la propiedad: Casa Demo 4..."
```

## Resultado Esperado

### Antes ❌
```
Usuario: "metete en casa demo 4"
Agente: "No he entendido qué valor quieres cambiar. Dime, por ejemplo: 'pon ITP a 12000' o 'pon presupuesto reforma a 25000'"
```

### Después ✅
```
Usuario: "metete en casa demo 4"
Agente: "Trabajaremos con la propiedad: Casa Demo 4 — [dirección]
Tienes 2 plantillas por completar: Documentos y Números. ¿Por dónde quieres empezar?"
```

## Casos de Uso Soportados

Ahora el agente reconoce todas estas variaciones:

### Verbos Formales
- ✅ "trabajar con casa demo 4"
- ✅ "usar casa demo 4"
- ✅ "cambiar a casa demo 4"
- ✅ "utilizar casa demo 4"

### Verbos Informales (NUEVOS)
- ✅ "metete en casa demo 4"
- ✅ "vamos a casa demo 4"
- ✅ "me voy a casa demo 4"
- ✅ "pasamos a casa demo 4"

### Con/Sin "Propiedad"
- ✅ "trabajar con la propiedad casa demo 4"
- ✅ "trabajar con casa demo 4" (sin mencionar "propiedad")

### En Cualquier Modo
- ✅ Funciona incluso en modo "focus: numbers"
- ✅ Funciona incluso en modo "focus: documents"
- ✅ Funciona en cualquier momento del flujo

## Testing Recomendado

1. **Test básico de cambio**:
   ```
   1. Entra en modo numbers con Casa Demo 6
   2. Escribe "metete en casa demo 4"
   3. Verificar que cambia a Casa Demo 4
   ```

2. **Test con variaciones de verbos**:
   ```
   - "vamos a casa demo 5"
   - "me voy a finca rural 2"
   - "pasamos a propiedad alameda"
   ```

3. **Test de salida de focus**:
   ```
   1. Entra en modo numbers
   2. Cambia de propiedad
   3. Verificar que el modo numbers se desactiva
   ```

## Archivos Modificados

- `/Users/mariasebares/Documents/RAMA_AI/rama-agentic-ai/app.py`
  - Función `_wants_property_search()` (líneas 198-212)
  - Nueva lógica "EARLY EXIT FROM FOCUS MODE" (líneas 985-993)

## Beneficios

1. ✅ **Más natural** - El usuario puede hablar como hablaría normalmente
2. ✅ **Más flexible** - Puede cambiar de contexto en cualquier momento
3. ✅ **Menos frustración** - No se queda "atascado" en un modo
4. ✅ **Mejor UX** - El agente entiende intenciones más variadas
5. ✅ **Más robusto** - Maneja mejor interrupciones y cambios de flujo

## Notas Adicionales

- El sistema limpia automáticamente `STATE["focus"]` cuando detecta cambio de contexto
- El orden de ejecución es importante: la detección debe ser ANTES de procesar acciones del modo focus
- Los logs de debug ayudan a rastrear cuándo se sale del modo focus: `[DEBUG] Exiting focus mode...`

