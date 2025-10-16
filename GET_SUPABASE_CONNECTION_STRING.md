# 🔗 Cómo Obtener el Connection String Correcto de Supabase

## ⚠️ Problema Actual

Los connection strings que probamos no funcionan porque:
- ❌ `db.tqqvgaiueheiqtqmbpjh.supabase.co:5432` - DNS no resuelve
- ❌ `postgres.tqqvgaiueheiqtqmbpjh@aws-0-us-west-1.pooler.supabase.com:5432` - "Tenant or user not found"

## ✅ Solución: Obtener el String Correcto

### Paso 1: Ve a tu Dashboard de Supabase

1. Abre: https://supabase.com/dashboard/project/tqqvgaiueheiqtqmbpjh
2. Click en **Settings** (⚙️) en la barra lateral
3. Click en **Database**

### Paso 2: Busca "Connection string"

En la sección **Connection string**, verás varias opciones:

#### Opción A: **Transaction Mode** (Recomendado para LangGraph)
```
postgresql://postgres:[YOUR-PASSWORD]@[HOST]:[PORT]/postgres
```

#### Opción B: **Session Mode**
```
postgresql://postgres:[YOUR-PASSWORD]@[HOST]:[PORT]/postgres
```

### Paso 3: Copia el Connection String Completo

**IMPORTANTE**: Usa el que dice **"Transaction mode"** o **"Session mode"**.

Ejemplo de cómo se ve:
```
postgresql://postgres.tqqvgaiueheiqtqmbpjh:[PASSWORD]@aws-0-us-west-1.pooler.supabase.com:6543/postgres
```

### Paso 4: Actualiza tu .env

Abre el archivo `.env` y **reemplaza completamente** la línea DATABASE_URL:

```bash
# REEMPLAZA ESTA LÍNEA COMPLETA
DATABASE_URL=[PEGA-AQUI-EL-CONNECTION-STRING-DE-SUPABASE]
```

**Ejemplo:**
```bash
DATABASE_URL=postgresql://postgres.tqqvgaiueheiqtqmbpjh:tu_contraseña_aqui@aws-0-us-west-1.pooler.supabase.com:6543/postgres
```

### Paso 5: Reinicia el Backend

```bash
pkill -f "python.*app.py"
.venv/bin/python3 app.py
```

### Paso 6: Verifica que Funciona

Deberías ver:
```
✅ PostgreSQL connected and tables created!
✅ PostgreSQL checkpointer ready for persistent memory
```

---

## 🔍 Alternativa: Obtener por CLI

Si prefieres, puedes obtenerlo con el CLI de Supabase:

```bash
# Instalar Supabase CLI
brew install supabase/tap/supabase

# Login
supabase login

# Ver connection string
supabase db show connection-string --project-id tqqvgaiueheiqtqmbpjh
```

---

## ⚠️ Notas Importantes

1. **NO uses el "Direct connection"** - Usa "Pooler" (Transaction o Session mode)
2. **El puerto** puede ser `5432`, `6543` o `5433` dependiendo del modo
3. **La contraseña** es la del usuario `postgres`, no tu cuenta de Supabase
4. **Si no tienes la contraseña**, puedes resetearla en Settings → Database → "Database password"

---

## 🆘 Si Sigue Sin Funcionar

Si después de esto sigue sin funcionar, copia y pégame el connection string que obtuviste (OCULTA la contraseña, reemplázala con `****`) y te ayudo a diagnosticar.

Ejemplo:
```
DATABASE_URL=postgresql://postgres.tqqvgaiueheiqtqmbpjh:****@aws-0-us-west-1.pooler.supabase.com:6543/postgres
```

