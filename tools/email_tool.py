from __future__ import annotations
import os
import base64
from typing import List
from uuid import uuid4
import logfire  # Logfire for event tracking

# Resend API Configuration
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", "RAMA AI <noreply@tumai.app>")

def send_email(to: List[str], subject: str, html: str, attachments: List[tuple[str, bytes]] = None):
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[send_email] ===== STARTING EMAIL SEND =====")
    logger.info(f"[send_email] to={to}, subject={subject[:50] if subject else '(empty)'}")
    logger.info(f"[send_email] html length={len(html) if html else 0}, attachments={len(attachments) if attachments else 0}")
    
    # Validate Resend API key
    if not RESEND_API_KEY:
        error_msg = (
            "Resend API key missing. Please set RESEND_API_KEY in .env\n"
            "Get your API key at: https://resend.com/api-keys"
        )
        logger.error(f"[send_email] {error_msg}")
        raise ValueError(error_msg)
    
    logger.info(f"[send_email] Sending email to: {to}, subject: {subject}")
    logger.info(f"[send_email] Using Resend API (cloud-friendly, no SMTP ports)")
    
    try:
        import resend
        resend.api_key = RESEND_API_KEY
        
        # Prepare email payload
        email_data = {
            "from": EMAIL_FROM,
            "to": to,
            "subject": subject,
            "html": html,
        }
        
        # Add attachments if provided
        if attachments:
            logger.info(f"[send_email] Adding {len(attachments)} attachment(s)")
            email_data["attachments"] = []
            for (filename, data) in attachments:
                logger.info(f"[send_email] Attachment: {filename}, size: {len(data)} bytes")
                # Resend expects base64-encoded content
                email_data["attachments"].append({
                    "filename": filename,
                    "content": base64.b64encode(data).decode("utf-8")
                })
        else:
            logger.info(f"[send_email] No attachments")
        
        # Send email via Resend API
        logger.info(f"[send_email] 🔄 DEBUG: About to call resend.Emails.send()...")
        logger.info(f"[send_email] 🔄 DEBUG: API Key starts with: {RESEND_API_KEY[:10] if RESEND_API_KEY else 'NONE'}...")
        logger.info(f"[send_email] 🔄 DEBUG: Email data keys: {list(email_data.keys())}")
        
        try:
            response = resend.Emails.send(email_data)
            logger.info(f"[send_email] 🔄 DEBUG: Resend API call completed!")
            logger.info(f"[send_email] 🔄 DEBUG: Response type: {type(response)}")
            logger.info(f"[send_email] 🔄 DEBUG: Response content: {response}")
        except Exception as resend_error:
            logger.error(f"[send_email] 🔄 DEBUG: Exception during Resend call: {type(resend_error).__name__}")
            logger.error(f"[send_email] 🔄 DEBUG: Exception message: {str(resend_error)}")
            raise
        
        # Resend returns: {"id": "..."} on success
        message_id = response.get("id", f"<{uuid4()}@rama.local>")
        logger.info(f"[send_email] ✅ Email sent successfully to {to}, message_id: {message_id}")
        
        # Log email sent event to Logfire
        logfire.info("email_sent", to=to, subject=subject, attachments_count=len(attachments or []), message_id=message_id)
        
        return {
            "sent": True, 
            "success": True,
            "status": "Email sent successfully via Resend API",
            "to": to, 
            "subject": subject, 
            "message_id": message_id
        }
        
    except ImportError:
        error_msg = (
            "Resend library not installed. Please run:\n"
            "pip install resend"
        )
        logger.error(f"[send_email] {error_msg}")
        raise ImportError(error_msg)
    except Exception as e:
        logger.error(f"[send_email] ❌ Error sending email via Resend: {e}", exc_info=True)
        raise
