"""
Evaluation Registry - Maps user intents to expected tools.
Used for automated tool selection evaluation.
"""
from typing import List, Dict, Optional
import re

# Map of user intent patterns to expected tools
EXPECTED_TOOLS_BY_INTENT = {
    # Property Management
    "create_property": ["add_property"],
    "list_properties": ["list_properties"],
    "search_properties": ["search_properties"],
    "get_property": ["get_property"],
    "delete_property": ["delete_property"],
    "set_current_property": ["set_current_property"],
    
    # Documents
    "upload_document": ["propose_doc_slot", "upload_and_link"],
    "list_documents": ["list_docs"],
    "get_document_url": ["signed_url_for"],
    "send_document_email": ["signed_url_for", "send_email"],
    
    # Numbers (Legacy)
    "set_number": ["set_number"],
    "get_numbers": ["get_numbers"],
    "calc_numbers": ["calc_numbers"],
    "export_numbers": ["numbers_excel_export"],
    
    # Numbers Table (R2B)
    "set_numbers_table_cell": ["set_numbers_table_cell"],
    "clear_numbers_table_cell": ["clear_numbers_table_cell"],
    "export_numbers_table": ["export_numbers_table"],
    "send_numbers_table_email": ["send_numbers_table_email"],
    "delete_numbers_template": ["delete_numbers_template"],
    "select_numbers_template": ["set_numbers_template"],
    
    # Email
    "send_email": ["send_email"],
    
    # Reminders
    "create_reminder": ["create_reminder"],
    "list_reminders": ["list_reminders"],
    "cancel_reminder": ["cancel_reminder"],
    
    # RAG / QA
    "summarize_document": ["summarize_document"],
    "qa_document": ["qa_document"],
    "rag_qa": ["rag_qa_with_citations"],
    "index_document": ["rag_index_document"],
    
    # Summary
    "compute_summary": ["compute_summary"],
    "build_summary_ppt": ["build_summary_ppt"],
}

# Intent classification patterns (simple regex-based for now)
INTENT_PATTERNS = {
    # Property
    r"(añade|agrega|crea|nueva?) propiedad": "create_property",
    r"(lista|listar|ver|muestra|mostrar) (todas? las )?propiedades": "list_properties",
    r"busca(r)? propiedad": "search_properties",
    r"(borra|elimina|delete) (la )?propiedad": "delete_property",
    r"(trabaja|trabajar|usar|selecciona) (con )?(la )?propiedad": "set_current_property",
    
    # Documents
    r"(sube|subir|añade|agregar|upload) (un? )?(documento|factura|contrato|escritura)": "upload_document",
    r"(lista|listar|ver|muestra) (los? )?documentos": "list_documents",
    r"(manda|envía|enviar|send).+(email|correo|mail)": "send_document_email",
    
    # Numbers Table
    r"(pon|poner|set|establece|añade|agrega) (el |la |en |valor ).+(en |a |celda |cell )?[A-Z]\d+": "set_numbers_table_cell",
    r"(borra|elimina|delete|clear) (el valor de )?la celda [A-Z]\d+": "clear_numbers_table_cell",
    r"(exporta|exportar|export|descarga|descargar).+(números|tabla|plantilla|numbers|template)": "export_numbers_table",
    r"(manda|envía|enviar|send).+(plantilla|tabla|números|template).+(email|correo)": "send_numbers_table_email",
    r"(elimina|borra|delete).+(tabla de números|plantilla|template)": "delete_numbers_template",
    r"(usa|usar|selecciona|seleccionar|cambiar a).+(plantilla|template).+(R2B|PM|Venta|Promocion)": "select_numbers_template",
    
    # Email (generic)
    r"(envia|envía|enviar|manda|mandar|send).+(email|correo|mail)": "send_email",
    
    # Reminders
    r"(crea|crear|añade|agregar|add).+(recordatorio|reminder)": "create_reminder",
    r"(lista|listar|ver|muestra).+(recordatorios|reminders)": "list_reminders",
    r"(cancela|cancelar|cancel|borra|elimina).+(recordatorio|reminder)": "cancel_reminder",
    
    # RAG
    r"(resume|resumen|resumir|summarize)": "summarize_document",
    r"(pregunta|question|qué|que|cuándo|cuando|cómo|como|dónde|donde)": "qa_document",
}


def classify_intent(user_message: str) -> Optional[str]:
    """
    Classify user intent from message.
    
    Args:
        user_message: User's message
        
    Returns:
        Intent string or None
    """
    message_lower = user_message.lower()
    
    for pattern, intent in INTENT_PATTERNS.items():
        if re.search(pattern, message_lower):
            return intent
    
    return None


def get_expected_tools(user_message: str) -> List[str]:
    """
    Get expected tools for a user message.
    
    Args:
        user_message: User's message
        
    Returns:
        List of expected tool names
    """
    intent = classify_intent(user_message)
    
    if intent and intent in EXPECTED_TOOLS_BY_INTENT:
        return EXPECTED_TOOLS_BY_INTENT[intent]
    
    # Default: no specific expectation
    return []


def get_intent_description(intent: str) -> str:
    """Get human-readable description of intent."""
    descriptions = {
        "create_property": "Crear nueva propiedad",
        "list_properties": "Listar propiedades",
        "search_properties": "Buscar propiedad",
        "delete_property": "Eliminar propiedad",
        "set_current_property": "Seleccionar propiedad activa",
        "upload_document": "Subir documento",
        "list_documents": "Listar documentos",
        "send_document_email": "Enviar documento por email",
        "set_numbers_table_cell": "Establecer valor en celda",
        "clear_numbers_table_cell": "Borrar valor de celda",
        "export_numbers_table": "Exportar tabla de números",
        "send_numbers_table_email": "Enviar plantilla por email",
        "delete_numbers_template": "Eliminar plantilla de números",
        "select_numbers_template": "Seleccionar plantilla",
        "send_email": "Enviar email",
        "create_reminder": "Crear recordatorio",
        "list_reminders": "Listar recordatorios",
        "cancel_reminder": "Cancelar recordatorio",
        "summarize_document": "Resumir documento",
        "qa_document": "Preguntar sobre documento",
    }
    return descriptions.get(intent, intent)

