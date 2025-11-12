-- Numbers Table Framework: Excel replica stored in DB
-- This migration creates tables to store Excel template structure and cell values
-- Run this in Supabase SQL editor

-- Ensure UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table to store Excel template structures (headers, labels, format, formulas)
CREATE TABLE IF NOT EXISTS public.numbers_templates (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  template_key text NOT NULL, -- e.g., "R2B", "R2B+PM"
  property_id uuid NULL REFERENCES public.properties(id) ON DELETE CASCADE,
  structure_json jsonb NOT NULL DEFAULT '{}', -- Full Excel structure: rows, columns, headers, format, formulas
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(template_key, property_id) -- One template per property (or global if property_id is NULL)
);

-- Index for fast lookup
CREATE INDEX IF NOT EXISTS idx_numbers_templates_template_key ON public.numbers_templates(template_key);
CREATE INDEX IF NOT EXISTS idx_numbers_templates_property_id ON public.numbers_templates(property_id);

-- Table to store cell values for each property's Numbers table
CREATE TABLE IF NOT EXISTS public.numbers_table_values (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id uuid NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
  template_key text NOT NULL, -- e.g., "R2B"
  cell_address text NOT NULL, -- e.g., "B6", "C7"
  value text, -- Can be number, text, or formula (for future)
  row_label text, -- e.g., "Precio de venta" (from column A)
  col_label text, -- e.g., "Importe (€)" (from row 4)
  format_json jsonb DEFAULT '{}', -- Store cell format: {bg_color, font_color, bold, borders, etc.}
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(property_id, template_key, cell_address) -- One value per cell
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_numbers_table_values_property_template ON public.numbers_table_values(property_id, template_key);
CREATE INDEX IF NOT EXISTS idx_numbers_table_values_cell_address ON public.numbers_table_values(cell_address);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_numbers_templates_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_numbers_templates_updated_at
  BEFORE UPDATE ON public.numbers_templates
  FOR EACH ROW
  EXECUTE FUNCTION public.update_numbers_templates_updated_at();

CREATE OR REPLACE FUNCTION public.update_numbers_table_values_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_numbers_table_values_updated_at
  BEFORE UPDATE ON public.numbers_table_values
  FOR EACH ROW
  EXECUTE FUNCTION public.update_numbers_table_values_updated_at();

-- RPC function to get template structure
CREATE OR REPLACE FUNCTION public.get_numbers_template_structure(
  p_template_key text,
  p_property_id uuid DEFAULT NULL
)
RETURNS jsonb AS $$
DECLARE
  result jsonb;
BEGIN
  SELECT structure_json INTO result
  FROM public.numbers_templates
  WHERE template_key = p_template_key
    AND (property_id = p_property_id OR (property_id IS NULL AND p_property_id IS NULL))
  ORDER BY property_id NULLS LAST -- Prefer property-specific over global
  LIMIT 1;
  
  RETURN COALESCE(result, '{}'::jsonb);
END;
$$ LANGUAGE plpgsql;

-- RPC function to get all cell values for a property's template
CREATE OR REPLACE FUNCTION public.get_numbers_table_values(
  p_property_id uuid,
  p_template_key text
)
RETURNS jsonb AS $$
DECLARE
  result jsonb := '{}';
BEGIN
  SELECT jsonb_object_agg(cell_address, jsonb_build_object(
    'value', value,
    'row_label', row_label,
    'col_label', col_label,
    'format', format_json
  )) INTO result
  FROM public.numbers_table_values
  WHERE property_id = p_property_id AND template_key = p_template_key;
  
  RETURN COALESCE(result, '{}'::jsonb);
END;
$$ LANGUAGE plpgsql;

-- RPC function to set a cell value
CREATE OR REPLACE FUNCTION public.set_numbers_table_cell(
  p_property_id uuid,
  p_template_key text,
  p_cell_address text,
  p_value text,
  p_row_label text DEFAULT NULL,
  p_col_label text DEFAULT NULL,
  p_format_json jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb AS $$
BEGIN
  INSERT INTO public.numbers_table_values (
    property_id, template_key, cell_address, value, row_label, col_label, format_json
  )
  VALUES (p_property_id, p_template_key, p_cell_address, p_value, p_row_label, p_col_label, p_format_json)
  ON CONFLICT (property_id, template_key, cell_address)
  DO UPDATE SET
    value = EXCLUDED.value,
    row_label = COALESCE(EXCLUDED.row_label, numbers_table_values.row_label),
    col_label = COALESCE(EXCLUDED.col_label, numbers_table_values.col_label),
    format_json = COALESCE(EXCLUDED.format_json, numbers_table_values.format_json),
    updated_at = now();
  
  RETURN jsonb_build_object('ok', true, 'cell_address', p_cell_address, 'value', p_value);
END;
$$ LANGUAGE plpgsql;

