-- Ensure document framework functions run with sufficient privileges
-- Mark functions as SECURITY DEFINER and grant execute to service_role

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname = 'ensure_documents_schema_v2'
  ) THEN
    EXECUTE 'ALTER FUNCTION public.ensure_documents_schema_v2(uuid) SECURITY DEFINER';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.ensure_documents_schema_v2(uuid) TO service_role';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname = 'seed_documents_v2'
  ) THEN
    EXECUTE 'ALTER FUNCTION public.seed_documents_v2(uuid) SECURITY DEFINER';
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.seed_documents_v2(uuid) TO service_role';
  END IF;
END $$;

