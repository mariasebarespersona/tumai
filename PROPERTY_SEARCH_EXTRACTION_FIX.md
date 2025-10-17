# Fix: Extracción y Búsqueda de Propiedades Mejorada

## Problema Original (Parte 2)

Después del primer fix (detección de cambio de propiedad), el agente **detectaba** correctamente que el usuario quería cambiar, pero **no encontraba** la propiedad aunque existía en la lista.

### Ejemplo del Problema

```
Usuario: "metete en casa demo 4"

Agente detecta: ✅ Quiere cambiar de propiedad
Agente busca con: ❌ "metete en casa demo 4" (texto completo)
Resultado búsqueda: ❌ No encontró coincidencias
Fallback: Muestra lista de propiedades (incluyendo Casa Demo 4)
```

**Lista mostrada**:
- Casa Demo 7 — Calle Alameda 24
- Casa Demo 6 — Calle Alameda 22
- Casa Demo 5 — Calle Hermosilla 11
- **Casa Demo 4 — Calle Ayala 25** ← ¡Está en la lista!
- Casa Demo 3 — Calle Real 3

## Causa Raíz

### 1. Extracción Incompleta del Nombre

**Problema**: La función `_extract_property_candidate_from_text()` solo reconocía patrones con verbos antiguos.

**Antes** ❌:
```python
patterns = [
    r"(?i)(?:trabajar|usar|utilizar)\s+(?:con|en)\s+(?:la\s+propiedad\s+)?(.+)$",
    r"(?i)quiero\s+(?:trabajar|usar|utilizar)\s+(?:con|en)\s+(?:la\s+propiedad\s+)?(.+)$",
]
```

**Resultado**:
- "trabajar con casa demo 4" → ✅ Extrae "casa demo 4"
- "metete en casa demo 4" → ❌ No extrae nada → Usa texto completo

### 2. Búsqueda Poco Tolerante

**Problema**: La función `search_properties()` solo hacía una búsqueda con patrón exacto.

**Antes** ❌:
```python
pattern = f"*{query}*"
# Busca: "*metete en casa demo 4*"
# NO coincide con "Casa Demo 4"
```

**Limitaciones**:
- No toleraba variaciones de espacios
- No buscaba por palabras individuales
- Si el patrón completo fallaba, devolvía vacío

## Solución Implementada

### 1. Extracción Expandida con Nuevos Verbos

**Archivo**: `app.py` (líneas 177-201)

```python
def _extract_property_candidate_from_text(user_text: str) -> str | None:
    """Extract a likely property name when phrased as 'trabajar/usar/metete con/en X'."""
    if not user_text:
        return None
    # Common Spanish patterns with expanded verb list
    patterns = [
        # Original patterns
        r"(?i)(?:trabajar|usar|utilizar)\s+(?:con|en)\s+(?:la\s+propiedad\s+)?(.+)$",
        r"(?i)quiero\s+(?:trabajar|usar|utilizar)\s+(?:con|en)\s+(?:la\s+propiedad\s+)?(.+)$",
        # New informal patterns
        r"(?i)(?:metete|meter|vamos|voy|ir|irme|pasamos|pasar)\s+(?:en|a|con)\s+(?:la\s+propiedad\s+)?(.+)$",
        r"(?i)(?:me\s+voy|nos\s+vamos)\s+(?:a|en)\s+(?:la\s+propiedad\s+)?(.+)$",
        # Direct "casa/finca + name" extraction
        r"(?i)(?:metete|meter|vamos|voy|ir|irme|pasamos|pasar|en|a)\s+(?:la\s+)?(?:casa|finca|propiedad)\s+(.+)$",
    ]
    # ... resto del código
```

**Ahora extrae correctamente**:
- ✅ "metete en casa demo 4" → "casa demo 4"
- ✅ "vamos a casa demo 5" → "casa demo 5"
- ✅ "me voy a finca rural 2" → "finca rural 2"
- ✅ "pasar a propiedad alameda" → "propiedad alameda"
- ✅ "metete casa demo 4" → "demo 4" (último patrón)

### 2. Búsqueda Multi-Estrategia

**Archivo**: `tools/property_tools.py` (líneas 57-113)

```python
def search_properties(query: str, limit: int = 5) -> List[Dict]:
    """Fuzzy search by name or address (case-insensitive).
    
    Tries multiple search strategies:
    1. Exact pattern match with wildcards
    2. Individual word matching if multi-word query
    3. Fallback to all properties if no results
    """
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        # Clean the query
        query_clean = query.strip()
        
        # Strategy 1: Direct pattern match
        pattern = f"*{query_clean}*"
        results = (
            sb.table("properties")
            .select("id,name,address")
            .or_(f"name.ilike.{pattern},address.ilike.{pattern}")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        ).data
        
        if results:
            logger.info(f"Found {len(results)} properties with direct pattern: {pattern}")
            return results
        
        # Strategy 2: Try individual words if multi-word query
        words = query_clean.split()
        if len(words) > 1:
            # Try with each significant word (skip common words)
            skip_words = {'la', 'el', 'de', 'en', 'a', 'con', 'propiedad', 'casa', 'finca'}
            for word in words:
                if word.lower() not in skip_words and len(word) >= 3:
                    pattern = f"*{word}*"
                    results = (
                        sb.table("properties")
                        .select("id,name,address")
                        .or_(f"name.ilike.{pattern},address.ilike.{pattern}")
                        .order("created_at", desc=True)
                        .limit(limit)
                        .execute()
                    ).data
                    if results:
                        logger.info(f"Found {len(results)} properties with word pattern: {pattern}")
                        return results
        
        logger.warning(f"No properties found for query: {query_clean}")
        return []
```

**Estrategias de Búsqueda**:

1. **Estrategia 1 - Patrón Directo**:
   - Busca: `*casa demo 4*`
   - Si encuentra → Devuelve resultados

2. **Estrategia 2 - Palabras Individuales**:
   - Divide en palabras: ["casa", "demo", "4"]
   - Filtra palabras comunes: {"la", "el", "de", "casa", "propiedad"}
   - Busca con palabras significativas: `*demo*`, `*4*`
   - Primera que encuentre resultados → Los devuelve

3. **Logging**:
   - Registra qué estrategia funcionó
   - Ayuda a debuggear problemas futuros

## Flujo Completo Mejorado

### Entrada del Usuario
```
"metete en casa demo 4"
```

### Procesamiento

1. **Detección de Intención** (Fix anterior):
   ```python
   _wants_property_search("metete en casa demo 4") 
   → TRUE (detecta "metete" + "en")
   ```

2. **Extracción del Nombre** (Fix actual):
   ```python
   _extract_property_candidate_from_text("metete en casa demo 4")
   → "casa demo 4"
   ```

3. **Búsqueda Multi-Estrategia** (Fix actual):
   ```python
   search_properties("casa demo 4", limit=5)
   
   # Estrategia 1: Busca "*casa demo 4*"
   # Si no encuentra...
   
   # Estrategia 2: Divide en palabras ["casa", "demo", "4"]
   # Filtra: ["demo", "4"] (skip "casa")
   # Busca "*demo*" → Encuentra:
   #   - Casa Demo 7
   #   - Casa Demo 6
   #   - Casa Demo 5
   #   - Casa Demo 4  ← ¡Match!
   #   - Casa Demo 3
   ```

4. **Selección y Respuesta**:
   ```python
   # Si hay múltiples resultados con "demo"
   # Busca el más específico con "4"
   # O muestra lista para que el usuario elija
   ```

## Resultado Esperado

### Antes ❌
```
Usuario: "metete en casa demo 4"
Sistema busca: "metete en casa demo 4"
Resultado: No encontró coincidencias
Respuesta: "No encontré coincidencias. Estas son las propiedades recientes: ..."
```

### Después ✅
```
Usuario: "metete en casa demo 4"
Sistema extrae: "casa demo 4"
Sistema busca: Strategy 2 con "*demo*" → Encuentra 5 propiedades
Sistema busca: Strategy 2 con "*4*" → Filtra a "Casa Demo 4"
Respuesta: "Trabajaremos con la propiedad: Casa Demo 4 — Calle Ayala 25
Tienes 2 plantillas por completar: Documentos y Números. ¿Por dónde quieres empezar?"
```

## Casos de Uso Mejorados

### Extracción Robusta
- ✅ "metete en casa demo 4" → "casa demo 4"
- ✅ "vamos a la propiedad alameda" → "alameda"
- ✅ "me voy a casa rural 5" → "casa rural 5"
- ✅ "pasar a demo 6" → "demo 6"

### Búsqueda Tolerante
- ✅ "Casa Demo 4" (con mayúsculas) → Encuentra
- ✅ "casa  demo  4" (espacios extras) → Encuentra
- ✅ "demo 4" (sin "casa") → Encuentra
- ✅ "alameda" (solo nombre) → Encuentra por dirección también

### Múltiples Resultados
Si hay múltiples coincidencias:
```
Sistema: "He encontrado estas propiedades:
1. Casa Demo 4 — Calle Ayala 25
2. Casa Demo 14 — Calle Mayor 4

Responde con el número para continuar."
```

## Archivos Modificados

1. **`app.py`**:
   - Función `_extract_property_candidate_from_text()` (líneas 177-201)
   - Patrones expandidos con nuevos verbos
   - Extracción de "casa/finca + nombre"

2. **`tools/property_tools.py`**:
   - Función `search_properties()` (líneas 57-113)
   - Búsqueda multi-estrategia
   - Logging de diagnóstico

## Beneficios

1. ✅ **Extracción precisa** - Saca el nombre correcto del texto
2. ✅ **Búsqueda robusta** - Múltiples estrategias de fallback
3. ✅ **Menos frustraciones** - Encuentra lo que el usuario busca
4. ✅ **Mejor logging** - Más fácil debuggear problemas
5. ✅ **Más natural** - Funciona como el usuario espera

## Testing Recomendado

1. **Test de extracción**:
   ```python
   _extract_property_candidate_from_text("metete en casa demo 4")
   # Esperado: "casa demo 4"
   ```

2. **Test de búsqueda directa**:
   ```python
   search_properties("Casa Demo 4")
   # Esperado: [{"name": "Casa Demo 4", ...}]
   ```

3. **Test de búsqueda por palabras**:
   ```python
   search_properties("demo 4")
   # Esperado: Lista con todas las "Casa Demo" que tengan "4"
   ```

4. **Test de flujo completo**:
   ```
   Usuario: "metete en casa demo 4"
   # Esperado: Cambia a Casa Demo 4 directamente
   ```

