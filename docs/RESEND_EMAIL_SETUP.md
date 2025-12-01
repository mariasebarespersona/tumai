# 📧 Resend Email Setup Guide

**Migrado de SMTP a Resend API** para compatibilidad con Railway y otros clouds que bloquean puertos SMTP.

---

## 🚀 Por qué Resend en lugar de SMTP

| Feature | SMTP | Resend API |
|---------|------|------------|
| **Funciona en Railway** | ❌ Bloqueado | ✅ Siempre funciona |
| **Velocidad** | 1-3 segundos | < 500ms |
| **Deliverability** | ⚠️ Variable | ✅ Mejor reputación |
| **Monitoreo** | ❌ No | ✅ Dashboard completo |
| **Setup** | Complicado | 2 minutos |

---

## 📝 Setup en 3 Pasos (2 minutos)

### 1️⃣ Crear cuenta en Resend

1. Ve a: **https://resend.com/signup**
2. Regístrate con tu email (gratis, 100 emails/mes)
3. Verifica tu email

### 2️⃣ Obtener API Key

1. Una vez logueado, ve a: **https://resend.com/api-keys**
2. Click en **"Create API Key"**
3. Dale un nombre: `RAMA AI Production`
4. Permisos: **"Sending access"** (default está bien)
5. Click **"Create"**
6. **COPIA LA API KEY** (empieza con `re_...`)
   - ⚠️ **Solo se muestra una vez**, guárdala en un lugar seguro

### 3️⃣ Configurar Variables de Entorno

#### **Local (.env)**

```bash
# Resend API
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxxxxx

# Email "From" (puedes usar el dominio por defecto de Resend para testing)
EMAIL_FROM=RAMA AI <noreply@resend.dev>
```

#### **Railway (Producción)**

1. Ve a tu proyecto en Railway
2. Click en tu servicio → **Variables**
3. Añade:
   - **Variable name:** `RESEND_API_KEY`
   - **Value:** `re_xxxxxxxxxxxxxxxxxxxxxxxxxxx` (tu API key)
4. Añade (opcional, ya tiene default):
   - **Variable name:** `EMAIL_FROM`
   - **Value:** `RAMA AI <noreply@resend.dev>`
5. Click **"Add"** y Railway redesplegará automáticamente

---

## ✅ Verificar que Funciona

### Opción 1: Local

```bash
# Asegúrate de tener la API key en .env
cd /Users/mariasebares/Documents/RAMA_AI/rama-agentic-ai
pip install resend  # Instala la librería
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('✅ RESEND_API_KEY loaded' if os.getenv('RESEND_API_KEY') else '❌ Missing RESEND_API_KEY')"
```

### Opción 2: Desde la App

1. Inicia tu app local o en Railway
2. Sube un documento
3. Pide al agente: "Mándame este documento por email a tu_email@gmail.com"
4. Deberías recibir el email en **< 10 segundos**

---

## 🎯 Dominio Personalizado (Opcional)

Por defecto, Resend usa `@resend.dev` para testing. Para producción con tu dominio:

### 1. Añadir tu dominio en Resend

1. Ve a: **https://resend.com/domains**
2. Click **"Add Domain"**
3. Ingresa tu dominio (ej: `tumai.app`)
4. Sigue las instrucciones para añadir registros DNS:
   - `MX`
   - `TXT` (SPF)
   - `TXT` (DKIM)

### 2. Actualizar EMAIL_FROM

```bash
# En .env y Railway
EMAIL_FROM=RAMA AI <noreply@tumai.app>
```

---

## 🆘 Troubleshooting

### Error: `Resend library not installed`

```bash
pip install resend
```

### Error: `Resend API key missing`

Verifica que `RESEND_API_KEY` esté en `.env` (local) o en Railway Variables (producción).

### Error: `Invalid API key`

- Asegúrate de que la API key empiece con `re_`
- Regenera una nueva en: https://resend.com/api-keys

### Emails no llegan (van a spam)

**Para testing con `@resend.dev`:**
- Revisa la carpeta de spam
- Algunos proveedores (Outlook, Hotmail) son más estrictos

**Solución:** Añade tu dominio personalizado (ver arriba)

### Ver logs de emails enviados

1. Ve a: **https://resend.com/emails**
2. Verás todos los emails enviados, su estado, y si fueron abiertos

---

## 📊 Monitoreo en Producción

Resend dashboard te muestra:
- ✅ **Emails enviados** (delivered)
- ❌ **Emails fallidos** (bounced)
- 📧 **Emails abiertos** (opened)
- 🔗 **Links clickeados** (clicked)

Dashboard: **https://resend.com/emails**

---

## 💰 Pricing

- **Gratis:** 3,000 emails/mes, 100 emails/día
- **Pro ($20/mes):** 50,000 emails/mes
- **Scale ($85/mes):** 100,000 emails/mes

Para tu app, el plan gratis es suficiente al inicio.

---

## 🔄 Rollback a SMTP (Si necesitas)

Si por alguna razón quieres volver a SMTP, revierte el commit:

```bash
git revert HEAD
```

---

## ✨ Checklist Final

- [ ] Cuenta creada en Resend
- [ ] API key obtenida (`re_...`)
- [ ] `RESEND_API_KEY` añadida en `.env` (local)
- [ ] `RESEND_API_KEY` añadida en Railway Variables
- [ ] `pip install resend` ejecutado (local)
- [ ] Railway redesplegado (automático al añadir variable)
- [ ] Email de prueba enviado y recibido

---

**¡Listo! 🎉** Ahora tus emails funcionarán en Railway sin problemas de puertos bloqueados.

