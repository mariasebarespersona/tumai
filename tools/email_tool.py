from __future__ import annotations
import os, smtplib, ssl
from email.message import EmailMessage
from typing import List

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)

def send_email(to: List[str], subject: str, html: str, attachments: List[tuple[str, bytes]] = None):
    import logging
    logger = logging.getLogger(__name__)
    
    # Validate SMTP configuration
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        error_msg = "SMTP configuration missing. Please set SMTP_HOST, SMTP_USER, and SMTP_PASS in .env"
        logger.error(f"[send_email] {error_msg}")
        raise ValueError(error_msg)
    
    logger.info(f"[send_email] Sending email to: {to}, subject: {subject}")
    logger.info(f"[send_email] SMTP_HOST: {SMTP_HOST}, SMTP_PORT: {SMTP_PORT}, SMTP_USER: {SMTP_USER}")
    
    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(html, subtype="html")
    
    if attachments:
        logger.info(f"[send_email] Adding {len(attachments)} attachment(s)")
        for (filename, data) in attachments:
            logger.info(f"[send_email] Attachment: {filename}, size: {len(data)} bytes")
            msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=filename)
    else:
        logger.info(f"[send_email] No attachments")
    
    # Create SSL context - use unverified context if default fails (common on macOS)
    try:
        ctx = ssl.create_default_context()
    except Exception:
        ctx = ssl._create_unverified_context()
    
    try:
        logger.info(f"[send_email] Connecting to SMTP server...")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
            logger.info(f"[send_email] Starting TLS...")
            s.starttls(context=ctx)
            logger.info(f"[send_email] Logging in...")
            s.login(SMTP_USER, SMTP_PASS)
            logger.info(f"[send_email] Sending message...")
            s.send_message(msg)
            logger.info(f"[send_email] ✅ Email sent successfully to {to}")
    except ssl.SSLError as e:
        logger.warning(f"[send_email] SSL error, trying with unverified context: {e}")
        # Fallback: try with unverified context
        ctx = ssl._create_unverified_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
            s.starttls(context=ctx)
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
            logger.info(f"[send_email] ✅ Email sent successfully (unverified SSL) to {to}")
    except Exception as e:
        logger.error(f"[send_email] ❌ Error sending email: {e}", exc_info=True)
        raise
    
    return {"sent": True, "to": to, "subject": subject}
