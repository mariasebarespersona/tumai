"""
Backward-compat launcher for reminders setup. The real implementation should be moved to scripts/.
"""
from scripts import setup_reminders as _impl  # type: ignore

if __name__ == "__main__":
    _impl.main()  # expects scripts/setup_reminders.py to expose main()
#!/usr/bin/env python3
"""
Script de configuración para el sistema de recordatorios.
Crea la tabla 'reminders' en Supabase si no existe.
"""
import env_loader
from tools.supabase_client import sb
import sys

SQL_CREATE_TABLE = """
-- Tabla de recordatorios para pagos y fechas importantes
CREATE TABLE IF NOT EXISTS public.reminders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    reminder_date TIMESTAMPTZ NOT NULL,
    recipient_email TEXT,
    document_reference JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ
);

-- Índices para mejor performance
CREATE INDEX IF NOT EXISTS idx_reminders_property_id ON public.reminders(property_id);
CREATE INDEX IF NOT EXISTS idx_reminders_status ON public.reminders(status);
CREATE INDEX IF NOT EXISTS idx_reminders_date ON public.reminders(reminder_date);
CREATE INDEX IF NOT EXISTS idx_reminders_pending_dates ON public.reminders(reminder_date) WHERE status = 'pending';

-- Permisos de acceso
ALTER TABLE public.reminders ENABLE ROW LEVEL SECURITY;

-- Política: Todos pueden leer y escribir sus propios recordatorios
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'reminders' 
        AND policyname = 'Users can manage their reminders'
    ) THEN
        CREATE POLICY "Users can manage their reminders"
        ON public.reminders
        FOR ALL
        USING (true)
        WITH CHECK (true);
    END IF;
END
$$;
"""

def setup_reminders_table():
    """Crea la tabla de recordatorios en Supabase."""
    print("🔧 Configurando tabla de recordatorios en Supabase...")
    
    try:
        # Intentar verificar si la tabla existe
        result = sb.table("reminders").select("id").limit(1).execute()
        print("✅ La tabla 'reminders' ya existe")
        return True
        
    except Exception as e:
        error_msg = str(e)
        
        if "does not exist" in error_msg or "Could not find the table" in error_msg or "PGRST" in error_msg:
            print("❌ La tabla 'reminders' no existe")
            print("\n🔨 Intentando crear la tabla...")
            
            # Intentar crear usando psycopg2 si DATABASE_URL está disponible
            import os
            database_url = os.getenv("DATABASE_URL")
            
            if database_url and database_url.startswith("postgresql"):
                try:
                    import psycopg2
                    conn = psycopg2.connect(database_url)
                    cur = conn.cursor()
                    cur.execute(SQL_CREATE_TABLE)
                    conn.commit()
                    cur.close()
                    conn.close()
                    print("✅ Tabla 'reminders' creada exitosamente")
                    return True
                except ImportError:
                    print("⚠️  psycopg2 no está instalado")
                    print("   Instala con: pip install psycopg2-binary")
                except Exception as db_error:
                    print(f"❌ Error creando tabla: {db_error}")
            
            # Si no se pudo crear automáticamente, mostrar instrucciones
            print("\n📋 Para crear la tabla manualmente, ejecuta este SQL en Supabase:")
            print("=" * 80)
            print(SQL_CREATE_TABLE)
            print("=" * 80)
            print("\nO ejecuta:")
            print("  psql $DATABASE_URL < migrations/create_reminders_table.sql")
            print("\nO copia el SQL anterior y pégalo en el SQL Editor de Supabase.")
            return False
        else:
            print(f"⚠️  Error inesperado: {error_msg}")
            return False

if __name__ == "__main__":
    success = setup_reminders_table()
    sys.exit(0 if success else 1)

