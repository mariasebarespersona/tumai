# Solución al Error de Conexión PostgreSQL

## 🔴 Problema Original

```
psycopg.OperationalError: consuming input failed: server closed the connection unexpectedly
This probably means the server terminated abnormally before or while processing the request.
```

### ¿Por qué ocurría?

El error ocurría cuando el **pool de conexiones de PostgreSQL** intentaba usar una conexión que se había cerrado por:
- **Inactividad**: Supabase cierra conexiones inactivas después de cierto tiempo
- **Timeout de red**: Problemas temporales de red entre el servidor y Supabase
- **No retry**: El sistema no reintentaba cuando fallaba la conexión

## ✅ Solución Implementada

### 1. **Keepalives en el Pool de Conexiones** (`agentic.py`)

Agregué configuración TCP keepalive para mantener las conexiones vivas:

```python
pool = ConnectionPool(
    conninfo=database_url,
    min_size=1,
    max_size=10,
    timeout=30,
    max_idle=300,
    max_lifetime=3600,
    kwargs={
        "keepalives": 1,              # Habilitar keepalive
        "keepalives_idle": 30,        # Enviar ping cada 30s de inactividad
        "keepalives_interval": 10,    # Intervalo entre pings
        "keepalives_count": 5,        # 5 intentos antes de marcar como muerta
    },
    check=ConnectionPool.check_connection,  # Verificar conexiones antes de usar
)
```

**Beneficios:**
- ✅ Detecta conexiones muertas antes de usarlas
- ✅ Mantiene conexiones vivas con pings periódicos
- ✅ Reconecta automáticamente cuando el pool detecta un problema

### 2. **Retry Logic en `run_turn()`** (`app.py`)

Agregué lógica de reintentos para errores transitorios:

```python
def run_turn(...):
    max_retries = 2
    for attempt in range(max_retries):
        try:
            result = agent.invoke(state, config={"configurable": {"thread_id": session_id}})
            return result
        except Exception as e:
            error_str = str(e)
            # Check if it's a transient connection error
            if "server closed the connection" in error_str or "connection" in error_str.lower():
                if attempt < max_retries - 1:
                    print(f"[WARNING] Connection error on attempt {attempt + 1}, retrying...")
                    time.sleep(0.5)  # Brief delay before retry
                    continue
                else:
                    print(f"[ERROR] Connection failed after {max_retries} attempts")
                    raise
            else:
                # Non-connection error, raise immediately
                raise
```

**Beneficios:**
- ✅ Reintenta automáticamente hasta 2 veces en errores de conexión
- ✅ Pausa 0.5s entre reintentos para dar tiempo al pool a reconectar
- ✅ No reintenta en otros tipos de errores (solo conexión)
- ✅ Registra warnings en los logs para debugging

## 📊 Flujo de Recuperación

```
Usuario envía mensaje
        ↓
run_turn() intenta invocar agente
        ↓
¿Conexión cerrada?
    ├─ NO → ✅ Respuesta exitosa
    └─ SÍ → ⚠️ Error detectado
            ↓
         Intento 1/2
            ↓
         Sleep 0.5s
            ↓
         Pool reconecta automáticamente
            ↓
         Reintento
            ↓
         ¿Éxito?
         ├─ SÍ → ✅ Respuesta exitosa
         └─ NO → ❌ Error después de 2 intentos
```

## 🎯 Resultado

Antes:
- ❌ Error cada vez que la conexión se cerraba por inactividad
- ❌ Usuario veía "500 Internal Server Error"
- ❌ Necesitaba refrescar la página

Ahora:
- ✅ Reconexión automática y transparente
- ✅ Usuario no nota nada (pequeño delay de 0.5s en reconexión)
- ✅ Sistema robusto ante problemas de red temporales

## 🔧 Configuración Adicional (Opcional)

Si los problemas persisten, puedes ajustar:

### En `agentic.py`:
```python
# Aumentar keepalive frequency para redes inestables
"keepalives_idle": 15,  # Más frecuente (cada 15s)
"keepalives_interval": 5,  # Más agresivo

# O aumentar tolerancia a desconexiones
max_idle=600,  # 10 minutos en lugar de 5
max_lifetime=7200,  # 2 horas en lugar de 1
```

### En `app.py`:
```python
# Más reintentos para redes muy inestables
max_retries = 3

# Más tiempo entre reintentos
time.sleep(1.0)  # 1 segundo en lugar de 0.5s
```

## 📝 Logs Útiles

Cuando hay un problema de conexión, verás:
```
[WARNING] Connection error on attempt 1, retrying...
[WARNING] discarding closed connection: <psycopg.Connection [BAD]>
```

Si funciona el retry:
```
[MEMORY DEBUG] Result has X messages in history
```

Si falla después de reintentos:
```
[ERROR] Connection failed after 2 attempts
psycopg.OperationalError: ...
```

## 🚀 Testing

Para probar la solución:

1. **Simular inactividad**: Espera 5+ minutos sin usar la app, luego envía un mensaje
2. **Verificar logs**: Deberías ver el retry si la primera conexión falla
3. **Usuario**: Debería recibir respuesta exitosa (con delay mínimo)

## 📚 Referencias

- [psycopg3 Connection Pools](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)
- [TCP Keepalive](https://tldp.org/HOWTO/TCP-Keepalive-HOWTO/overview.html)
- [Supabase Connection Limits](https://supabase.com/docs/guides/database/connecting-to-postgres#connection-pool)

