-- ========================================
-- TABLA DE RECORDATORIOS PARA RAMA
-- ========================================
-- Copia y pega todo este archivo en el SQL Editor de Supabase
-- https://supabase.com/dashboard/project/tqqvgaiueheiqtqmbpjh/sql

-- Crear tabla
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

-- Crear índices para mejor performance
CREATE INDEX IF NOT EXISTS idx_reminders_property_id ON public.reminders(property_id);
CREATE INDEX IF NOT EXISTS idx_reminders_status ON public.reminders(status);
CREATE INDEX IF NOT EXISTS idx_reminders_date ON public.reminders(reminder_date);
CREATE INDEX IF NOT EXISTS idx_reminders_pending_dates ON public.reminders(reminder_date) WHERE status = 'pending';

-- Habilitar Row Level Security
ALTER TABLE public.reminders ENABLE ROW LEVEL SECURITY;

-- Crear política de acceso (permite a todos leer y escribir)
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

-- Verificar que se creó correctamente
SELECT 'Tabla reminders creada exitosamente!' as result;
SELECT COUNT(*) as total_reminders FROM public.reminders;

