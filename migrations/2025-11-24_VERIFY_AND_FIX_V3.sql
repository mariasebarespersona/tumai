-- ============================================================================
-- MIGRATION: Verificar y Arreglar Estructura V3 de Documentos
-- ============================================================================
-- Este script:
-- 1. Verifica si seed_documents_v3 existe
-- 2. Si no existe, la crea
-- 3. Verifica si set_property_strategy existe
-- 4. Si no existe, la crea
-- 5. Limpia cualquier propiedad con estructura antigua
-- ============================================================================

-- 1. Verificar funciones existentes
DO $$
BEGIN
  -- Check if seed_documents_v3 exists
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname = 'seed_documents_v3'
  ) THEN
    RAISE NOTICE '❌ seed_documents_v3 NO EXISTE - Creándola ahora...';
  ELSE
    RAISE NOTICE '✅ seed_documents_v3 existe';
  END IF;

  -- Check if set_property_strategy exists
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname = 'set_property_strategy'
  ) THEN
    RAISE NOTICE '❌ set_property_strategy NO EXISTE - Creándola ahora...';
  ELSE
    RAISE NOTICE '✅ set_property_strategy existe';
  END IF;

  -- Check if strategy column exists
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'properties'
      AND column_name = 'strategy'
  ) THEN
    RAISE NOTICE '❌ Columna strategy NO EXISTE - Creándola ahora...';
  ELSE
    RAISE NOTICE '✅ Columna strategy existe';
  END IF;
END $$;

-- 2. Crear columna strategy si no existe
ALTER TABLE public.properties 
ADD COLUMN IF NOT EXISTS strategy text DEFAULT NULL;

-- 3. Crear función set_property_strategy
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

-- 4. Crear función get_property_strategy
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

-- 5. Crear función seed_documents_v3
CREATE OR REPLACE FUNCTION public.seed_documents_v3(p_id uuid)
RETURNS void AS $$
DECLARE
  sid text := public.shortid(p_id);
  sch text := format('prop_%s__documents_framework', sid);
BEGIN
  -- 1. COMPRA (Compulsory for ALL)
  EXECUTE format($SQL$
    INSERT INTO %I.documents(property_id, document_group, document_subgroup, document_name)
    SELECT $1, 'COMPRA', '', x
    FROM (VALUES
      ('Catastro y la nota simple'),
      ('Acuerdo compraventa (verbal)'),
      ('Señal / Arras'),
      ('Due Diligence (DD) compra'),
      ('Escritura notarial de compraventa'),
      ('Notaria factura'),
      ('Impuestos de compra (ITP/IVA/Actos jurídicos)'),
      ('Registro de la propiedad')
    ) v(x)
    ON CONFLICT DO NOTHING;
  $SQL$, sch) USING p_id;

  -- 2. R2B - Diseño
  EXECUTE format($SQL$
    INSERT INTO %I.documents(property_id, document_group, document_subgroup, document_name)
    SELECT $1, 'R2B', 'Diseño', x
    FROM (VALUES
      ('Mapas Nivel + facturas'),
      ('Contrato arquitecto + facturas arquitecto'),
      ('Projecto basico/ mediciones/planos'),
      ('Contrato Aparejador + facturas'),
      ('Licencia de obra y acometidas + facturas'),
      ('Contrato constructor + facturas')
    ) v(x)
    ON CONFLICT DO NOTHING;
  $SQL$, sch) USING p_id;

  -- 2.1 R2B - Venta
  EXECUTE format($SQL$
    INSERT INTO %I.documents(property_id, document_group, document_subgroup, document_name)
    SELECT $1, 'R2B', 'Venta', x
    FROM (VALUES
      ('Due Diligence (DD) de venta'),
      ('Arras venta'),
      ('Venta terreno'),
      ('Venta projecto'),
      ('Escritura compraventa'),
      ('Impuestos de venta')
    ) v(x)
    ON CONFLICT DO NOTHING;
  $SQL$, sch) USING p_id;

  -- 2.2 R2B - Venta + PM
  EXECUTE format($SQL$
    INSERT INTO %I.documents(property_id, document_group, document_subgroup, document_name)
    SELECT $1, 'R2B', 'Venta + PM', x
    FROM (VALUES
      ('Planificacion obra (cronograma)'),
      ('Contrato obra'),
      ('Facturas (multiples documentos)'),
      ('Contrato Raquel como PM')
    ) v(x)
    ON CONFLICT DO NOTHING;
  $SQL$, sch) USING p_id;

  -- 3. Promoción - Obra
  EXECUTE format($SQL$
    INSERT INTO %I.documents(property_id, document_group, document_subgroup, document_name)
    SELECT $1, 'Promoción', 'Obra', x
    FROM (VALUES
      ('Planificacion obra (cronograma)'),
      ('Contrato obra'),
      ('Facturas (multiples documentos)'),
      ('OCT'),
      ('Seguro decenal'),
      ('Libro del edificio'),
      ('Escritura obra nueva')
    ) v(x)
    ON CONFLICT DO NOTHING;
  $SQL$, sch) USING p_id;

  -- 3. Promoción - Venta
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

END;$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 6. Grant permissions
GRANT EXECUTE ON FUNCTION public.seed_documents_v3(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.set_property_strategy(uuid, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.get_property_strategy(uuid) TO service_role;

-- 7. Reload schema
SELECT pg_notify('pgrst', 'reload schema');

-- ============================================================================
-- VERIFICACIÓN FINAL
-- ============================================================================
DO $$
DECLARE
  v3_exists boolean;
  strategy_fn_exists boolean;
  strategy_col_exists boolean;
BEGIN
  -- Check seed_documents_v3
  SELECT EXISTS (
    SELECT 1 FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname = 'seed_documents_v3'
  ) INTO v3_exists;

  -- Check set_property_strategy
  SELECT EXISTS (
    SELECT 1 FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname = 'set_property_strategy'
  ) INTO strategy_fn_exists;

  -- Check strategy column
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'properties'
      AND column_name = 'strategy'
  ) INTO strategy_col_exists;

  -- Report
  RAISE NOTICE '';
  RAISE NOTICE '=== VERIFICACIÓN FINAL ===';
  IF v3_exists THEN
    RAISE NOTICE '✅ seed_documents_v3 existe';
  ELSE
    RAISE NOTICE '❌ seed_documents_v3 NO existe';
  END IF;

  IF strategy_fn_exists THEN
    RAISE NOTICE '✅ set_property_strategy existe';
  ELSE
    RAISE NOTICE '❌ set_property_strategy NO existe';
  END IF;

  IF strategy_col_exists THEN
    RAISE NOTICE '✅ Columna strategy existe';
  ELSE
    RAISE NOTICE '❌ Columna strategy NO existe';
  END IF;

  IF v3_exists AND strategy_fn_exists AND strategy_col_exists THEN
    RAISE NOTICE '';
    RAISE NOTICE '🎉 MIGRACIÓN V3 COMPLETA - SISTEMA LISTO';
    RAISE NOTICE '';
  ELSE
    RAISE NOTICE '';
    RAISE NOTICE '⚠️ ALGUNAS FUNCIONES FALTAN - REVISAR ERRORES ARRIBA';
    RAISE NOTICE '';
  END IF;
END $$;

