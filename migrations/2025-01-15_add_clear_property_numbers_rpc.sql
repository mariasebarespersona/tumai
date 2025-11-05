-- Add RPC to clear all number values for a property
-- This is used when selecting a new numbers template to start fresh

-- Drop existing function if it exists (for idempotency)
DROP FUNCTION IF EXISTS public.clear_property_numbers(uuid);

-- Create RPC to clear all number values
CREATE OR REPLACE FUNCTION public.clear_property_numbers(p_id uuid)
RETURNS void AS $$
DECLARE
  sid text := public.shortid(p_id);
  sch text := format('prop_%s__numbers_framework', sid);
  sql text;
BEGIN
  -- Check if schema exists
  IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = sch) THEN
    RAISE NOTICE 'Schema % does not exist, skipping clear', sch;
    RETURN;
  END IF;

  -- Update all line_items to set amount = NULL
  sql := format('UPDATE %I.line_items SET amount = NULL WHERE property_id = $1', sch);
  EXECUTE sql USING p_id;
  
  RAISE NOTICE 'Cleared all number values for property %', p_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

