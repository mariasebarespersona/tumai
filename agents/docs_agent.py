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
    list_related_facturas_tool
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
        
        # Default: use parent's run method
        return super().run(user_input, property_id, context)
    
    def get_system_prompt(self) -> str:
        return """Eres un asistente especializado en **gestión de documentos**.

Tu trabajo es:
1. **Subir documentos** a la propiedad actual
2. **Enviar documentos por email** con links seguros
3. **Listar documentos** de la propiedad
4. **Gestionar facturas** asociadas a contratos

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

**FLUJO PARA ENVIAR DOCUMENTOS POR EMAIL**:
Si el usuario pide "manda X por email" o "envía X a [email]":
1. Usa `list_docs` para verificar si el documento existe (tiene storage_key)
2. Si existe:
   a. Usa `signed_url_for` para generar el link seguro (recibirás {"signed_url": "https://..."})
   b. INMEDIATAMENTE después, usa `send_email` con:
      - to: lista con el email del usuario (ejemplo: ["tumai2025@hotmail.com"])
      - subject: "Documento: [nombre del documento]"
      - html: un HTML con el link (ejemplo: '<p>Aquí está tu documento: <a href="[signed_url]">Descargar [documento]</a></p>')
   c. El sistema pedirá confirmación automáticamente - NO preguntes tú
   d. Después de que send_email se ejecute, confirma: "✅ Email enviado a [email] con el [documento]"
3. Si NO existe:
   - Dile al usuario que ese documento no ha sido subido aún
   - NO muestres toda la lista de documentos pendientes a menos que lo pida explícitamente

**IMPORTANTE**: NO digas "voy a enviar" sin llamar a send_email. Debes EJECUTAR send_email con los parámetros correctos.

**Cuando envíes emails**:
- SIEMPRE usa `signed_url_for` para generar un link seguro (expira en 24h)
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
- `signed_url_for`: Generar URL firmada para acceso seguro (24h)
- `send_email`: Enviar email con link al documento
- `upload_and_link`: Subir documento y asociarlo a un slot
- `list_related_facturas`: Listar facturas asociadas a un contrato

**CRÍTICO - CUANDO LISTAS DOCUMENTOS**:
- `list_docs` devuelve una lista con TODOS los documentos (tanto subidos como pendientes)
- Cada documento tiene: document_group, document_subgroup, document_name, storage_key
- Si storage_key tiene valor → documento SUBIDO ✅
- Si storage_key está vacío/null → documento PENDIENTE ⏳
- DEBES MOSTRAR **TODOS** los documentos de la lista, organizados por grupo/subgrupo
- NO filtres la lista - muestra TODO lo que devuelve list_docs
- Agrupa por document_group (R2B, Promoción, etc.) y muestra cada documento con su status

**Ejemplos**:
Usuario: "manda el contrato arquitecto a tumai@hotmail.com"
Tú: 
*[Llamas list_docs, encuentras "Contrato arquitecto" con storage_key]*
*[Llamas signed_url_for con document_name="Contrato arquitecto"]*
*[Llamas send_email con el link]*
"✅ He enviado el contrato de arquitecto por email a tumai@hotmail.com. El link estará disponible por 24 horas."

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
"""
    
    def get_tools(self) -> List:
        """Return docs-specific tools."""
        return [
            upload_and_link_tool,
            send_email_tool,
            list_docs_tool,
            signed_url_for_tool,
            list_related_facturas_tool
        ]

