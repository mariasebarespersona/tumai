"""
Herramientas para gestionar recordatorios de pagos y fechas importantes.
"""
from __future__ import annotations
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import uuid

from .supabase_client import sb
from .rag_tool import qa_document

def _parse_date_from_text(date_text: str) -> Optional[datetime]:
    """Intenta parsear una fecha de texto en múltiples formatos."""
    from dateutil import parser
    try:
        return parser.parse(date_text, dayfirst=True)
    except:
        return None

def create_reminder(
    property_id: str,
    title: str,
    description: str,
    reminder_date: str,
    recipient_email: Optional[str] = None,
    document_reference: Optional[Dict] = None,
    metadata: Optional[Dict] = None,
    recurrence: Optional[str] = None,
    recurrence_count: Optional[int] = None
) -> Dict:
    """
    Crea un recordatorio (o múltiples si es recurrente).
    
    Args:
        property_id: UUID de la propiedad
        title: Título del recordatorio (ej: "Pago a arquitecto")
        description: Descripción detallada
        reminder_date: Fecha del recordatorio en formato ISO o texto (ej: "2024-12-15", "15 de diciembre", "día 5")
        recipient_email: Email del destinatario (opcional, usa el del usuario por defecto)
        document_reference: Referencia al documento relacionado (group, subgroup, name)
        metadata: Metadata adicional
        recurrence: Tipo de recurrencia: "monthly", "yearly", None
        recurrence_count: Número de ocurrencias (default: 12 para monthly, 1 para None)
    
    Returns:
        Dict con id(s) del recordatorio, fecha(s), y confirmación
    """
    from dateutil.relativedelta import relativedelta
    
    # Parse fecha base
    if isinstance(reminder_date, str):
        parsed_date = _parse_date_from_text(reminder_date)
        if not parsed_date:
            return {
                "error": "No se pudo interpretar la fecha. Usa formato DD/MM/YYYY o 'DD de mes de YYYY'",
                "date_provided": reminder_date
            }
    else:
        parsed_date = reminder_date
    
    # Determinar recurrence_count por defecto
    if recurrence == "monthly" and not recurrence_count:
        recurrence_count = 12  # 12 meses por defecto
    elif not recurrence_count:
        recurrence_count = 1  # Solo 1 recordatorio
    
    # Crear lista de fechas según recurrencia
    dates_to_create = []
    for i in range(recurrence_count):
        if recurrence == "monthly":
            target_date = parsed_date + relativedelta(months=i)
        elif recurrence == "yearly":
            target_date = parsed_date + relativedelta(years=i)
        else:
            target_date = parsed_date if i == 0 else None
        
        if target_date:
            dates_to_create.append(target_date)
    
    # Crear recordatorios
    created_reminders = []
    
    try:
        for target_date in dates_to_create:
            reminder_id = str(uuid.uuid4())
            
            payload = {
                "id": reminder_id,
                "property_id": property_id,
                "title": title,
                "description": description,
                "reminder_date": target_date.isoformat(),
                "recipient_email": recipient_email,
                "document_reference": document_reference or {},
                "metadata": {
                    **(metadata or {}),
                    "recurrence": recurrence,
                    "recurrence_index": dates_to_create.index(target_date)
                },
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
            }
            
            result = sb.table("reminders").insert(payload).execute()
            created_reminders.append({
                "id": reminder_id,
                "date": target_date.strftime('%d de %B de %Y'),
                "date_iso": target_date.isoformat()
            })
        
        # Mensaje de confirmación
        if len(created_reminders) == 1:
            msg = f"✅ Recordatorio creado: '{title}' para el {created_reminders[0]['date']}"
        else:
            first_date = created_reminders[0]['date']
            last_date = created_reminders[-1]['date']
            msg = f"✅ {len(created_reminders)} recordatorios creados: '{title}' desde {first_date} hasta {last_date} ({recurrence})"
        
        return {
            "status": "created",
            "count": len(created_reminders),
            "reminders": created_reminders,
            "message": msg
        }
    except Exception as e:
        error_msg = str(e)
        
        # Si la tabla no existe, dar instrucciones claras
        if "does not exist" in error_msg or "Could not find the table" in error_msg or "PGRST" in error_msg:
            return {
                "error": "La tabla 'reminders' no existe en Supabase",
                "setup_required": True,
                "instructions": "Para activar recordatorios: 1) Ve a https://supabase.com/dashboard/project/tqqvgaiueheiqtqmbpjh/sql 2) Copia y pega el SQL de CREAR_TABLA_REMINDERS.sql 3) Click en RUN",
                "message": "⚠️ Sistema de recordatorios no configurado. Ejecuta el SQL en CREAR_TABLA_REMINDERS.sql para activarlo. Toma solo 1 minuto."
            }
        
        return {
            "error": f"Error al crear recordatorio: {error_msg}",
            "created_before_error": len(created_reminders)
        }

def extract_payment_date_from_document(
    property_id: str,
    document_group: str,
    document_subgroup: str,
    document_name: str,
    payment_concept: str
) -> Dict:
    """
    Extrae la fecha de pago de un documento usando QA.
    
    Args:
        property_id: UUID de la propiedad
        document_group: Grupo del documento
        document_subgroup: Subgrupo del documento
        document_name: Nombre del documento
        payment_concept: Concepto del pago (ej: "pago al arquitecto", "honorarios")
    
    Returns:
        Dict con fecha extraída y contexto
    """
    # Usar QA para extraer la fecha
    question = f"¿Cuál es la fecha de pago para {payment_concept}? Responde SOLO con la fecha en formato DD/MM/YYYY si está mencionada, o 'No especificada' si no aparece."
    
    try:
        qa_result = qa_document(
            property_id=property_id,
            group=document_group,
            subgroup=document_subgroup,
            name=document_name,
            question=question,
            model="gpt-4o"
        )
        
        answer = qa_result.get("answer", "")
        
        # Intentar parsear fecha de la respuesta
        parsed_date = _parse_date_from_text(answer)
        
        if parsed_date:
            return {
                "date_found": True,
                "date": parsed_date.isoformat(),
                "date_formatted": parsed_date.strftime("%d/%m/%Y"),
                "source": f"{document_group}/{document_name}",
                "context": answer
            }
        else:
            return {
                "date_found": False,
                "message": "No se encontró una fecha específica en el documento",
                "answer": answer,
                "source": f"{document_group}/{document_name}"
            }
    except Exception as e:
        return {
            "error": f"Error al extraer fecha: {str(e)}",
            "date_found": False
        }

def list_reminders(
    property_id: str,
    status: Optional[str] = None,
    upcoming_days: Optional[int] = None
) -> List[Dict]:
    """
    Lista recordatorios para una propiedad.
    
    Args:
        property_id: UUID de la propiedad
        status: Filtrar por estado (pending, sent, cancelled)
        upcoming_days: Solo mostrar recordatorios de los próximos N días
    
    Returns:
        Lista de recordatorios
    """
    try:
        query = sb.table("reminders").select("*").eq("property_id", property_id)
        
        if status:
            query = query.eq("status", status)
        
        if upcoming_days:
            cutoff_date = (datetime.utcnow() + timedelta(days=upcoming_days)).isoformat()
            query = query.lte("reminder_date", cutoff_date)
        
        query = query.order("reminder_date", desc=False)
        
        result = query.execute()
        return result.data
    except Exception as e:
        return []

def cancel_reminder(reminder_id: str) -> Dict:
    """
    Cancela un recordatorio.
    
    Args:
        reminder_id: UUID del recordatorio
    
    Returns:
        Dict con confirmación
    """
    try:
        result = sb.table("reminders").update({"status": "cancelled"}).eq("id", reminder_id).execute()
        
        if result.data:
            return {
                "cancelled": True,
                "id": reminder_id,
                "message": "Recordatorio cancelado"
            }
        else:
            return {
                "cancelled": False,
                "error": "Recordatorio no encontrado"
            }
    except Exception as e:
        return {
            "cancelled": False,
            "error": str(e)
        }

def send_reminder_email(reminder_id: str) -> Dict:
    """
    Envía el email de un recordatorio y marca como enviado.
    Esta función debería ser llamada por un cron job o scheduler.
    
    Args:
        reminder_id: UUID del recordatorio
    
    Returns:
        Dict con resultado del envío
    """
    try:
        # Obtener recordatorio
        reminder = sb.table("reminders").select("*").eq("id", reminder_id).execute().data
        
        if not reminder:
            return {"error": "Recordatorio no encontrado"}
        
        reminder = reminder[0]
        
        # Enviar email
        from .email_tool import send_email
        
        recipient = reminder.get("recipient_email") or "user@example.com"  # TODO: get from user settings
        subject = f"🔔 Recordatorio: {reminder.get('title')}"
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #3d7435;">🔔 Recordatorio RAMA</h2>
            <h3>{reminder.get('title')}</h3>
            <p>{reminder.get('description')}</p>
            <p><strong>Fecha:</strong> {reminder.get('reminder_date')}</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                Este es un recordatorio automático de RAMA Country Living.
            </p>
        </body>
        </html>
        """
        
        send_result = send_email([recipient], subject, html)
        
        # Marcar como enviado
        sb.table("reminders").update({"status": "sent", "sent_at": datetime.utcnow().isoformat()}).eq("id", reminder_id).execute()
        
        return {
            "sent": True,
            "reminder_id": reminder_id,
            "recipient": recipient
        }
    except Exception as e:
        return {
            "sent": False,
            "error": str(e)
        }

