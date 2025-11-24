# Flujo: Enviar Documento por Email

Cuando el usuario pide "manda X por email" o "envía X a [email]"

## Pasos obligatorios

### 1. Verificar email
- Si NO está en el mensaje: pregunta "¿A qué correo quieres que lo envíe?" y ESPERA respuesta
- Si SÍ está en el mensaje: continúa al paso 2

### 2. Buscar documento (INTERNO - no mostrar al usuario)
```
Llama: list_docs(property_id)
Objetivo: Encontrar documento que coincida con lo solicitado
Ejemplo: "escritura notarial" → buscar doc con "escritura" y "notarial"
Extrae: document_group, document_subgroup, document_name EXACTOS
```

### 3. Obtener URL y enviar
```
Llama: signed_url_for(property_id, document_group, document_subgroup, document_name)
Si falla → ir a paso 4 (error)
Si funciona → INMEDIATAMENTE:
  Llama: send_email(
    to: ["email_del_usuario"],
    subject: "Documento: [nombre]",
    html: '<p>Aquí está el documento solicitado:</p><p><a href="[signed_url]" style="display:inline-block;padding:10px 20px;background-color:#10b981;color:white;text-decoration:none;border-radius:5px;">📄 Descargar [nombre]</a></p>'
  )
```

### 4. Si documento NO existe
```
"El documento '[nombre]' aún no ha sido subido. Por favor, sube el documento primero."
```

## ❌ NUNCA hagas esto
- Mostrar lista de todos los documentos
- Escribir texto entre `signed_url_for` y `send_email`
- Mostrar el HTML del email en el chat

## ✅ Respuesta correcta
"✅ He enviado [documento] a [email]"

