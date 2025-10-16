# Fix: Network Errors en Herramientas de Propiedades

## 🐛 Problema Identificado

El agente mostraba errores técnicos al usuario cuando había problemas de red:
- `[Errno 51] Network is unreachable`
- `[Errno 8] nodename nor servname provided, or not known`

Estos errores aparecían cuando:
1. El agente intentaba buscar o listar propiedades
2. Había problemas temporales de conexión a Supabase
3. Las herramientas no manejaban los errores gracefully

## ✅ Solución Implementada

### 1. **Error Handling en `tools/property_tools.py`**

Agregado try-catch para manejar errores de red en ambas funciones:

```python
def list_properties(limit: int = 20) -> List[Dict]:
    try:
        return (
            sb.table("properties")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        ).data
    except Exception as e:
        import logging
        logging.error(f"Error listing properties: {e}")
        return []  # Return empty list instead of crashing


def search_properties(query: str, limit: int = 5) -> List[Dict]:
    try:
        # ... query code ...
        return result.data
    except Exception as e:
        import logging
        logging.error(f"Error searching properties: {e}")
        return []  # Return empty list instead of crashing
```

**Beneficios:**
- ✅ No crash de la aplicación
- ✅ Logging de errores para debugging
- ✅ Respuesta vacía permite al agente manejar el caso elegantemente

### 2. **SYSTEM_PROMPT Actualizado en `agentic.py`**

Agregadas instrucciones para manejo amigable de errores:

```
ERRORES Y MANEJO DE FALLOS
- Si `search_properties` o `list_properties` devuelven lista vacía, puede ser un error 
  temporal de conexión. Informa al usuario que hay un problema de conexión y pídele que 
  reintente en un momento.
- NUNCA muestres errores técnicos como "[Errno 8]" o "Network is unreachable" al usuario. 
  En su lugar, di "Hay un problema temporal de conexión. Por favor, inténtalo de nuevo en 
  un momento."
```

### 3. **Comportamiento Antes vs Después**

**ANTES:**
```
User: ¿en qué propiedad estoy?
Agent: No he podido buscar propiedades: [Errno 51] Network is unreachable
```

**DESPUÉS:**
```
User: ¿en qué propiedad estoy?
Agent: Hay un problema temporal de conexión con la base de datos. 
       Por favor, inténtalo de nuevo en un momento.
```

## 🔧 Casos de Uso Manejados

1. **Error de red temporal**: Devuelve lista vacía → agente responde con mensaje amigable
2. **Error DNS**: Devuelve lista vacía → agente responde con mensaje amigable
3. **Timeout**: Devuelve lista vacía → agente responde con mensaje amigable
4. **Conexión exitosa pero sin resultados**: Devuelve lista vacía → agente sugiere alternativas

## 📊 Logging

Los errores se registran en los logs del servidor para debugging:

```
[ERROR] Error searching properties: [Errno 8] nodename nor servname provided
[ERROR] Error listing properties: [Errno 51] Network is unreachable
```

Esto permite:
- ✅ Detectar problemas de infraestructura
- ✅ Monitorear la salud de la conexión a Supabase
- ✅ No exponer detalles técnicos al usuario

## 🎯 Testing

Para verificar que funciona:

1. **Simular error de red** (opcional):
   ```python
   # Temporalmente romper la conexión
   os.environ['SUPABASE_URL'] = 'https://invalid-url.com'
   ```

2. **Preguntar al agente**:
   ```
   User: ¿qué propiedades tengo?
   Agent: Hay un problema temporal de conexión...
   ```

3. **Verificar logs**:
   ```bash
   tail -f /tmp/rama_uvicorn.log | grep ERROR
   ```

## ✅ Estado Actual

- ✅ Error handling en `list_properties`
- ✅ Error handling en `search_properties`
- ✅ SYSTEM_PROMPT actualizado con instrucciones
- ✅ Logging de errores para debugging
- ✅ Mensajes amigables al usuario
- ✅ No crashes de la aplicación

## 🚀 Próximos Pasos (Opcional)

Si los errores de red persisten frecuentemente:

1. **Retry logic**: Reintentar automáticamente 2-3 veces
2. **Circuit breaker**: Detectar cuando Supabase está down y cache local
3. **Health check**: Endpoint `/health` que verifique conectividad
4. **Monitoring**: Alertas cuando hay > X errores en Y minutos

## 📝 Notas Adicionales

- Los errores de red son **temporales** y suelen resolverse solos
- Si persisten, verificar:
  - Conectividad a Internet
  - Estado de Supabase (status.supabase.com)
  - Límites de rate limiting
  - Configuración de firewall/VPN

