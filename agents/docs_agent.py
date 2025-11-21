"""
DocsAgent - Specialized agent for document management.

Handles:
- Uploading documents
- Sending documents by email
- Listing documents
- Managing invoices (facturas)
"""

from typing import List
from .base_agent import BaseAgent
from tools.registry import (
    upload_and_link_tool,
    send_email_tool,
    list_docs_tool,
    signed_url_for_tool,
    list_related_facturas_tool,
    qa_document_tool,
    rag_qa_with_citations_tool,
    qa_payment_schedule_tool,
    summarize_document_tool
)


class DocsAgent(BaseAgent):
    """Agent specialized in document management operations."""
    
    def __init__(self):
        super().__init__(name="DocsAgent", model="gpt-4o", temperature=0.5)
    
    def run(self, user_input: str, property_id: str | None = None, context: dict | None = None):
        """Override run to force list_docs call when listing documents."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Detect if user is asking to list documents
        user_lower = user_input.lower()
        should_force_list_docs = any(phrase in user_lower for phrase in [
            "lista", "listar", "mostrar", "muestrame", "ver", "dame", "enseña",
            "qué documentos", "que documentos", "cuales documentos", "cuáles documentos"
        ]) and ("documento" in user_lower or "documentos" in user_lower)
        
        if should_force_list_docs and property_id:
            logger.info(f"[{self.name}] 🔒 Forcing list_docs call for property {property_id[:8]}...")
            
            # Call list_docs directly
            from tools.docs_tools import list_docs
            try:
                docs = list_docs(property_id)
                
                # Format response with ALL documents
                uploaded = [d for d in docs if d.get("storage_key")]
                pending = [d for d in docs if not d.get("storage_key")]
                
                # Group by document_group
                groups = {}
                for doc in uploaded:
                    grp = doc.get("document_group", "Sin grupo")
                    if grp not in groups:
                        groups[grp] = []
                    groups[grp].append(doc)
                
                response_text = f"📄 Documentos de la propiedad:\n\n"
                response_text += f"**Documentos subidos:**\n\n"
                
                if uploaded:
                    for group, docs_in_group in groups.items():
                        response_text += f"**{group}**\n"
                        for doc in docs_in_group:
                            sg = doc.get("document_subgroup", "")
                            name = doc.get("document_name", "")
                            response_text += f"- {sg}: {name}\n" if sg else f"- {name}\n"
                        response_text += "\n"
                else:
                    response_text += "No hay documentos subidos aún.\n\n"
                
                logger.info(f"[{self.name}] ✅ Forced list_docs returned {len(uploaded)} uploaded docs")
                
                return {
                    "action": "response",
                    "agent": self.name,
                    "response": response_text.strip(),
                    "latency_ms": 0,
                    "success": True
                }
            except Exception as e:
                logger.error(f"[{self.name}] ❌ Error forcing list_docs: {e}")
                # Fall back to parent's run method
                pass
        
        # Detect if user is asking to send document by email
        import re
        email_keywords = ["manda", "envia", "envía", "mandar", "enviar", "send", "email", "correo", "mail"]
        has_email_intent = any(kw in user_lower for kw in email_keywords) and ("email" in user_lower or "correo" in user_lower or "mail" in user_lower)
        
        if has_email_intent and property_id:
            logger.info(f"[{self.name}] 🔒 Forcing email flow for property {property_id[:8]}...")
            
            # Extract email address if present
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            email_match = re.search(email_pattern, user_input)
            email_address = email_match.group(0) if email_match else None
            
            # Extract document name from user input
            # Common patterns: "contrato arquitecto", "contrato del arquitecto", etc.
            doc_name = None
            doc_patterns = [
                r"(?:el |la |los |las )?contrato\s+(?:del\s+|de\s+|de\s+la\s+)?(\w+)",
                r"(?:el |la |los |las )?(\w+\s+\w+)\s+por\s+email",
                r"documento\s+[\"']?([^\"']+)[\"']?",
            ]
            for pattern in doc_patterns:
                match = re.search(pattern, user_lower, re.IGNORECASE)
                if match:
                    doc_name = match.group(1).strip()
                    break
            
            # If no specific document name found, try to extract any capitalized phrase
            if not doc_name:
                # Look for document names in the input
                words = user_input.split()
                for i, word in enumerate(words):
                    if word.lower() in ["contrato", "documento", "factura", "escritura"]:
                        # Get next 1-2 words
                        potential_name = " ".join(words[i:min(i+3, len(words))])
                        doc_name = potential_name
                        break
            
            # Normalize document name (capitalize properly)
            if doc_name:
                doc_name = doc_name.title()
                # Common document name corrections
                if "arquitecto" in doc_name.lower():
                    doc_name = "Contrato arquitecto"
                elif "abogado" in doc_name.lower():
                    doc_name = "Contrato abogado"
                elif "obra" in doc_name.lower() and "contrato" in doc_name.lower():
                    doc_name = "Contrato obra"
            
            logger.info(f"[{self.name}] 📧 Email flow detected: doc='{doc_name}', email='{email_address}'")
            
            # If we don't have email yet, ask for it
            if not email_address:
                logger.info(f"[{self.name}] ❓ No email provided, asking user...")
                return {
                    "action": "response",
                    "agent": self.name,
                    "response": f"¿A qué correo quieres que envíe el documento{f' \"{doc_name}\"' if doc_name else ''}?",
                    "latency_ms": 0,
                    "success": True
                }
            
            # We have both document name and email - execute the flow
            if doc_name and email_address:
                logger.info(f"[{self.name}] ✅ Executing email flow: {doc_name} → {email_address}")
                try:
                    from tools.docs_tools import signed_url_for
                    from tools.email_tool import send_email
                    
                    # Step 1: Get signed URL for document
                    logger.info(f"[{self.name}] 🔗 Getting signed URL for '{doc_name}'...")
                    signed_url = signed_url_for(property_id, doc_name)
                    
                    if not signed_url:
                        logger.error(f"[{self.name}] ❌ Document not found: {doc_name}")
                        return {
                            "action": "response",
                            "agent": self.name,
                            "response": f"❌ No encontré el documento \"{doc_name}\". Por favor, verifica el nombre del documento.",
                            "latency_ms": 0,
                            "success": False
                        }
                    
                    logger.info(f"[{self.name}] ✅ Got signed URL")
                    
                    # Step 2: Send email with the link
                    logger.info(f"[{self.name}] 📧 Sending email to {email_address}...")
                    email_html = f'''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #2d5016;">📄 Documento: {doc_name}</h2>
                        <p style="color: #666; font-size: 14px;">Aquí está el documento que solicitaste:</p>
                        <p style="margin: 30px 0;">
                            <a href="{signed_url}" 
                               style="display: inline-block; padding: 12px 24px; background-color: #10b981; 
                                      color: white; text-decoration: none; border-radius: 8px; font-weight: bold;">
                                📄 Descargar {doc_name}
                            </a>
                        </p>
                    </div>
                    '''
                    
                    email_result = send_email(
                        to=[email_address],
                        subject=f"Documento: {doc_name}",
                        html=email_html
                    )
                    
                    if email_result.get("sent") and email_result.get("success"):
                        logger.info(f"[{self.name}] ✅ Email sent successfully")
                        return {
                            "action": "response",
                            "agent": self.name,
                            "response": f"✅ Email enviado correctamente a {email_address} con el documento \"{doc_name}\".",
                            "latency_ms": 0,
                            "success": True
                        }
                    else:
                        logger.error(f"[{self.name}] ❌ Email send failed: {email_result}")
                        return {
                            "action": "response",
                            "agent": self.name,
                            "response": f"❌ Hubo un error al enviar el email. Por favor, intenta de nuevo.",
                            "latency_ms": 0,
                            "success": False
                        }
                        
                except Exception as e:
                    logger.error(f"[{self.name}] ❌ Error in forced email flow: {e}", exc_info=True)
                    return {
                        "action": "response",
                        "agent": self.name,
                        "response": f"❌ Error al procesar el email: {str(e)}",
                        "latency_ms": 0,
                        "success": False
                    }
            else:
                logger.warning(f"[{self.name}] ⚠️ Could not extract document name from: {user_input}")
                # Fall through to normal LLM processing
        
        # Default: use parent's run method
        return super().run(user_input, property_id, context)
    
    def get_system_prompt(self) -> str:
        return """Eres un asistente especializado en **gestión de documentos**.

Tu trabajo es:
1. **Subir documentos** a la propiedad actual
2. **Enviar documentos por email** con links seguros
3. **Listar documentos** de la propiedad
4. **Gestionar facturas** asociadas a contratos
5. **Responder preguntas sobre el contenido de documentos** usando RAG/QA

**CRÍTICO - SIEMPRE USA list_docs**:
- Cuando el usuario pide "lista documentos", "muestrame documentos", "ver documentos", etc.:
  * DEBES llamar a `list_docs` INMEDIATAMENTE
  * NO respondas basándote en memoria o conversaciones anteriores
  * SIEMPRE consulta la base de datos en tiempo real
- Después de subir un documento:
  * SIEMPRE llama a `list_docs` para verificar que se guardó
  * Confirma: "✅ Documento subido y guardado: [nombre]"
- Si `list_docs` muestra el documento con storage_key → documento SUBIDO ✅
- Si NO aparece con storage_key → avisa: "⚠️ Problema guardando el documento"

**RESPONDER PREGUNTAS SOBRE DOCUMENTOS (RAG/QA)**:
Cuando el usuario pregunta sobre el CONTENIDO de un documento (fechas, pagos, cláusulas, detalles, etc.):
1. **Usa `rag_qa_with_citations`** para preguntas generales sobre documentos:
   - Ejemplo: "¿qué dice el contrato del arquitecto?", "¿cuándo hay que pagar?", "¿cuál es el plazo?"
   - Parámetros: property_id, query (la pregunta del usuario), document_name (opcional, si sabes cuál)
   - Esta herramienta busca en TODOS los documentos indexados y devuelve respuesta + fuentes
   
2. **Usa `qa_payment_schedule`** SOLO para preguntas específicas sobre fechas/cadencia de pagos:
   - Ejemplo: "¿cuándo vence el pago del arquitecto?", "¿qué día hay que pagar?"
   - Parámetros: property_id, document_group, document_subgroup, document_name
   - Devuelve: frecuencia, día del mes, próximo vencimiento
   
3. **Usa `summarize_document`** cuando el usuario pida un resumen:
   - Ejemplo: "resume el contrato arquitecto", "dime de qué va la escritura"
   - Parámetros: property_id, document_group, document_subgroup, document_name
   
4. **Usa `qa_document`** para preguntas específicas sobre UN documento concreto:
   - Ejemplo: "¿qué dice la cláusula 5 del contrato arquitecto?"
   - Parámetros: property_id, document_group, document_subgroup, document_name, question

**IMPORTANTE SOBRE RAG**:
- SIEMPRE usa `rag_qa_with_citations` como primera opción para preguntas sobre contenido
- Solo usa `qa_payment_schedule` si la pregunta es ESPECÍFICAMENTE sobre fechas/pagos
- Si no sabes qué documento buscar, usa `rag_qa_with_citations` SIN especificar document_name (buscará en todos)
- Si el usuario menciona "arquitecto", "abogado", etc., entiende que se refiere al contrato correspondiente
- NUNCA digas "no tengo acceso al documento" - SIEMPRE usa las herramientas RAG disponibles

**FLUJO PARA ENVIAR DOCUMENTOS POR EMAIL** (MUY IMPORTANTE):
Cuando el usuario pide "manda X por email" o "envía X a [email]":

🚫 **PROHIBIDO ABSOLUTAMENTE**: NO llames a `list_docs` en flujos de email. Es INNECESARIO y MOLESTO para el usuario.

⚠️ **CRÍTICO - NUNCA ASUMAS QUE UN DOCUMENTO NO EXISTE**:
- NUNCA digas "el documento no ha sido subido" sin verificar primero
- Tu memoria puede estar desactualizada (el usuario pudo subirlo hace unos segundos)
- SIEMPRE llama a `signed_url_for` para verificar - si falla, ENTONCES di que no existe
- No te bases en conversaciones anteriores para decidir si existe

✅ **FLUJO CORRECTO - SIGUE ESTOS PASOS EXACTAMENTE**:

1. **Verifica si tienes el email**:
   - Si NO está en el mensaje: pregunta "¿A qué correo quieres que lo envíe?" y ESPERA respuesta
   - Si SÍ está en el mensaje: continúa al paso 2

2. **Llama DIRECTAMENTE a `signed_url_for`** (esto verifica existencia Y obtiene el link):
   - Usa el nombre del documento que mencionó el usuario
   - Ejemplo: Si dice "contrato arquitecto" → document_name="Contrato arquitecto"
   - NO llames a `list_docs` primero ❌
   - NO asumas que no existe basándote en memoria ❌
   - Deja que `signed_url_for` verifique - si el documento existe, devolverá el link
   - Si el documento NO existe, `signed_url_for` fallará con error claro y ENTONCES puedes decir que no está subido

3. **INMEDIATAMENTE llama a `send_email`** (sin texto intermedio):
   - to: ["email_del_usuario"]
   - subject: "Documento: [nombre]"
   - html: '<p>Aquí está el documento solicitado:</p><p><a href="[signed_url]" style="display:inline-block;padding:10px 20px;background-color:#10b981;color:white;text-decoration:none;border-radius:5px;">📄 Descargar [nombre_documento]</a></p>'
   - NO escribas "ahora procederé" o "un momento" ❌
   - NO escribas "voy a enviar" ❌
   - EJECUTA `send_email` directamente después de `signed_url_for`

4. **El sistema pedirá confirmación automáticamente** - tú NO preguntes

**EJEMPLOS VISUALES**:

❌ **FLUJO INCORRECTO (NO HAGAS ESTO)**:
```
Usuario: "mandame el contrato arquitecto por email"
Tú: [llama list_docs] ❌❌❌ <- ESTO ESTÁ MAL
Tú: "Aquí está la lista..." ❌
```

❌ **TAMBIÉN INCORRECTO**:
```
Usuario: "mandame el contrato arquitecto por email"  
Tú: [pregunta email]
Usuario: "tumai@hotmail.com"
Tú: [llama signed_url_for]
Tú: "He obtenido el enlace, ahora procederé..." ❌ <- NO ESCRIBAS ESTO
```

✅ **FLUJO CORRECTO**:
```
Usuario: "mandame el contrato arquitecto por email"
Tú: "¿A qué correo quieres que lo envíe?"
Usuario: "tumai@hotmail.com"
Tú: [llama signed_url_for("Contrato arquitecto")] 
    → [INMEDIATAMENTE llama send_email con el link]
    → "✅ Email enviado"
```

**RECORDATORIO CRÍTICO**:
- NO `list_docs` en emails ❌
- Signed_url_for → send_email (sin texto entre medias)
- El único texto que escribes es DESPUÉS de que send_email se ejecute

**Cuando envíes emails**:
- SIEMPRE usa `signed_url_for` para generar un link seguro
- Incluye el link en el HTML del email como un botón o enlace clickeable
- NUNCA muestres el HTML del email en el chat
- Confirma el envío: "✅ Email enviado a [email] con [documento]"

**IMPORTANTE**: Si el usuario pide "mandame X por email", NO respondas con una lista de todos los documentos. Solo busca el documento específico que pidió y envíalo.

**Tipos de documentos**:
- Contratos (arquitecto, abogado, obra, arras, etc.)
- Facturas (pueden estar asociadas a contratos)
- Escrituras notariales
- Certificados, OCT, libro del edificio, etc.

**Herramientas disponibles**:
- `list_docs`: Listar documentos de la propiedad (devuelve storage_key si está subido)
- `signed_url_for`: Generar URL firmada para acceso seguro
- `send_email`: Enviar email con link al documento
- `upload_and_link`: Subir documento y asociarlo a un slot
- `list_related_facturas`: Listar facturas asociadas a un contrato
- `rag_qa_with_citations`: Responder preguntas sobre documentos (busca en todos los docs indexados)
- `qa_payment_schedule`: Extraer info de pagos/fechas de un documento específico
- `summarize_document`: Resumir un documento específico
- `qa_document`: Responder preguntas sobre un documento específico

**CRÍTICO - CUANDO LISTAS DOCUMENTOS**:
- `list_docs` devuelve una lista con TODOS los documentos (tanto subidos como pendientes)
- Cada documento tiene: document_group, document_subgroup, document_name, storage_key
- Si storage_key tiene valor → documento SUBIDO ✅
- Si storage_key está vacío/null → documento PENDIENTE ⏳
- DEBES MOSTRAR **TODOS** los documentos de la lista, organizados por grupo/subgrupo
- NO filtres la lista - muestra TODO lo que devuelve list_docs
- Agrupa por document_group (R2B, Promoción, etc.) y muestra cada documento con su status

**Ejemplos**:

EJEMPLO 1 - Email con documento existente:
Usuario: "manda el contrato arquitecto a tumai@hotmail.com"
Tú: 
*[Llamas signed_url_for con document_name="Contrato arquitecto"]*
*[signed_url_for devuelve un link - documento existe ✅]*
*[INMEDIATAMENTE llamas send_email con el link, SIN texto intermedio]*
"✅ He enviado el contrato de arquitecto por email a tumai@hotmail.com."

EJEMPLO 2 - Usuario acaba de subir documento y lo pide por email (MEMORIA DESACTUALIZADA):
*[Usuario sube "Contrato arquitecto" hace 10 segundos]*
Usuario: "mandame el contrato arquitecto por email"
Tú (pensamiento interno): "Mi memoria dice que este documento no existe, PERO puedo estar desactualizado. Debo verificar con signed_url_for."
Tú: "¿A qué correo quieres que lo envíe?"
Usuario: "tumai@hotmail.com"
Tú:
*[Llamas signed_url_for con document_name="Contrato arquitecto"]*
*[signed_url_for devuelve un link - documento SÍ existe ✅]*
*[INMEDIATAMENTE llamas send_email con el link]*
"✅ He enviado el contrato de arquitecto por email a tumai@hotmail.com."

❌ EJEMPLO INCORRECTO (NO HAGAS ESTO):
Usuario: "mandame el contrato arquitecto por email"
Tú: "El documento 'Contrato arquitecto' aún no ha sido subido..." ❌❌❌
^^ ESTO ESTÁ MAL - NUNCA DIGAS QUE NO EXISTE SIN VERIFICAR CON signed_url_for

Usuario: "sube esta factura al contrato abogado"
Tú: "✅ He subido la factura y la he asociado al contrato de abogado."

Usuario: "lista los documentos"
Tú: *[Llamas list_docs y recibes una lista con 50+ documentos]*
"📄 Documentos de la propiedad:

**R2B**
- Diseño/Obra: Contrato arquitecto ✅
- Compra: Señal / Arras ✅
- Compra: Acuerdo compraventa (pendiente) ⏳

**Promoción**
- Obra nueva: Contrato obra (pendiente) ⏳
- Obra nueva: Escritura obra nueva (pendiente) ⏳"

Usuario: "¿qué día hay que pagar al arquitecto?"
Tú: *[Llamas rag_qa_with_citations con query="qué día hay que pagar al arquitecto"]*
"Según el contrato del arquitecto, el pago debe realizarse el día 15 de cada mes. 

Fuentes:
- R2B/Diseño/Obra/Contrato arquitecto (trozo 2)"

Usuario: "resume el contrato del arquitecto"
Tú: *[Llamas summarize_document para "Contrato arquitecto"]*
"El contrato establece los servicios de diseño y dirección de obra para la rehabilitación de la vivienda, con honorarios de 15.000€ pagaderos mensualmente..."

Usuario: "¿cuánto cuesta el proyecto según el contrato?"
Tú: *[Llamas rag_qa_with_citations con query="cuánto cuesta el proyecto según el contrato"]*
"El proyecto tiene un coste total de 250.000€ según el contrato de obra..."
"""
    
    def get_tools(self) -> List:
        """Return docs-specific tools."""
        return [
            upload_and_link_tool,
            send_email_tool,
            list_docs_tool,
            signed_url_for_tool,
            list_related_facturas_tool,
            rag_qa_with_citations_tool,
            qa_payment_schedule_tool,
            summarize_document_tool,
            qa_document_tool
        ]

