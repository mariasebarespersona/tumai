#!/usr/bin/env python3
"""
Cron job para enviar recordatorios pendientes.
Debe ejecutarse diariamente (ej: 9:00 AM).

Configuración del cron:
0 9 * * * cd /path/to/rama-agentic-ai && python3 send_reminders_cron.py
"""
import env_loader
from datetime import datetime, timedelta
from tools.reminders_tools import send_reminder_email
from tools.supabase_client import sb

def send_due_reminders():
    """Envía todos los recordatorios cuya fecha es hoy o anterior."""
    print(f"🔔 Checking for reminders to send at {datetime.now()}")
    
    # Buscar recordatorios pendientes cuya fecha es hoy o anterior
    today = datetime.utcnow().date()
    cutoff = (datetime.utcnow() + timedelta(days=1)).isoformat()  # Hasta mañana
    
    try:
        reminders = sb.table("reminders")\
            .select("*")\
            .eq("status", "pending")\
            .lte("reminder_date", cutoff)\
            .execute()
        
        if not reminders.data:
            print("✅ No reminders to send today")
            return
        
        print(f"📬 Found {len(reminders.data)} reminders to send")
        
        sent_count = 0
        error_count = 0
        
        for reminder in reminders.data:
            reminder_id = reminder.get("id")
            title = reminder.get("title")
            
            try:
                result = send_reminder_email(reminder_id)
                if result.get("sent"):
                    print(f"✅ Sent: {title} (ID: {reminder_id[:8]}...)")
                    sent_count += 1
                else:
                    print(f"❌ Failed: {title} - {result.get('error')}")
                    error_count += 1
            except Exception as e:
                print(f"❌ Error sending {title}: {e}")
                error_count += 1
        
        print(f"\n📊 Summary: {sent_count} sent, {error_count} errors")
        
    except Exception as e:
        print(f"❌ Error querying reminders: {e}")

if __name__ == "__main__":
    send_due_reminders()

