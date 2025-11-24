-- Enable RLS and create permissive policies for all public tables
-- Execute this in Supabase SQL Editor

-- 1. properties
ALTER TABLE public.properties ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable all access for properties"
ON public.properties
FOR ALL
USING (true)
WITH CHECK (true);

-- 2. rag_chunks
ALTER TABLE public.rag_chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable all access for rag_chunks"
ON public.rag_chunks
FOR ALL
USING (true)
WITH CHECK (true);

-- 3. checkpoints
ALTER TABLE public.checkpoints ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable all access for checkpoints"
ON public.checkpoints
FOR ALL
USING (true)
WITH CHECK (true);

-- 4. checkpoint_migrations
ALTER TABLE public.checkpoint_migrations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable all access for checkpoint_migrations"
ON public.checkpoint_migrations
FOR ALL
USING (true)
WITH CHECK (true);

-- 5. checkpoint_blobs
ALTER TABLE public.checkpoint_blobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable all access for checkpoint_blobs"
ON public.checkpoint_blobs
FOR ALL
USING (true)
WITH CHECK (true);

-- 6. checkpoint_writes
ALTER TABLE public.checkpoint_writes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable all access for checkpoint_writes"
ON public.checkpoint_writes
FOR ALL
USING (true)
WITH CHECK (true);

-- 7. numbers_templates
ALTER TABLE public.numbers_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable all access for numbers_templates"
ON public.numbers_templates
FOR ALL
USING (true)
WITH CHECK (true);

-- 8. numbers_table_values
ALTER TABLE public.numbers_table_values ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable all access for numbers_table_values"
ON public.numbers_table_values
FOR ALL
USING (true)
WITH CHECK (true);

-- Verify RLS is enabled
SELECT schemaname, tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN (
    'properties', 
    'rag_chunks', 
    'checkpoints', 
    'checkpoint_migrations', 
    'checkpoint_blobs', 
    'checkpoint_writes',
    'numbers_templates',
    'numbers_table_values'
);

