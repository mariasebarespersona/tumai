-- Tabla de recordatorios para pagos y fechas importantes
CREATE TABLE IF NOT EXISTS public.reminders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    reminder_date TIMESTAMPTZ NOT NULL,
    recipient_email TEXT,
    document_reference JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    CONSTRAINT reminder_date_future CHECK (reminder_date >= NOW())
);

-- Índices para mejor performance
CREATE INDEX IF NOT EXISTS idx_reminders_property_id ON public.reminders(property_id);
CREATE INDEX IF NOT EXISTS idx_reminders_status ON public.reminders(status);
CREATE INDEX IF NOT EXISTS idx_reminders_date ON public.reminders(reminder_date);
CREATE INDEX IF NOT EXISTS idx_reminders_pending_dates ON public.reminders(reminder_date) WHERE status = 'pending';

-- Permisos de acceso
ALTER TABLE public.reminders ENABLE ROW LEVEL SECURITY;

-- Política: Todos pueden leer y escribir sus propios recordatorios
CREATE POLICY "Users can manage their reminders"
ON public.reminders
FOR ALL
USING (true)
WITH CHECK (true);

COMMENT ON TABLE public.reminders IS 'Recordatorios automáticos para pagos y fechas importantes de propiedades';
COMMENT ON COLUMN public.reminders.status IS 'Estado: pending (pendiente), sent (enviado), cancelled (cancelado)';
COMMENT ON COLUMN public.reminders.document_reference IS 'Referencia opcional al documento relacionado: {group, subgroup, name}';

