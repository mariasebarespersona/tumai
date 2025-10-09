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
    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(html, subtype="html")
    for (filename, data) in attachments or []:
        msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=filename)
    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls(context=ctx)
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
    return {"sent": True, "to": to, "subject": subject}
