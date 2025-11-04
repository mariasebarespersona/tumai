-- Document Framework V2 (I/II/III/IV) — per-property schemas rebuild
-- Run this in Supabase SQL editor. It will DROP and RECREATE the per‑property
-- documents schemas with the new structure and seed rows.

-- Safety: drop old helper/RPCs if they exist (avoids 42P13 return-type conflicts)
DROP FUNCTION IF EXISTS public.list_property_documents(uuid);
DROP FUNCTION IF EXISTS public.get_property_document_storage_key(uuid, text, text, text);
DROP FUNCTION IF EXISTS public.update_property_document_link(uuid, text, text, text, text, text, jsonb, text, timestamptz);
DROP FUNCTION IF EXISTS public.insert_property_document(uuid, text, text, text, text, uuid, date, boolean, boolean, jsonb);
DROP FUNCTION IF EXISTS public.ensure_documents_schema_v2(uuid);
DROP FUNCTION IF EXISTS public.seed_documents_v2(uuid);

-- Ensure UUID extension (some projects already have it)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Helper: shortid(uuid) -> 8 chars used in schema names
CREATE OR REPLACE FUNCTION public.shortid(u uuid)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$ SELECT left(replace(u::text, '-', ''), 8) $$;

-- Core: create or replace per‑property documents schema + table
CREATE OR REPLACE FUNCTION public.ensure_documents_schema_v2(p_id uuid)
RETURNS void AS $$
DECLARE
  sid text := public.shortid(p_id);
  sch text := format('prop_%s__documents_framework', sid);
BEGIN
  -- Drop old schema if exists and recreate clean
  EXECUTE format('DROP SCHEMA IF EXISTS %I CASCADE', sch);
  EXECUTE format('CREATE SCHEMA %I', sch);

  -- Table with parent/child relations and placeholders support
  EXECUTE format($DDL$
    CREATE TABLE %I.documents (
      id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
      property_id uuid NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
      document_group text NOT NULL,
      document_subgroup text NOT NULL DEFAULT '',
      document_name text NOT NULL,
      document_kind text NOT NULL DEFAULT 'document' CHECK (document_kind IN ('document','factura')),
      parent_document_id uuid NULL,
      storage_key text DEFAULT '',
      content_type text,
      metadata jsonb DEFAULT '{}',
      last_signed_url text,
      signed_url_expires_at timestamptz,
      due_date date,
      placeholder boolean NOT NULL DEFAULT false,
      auto_generated boolean NOT NULL DEFAULT false,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(property_id, document_group, document_subgroup, document_name)
    );
  $DDL$, sch);

  -- FK for parent → child within same table
  EXECUTE format('ALTER TABLE %I.documents ADD CONSTRAINT documents_parent_fk FOREIGN KEY (parent_document_id) REFERENCES %I.documents(id) ON DELETE CASCADE', sch, sch);

  -- Permissions: allow PostgREST service_role to use and modify this schema
  EXECUTE format('GRANT USAGE ON SCHEMA %I TO service_role', sch);
  EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO service_role', sch);
  EXECUTE format('GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA %I TO service_role', sch);
  EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO service_role', sch);

  -- Seed rows — Section I (R2B) compulsory
  PERFORM public.seed_documents_v2(p_id);
END;$$ LANGUAGE plpgsql;

-- Seeder for a single property
CREATE OR REPLACE FUNCTION public.seed_documents_v2(p_id uuid)
RETURNS void AS $$
DECLARE
  sid text := public.shortid(p_id);
  sch text := format('prop_%s__documents_framework', sid);
BEGIN
  -- I) R2B — Compra
  EXECUTE format($SQL$
    INSERT INTO %I.documents(property_id, document_group, document_subgroup, document_name)
    SELECT $1, 'R2B', 'Compra', x
    FROM (VALUES
      ('Catastro y nota simple'),
      ('Acuerdo compraventa (verbal)'),
      ('Señal / Arras'),
      ('Due Diligence (DD) compra'),
      ('Escritura notarial de compraventa'),
      ('Notaría — factura'),
      ('Impuestos de compra (ITP/IVA/Actos jurídicos)'),
      ('Registro de la propiedad')
    ) v(x)
    ON CONFLICT DO NOTHING;
  $SQL$, sch) USING p_id;

  -- I) R2B — Diseño/Obra (parent docs; facturas are generated automatically on upload)
  EXECUTE format($SQL$
    INSERT INTO %I.documents(property_id, document_group, document_subgroup, document_name)
    SELECT $1, 'R2B', 'Diseño/Obra', x
    FROM (VALUES
      ('Mapas Nivel'),
      ('Contrato arquitecto'),
      ('Proyecto básico / mediciones / planos'),
      ('Contrato Aparejador'),
      ('Licencia de obra y acometidas'),
      ('Contrato constructor')
    ) v(x)
    ON CONFLICT DO NOTHING;
  $SQL$, sch) USING p_id;

  -- II) Venta R2B (only one of II/III/IV will be filled by user)
  EXECUTE format($SQL$
    INSERT INTO %I.documents(property_id, document_group, document_subgroup, document_name)
    SELECT $1, 'Venta R2B', '', x
    FROM (VALUES
      ('Due Diligence (DD) de venta'),
      ('Arras venta'),
      ('Venta terreno'),
      ('Venta proyecto'),
      ('Escritura compraventa'),
      ('Impuestos de venta')
    ) v(x)
    ON CONFLICT DO NOTHING;
  $SQL$, sch) USING p_id;

  -- III) Venta R2B + Raquel PM
  EXECUTE format($SQL$
    INSERT INTO %I.documents(property_id, document_group, document_subgroup, document_name)
    SELECT $1, 'Venta R2B + Raquel PM', '', x
    FROM (VALUES
      ('Planificación obra (cronograma)'),
      ('Contrato obra'),
      ('Facturas (múltiples documentos)'),
      ('Contrato Raquel como PM')
    ) v(x)
    ON CONFLICT DO NOTHING;
  $SQL$, sch) USING p_id;

  -- IV) Promoción — Obra nueva
  EXECUTE format($SQL$
    INSERT INTO %I.documents(property_id, document_group, document_subgroup, document_name)
    SELECT $1, 'Promoción', 'Obra nueva', x
    FROM (VALUES
      ('Planificación obra (cronograma)'),
      ('Contrato obra'),
      ('Facturas (múltiples documentos)'),
      ('OCT'),
      ('Seguro decenal'),
      ('Libro del edificio'),
      ('Escritura obra nueva')
    ) v(x)
    ON CONFLICT DO NOTHING;
  $SQL$, sch) USING p_id;

  -- IV) Promoción — Venta
  EXECUTE format($SQL$
    INSERT INTO %I.documents(property_id, document_group, document_subgroup, document_name)
    SELECT $1, 'Promoción', 'Venta', x
    FROM (VALUES
      ('Contrato arras venta'),
      ('Registro obra nueva'),
      ('Escritura compraventa'),
      ('Impuestos de venta')
    ) v(x)
    ON CONFLICT DO NOTHING;
  $SQL$, sch) USING p_id;
END;$$ LANGUAGE plpgsql;

-- RPC helpers compatible with the app fallbacks
CREATE OR REPLACE FUNCTION public.list_property_documents(p_id uuid)
RETURNS SETOF jsonb AS $$
DECLARE
  sid text := public.shortid(p_id);
  sch text := format('prop_%s__documents_framework', sid);
  sql text;
BEGIN
  sql := format('SELECT to_jsonb(t) FROM %I.documents t WHERE property_id = $1 ORDER BY document_group, document_subgroup, document_name', sch);
  RETURN QUERY EXECUTE sql USING p_id;
END;$$ LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public;

CREATE OR REPLACE FUNCTION public.get_property_document_storage_key(p_id uuid, g text, sg text, n text)
RETURNS text AS $$
DECLARE
  sid text := public.shortid(p_id);
  sch text := format('prop_%s__documents_framework', sid);
  sql text;
  out text;
BEGIN
  sql := format('SELECT storage_key FROM %I.documents WHERE property_id = $1 AND document_group = $2 AND document_subgroup = $3 AND document_name = $4 LIMIT 1', sch);
  EXECUTE sql INTO out USING p_id, g, coalesce(sg, ''), n;
  RETURN out;
END;$$ LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public;

CREATE OR REPLACE FUNCTION public.update_property_document_link(
  p_id uuid, g text, sg text, n text,
  storage_key text, content_type text, metadata jsonb, signed_url text, expires_at timestamptz
)
RETURNS void AS $$
DECLARE
  sid text := public.shortid(p_id);
  sch text := format('prop_%s__documents_framework', sid);
  sql text;
BEGIN
  sql := format('UPDATE %I.documents SET storage_key=$5, content_type=$6, metadata=$7, last_signed_url=$8, signed_url_expires_at=$9, updated_at=now() WHERE property_id=$1 AND document_group=$2 AND document_subgroup=$3 AND document_name=$4', sch);
  EXECUTE sql USING p_id, g, coalesce(sg, ''), n, storage_key, content_type, coalesce(metadata, '{}'::jsonb), signed_url, expires_at;
END;$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE OR REPLACE FUNCTION public.insert_property_document(
  p_id uuid, g text, sg text, n text, doc_kind text,
  parent_id uuid, due_date date, is_placeholder boolean, is_auto_generated boolean, metadata jsonb
)
RETURNS uuid AS $$
DECLARE
  sid text := public.shortid(p_id);
  sch text := format('prop_%s__documents_framework', sid);
  sql text;
  new_id uuid;
BEGIN
  sql := format('INSERT INTO %I.documents (property_id, document_group, document_subgroup, document_name, document_kind, parent_document_id, due_date, placeholder, auto_generated, metadata) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING id', sch);
  EXECUTE sql INTO new_id USING p_id, g, coalesce(sg, ''), n, doc_kind, parent_id, due_date, is_placeholder, is_auto_generated, coalesce(metadata, '{}'::jsonb);
  RETURN new_id;
END;$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Apply to all existing properties
DO $$
DECLARE r RECORD; BEGIN
  FOR r IN SELECT id FROM public.properties LOOP
    PERFORM public.ensure_documents_schema_v2(r.id);
  END LOOP;
END$$;

-- Ensure permissions on any pre-existing schemas (idempotent)
DO $$
DECLARE s RECORD; BEGIN
  FOR s IN SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'prop_%__documents_framework' LOOP
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO service_role', s.schema_name);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO service_role', s.schema_name);
    EXECUTE format('GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA %I TO service_role', s.schema_name);
    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO service_role', s.schema_name);
  END LOOP;
END$$;


