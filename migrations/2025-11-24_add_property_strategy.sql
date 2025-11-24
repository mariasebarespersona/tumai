-- Migration to add 'strategy' column to properties table
-- Possible values: 'R2B', 'PROMOCION', 'R2B_VENTA', 'R2B_PM'
-- Default is NULL (user hasn't decided yet)

ALTER TABLE public.properties 
ADD COLUMN IF NOT EXISTS strategy text DEFAULT NULL;

-- Create RPC to update property strategy safely
CREATE OR REPLACE FUNCTION public.set_property_strategy(p_id uuid, new_strategy text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  UPDATE public.properties
  SET strategy = new_strategy
  WHERE id = p_id;
END;
$$;

-- Function to get property strategy
CREATE OR REPLACE FUNCTION public.get_property_strategy(p_id uuid)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  strat text;
BEGIN
  SELECT strategy INTO strat
  FROM public.properties
  WHERE id = p_id;
  
  RETURN strat;
END;
$$;

