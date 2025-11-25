-- ============================================================================
-- LIMPIEZA: Borrar documentos antiguos y reemplazar con estructura V3
-- ============================================================================
-- Este script:
-- 1. Borra TODOS los documentos de Sobradiel 2
-- 2. Re-siembra con la estructura V3 limpia (COMPRA → R2B/Promoción)
-- ============================================================================

-- Propiedad: Sobradiel 2
DO $$
DECLARE
  p_id uuid := 'c20ceb7d-9bbd-4760-bcd4-d22c72ef0f85';
  sid text;
  sch text;
BEGIN
  sid := public.shortid(p_id);
  sch := format('prop_%s__documents_framework', sid);

  -- 1. BORRAR todos los documentos existentes
  EXECUTE format('DELETE FROM %I.documents WHERE property_id = $1', sch) USING p_id;
  RAISE NOTICE '🧹 Documentos antiguos borrados';

  -- 2. COMPRA (Obligatorio para TODOS)
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
    ) v(x);
  $SQL$, sch) USING p_id;
  RAISE NOTICE '✅ COMPRA (8 docs)';

  -- 3. R2B - Diseño
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
    ) v(x);
  $SQL$, sch) USING p_id;
  RAISE NOTICE '✅ R2B - Diseño (6 docs)';

  -- 4. R2B - Venta
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
    ) v(x);
  $SQL$, sch) USING p_id;
  RAISE NOTICE '✅ R2B - Venta (6 docs)';

  -- 5. R2B - Venta + PM
  EXECUTE format($SQL$
    INSERT INTO %I.documents(property_id, document_group, document_subgroup, document_name)
    SELECT $1, 'R2B', 'Venta + PM', x
    FROM (VALUES
      ('Planificacion obra (cronograma)'),
      ('Contrato obra'),
      ('Facturas (multiples documentos)'),
      ('Contrato Raquel como PM')
    ) v(x);
  $SQL$, sch) USING p_id;
  RAISE NOTICE '✅ R2B - Venta + PM (4 docs)';

  -- 6. Promoción - Obra
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
    ) v(x);
  $SQL$, sch) USING p_id;
  RAISE NOTICE '✅ Promoción - Obra (7 docs)';

  -- 7. Promoción - Venta
  EXECUTE format($SQL$
    INSERT INTO %I.documents(property_id, document_group, document_subgroup, document_name)
    SELECT $1, 'Promoción', 'Venta', x
    FROM (VALUES
      ('Contrato arras venta'),
      ('Registro obra nueva'),
      ('Escritura compraventa'),
      ('Impuestos de venta')
    ) v(x);
  $SQL$, sch) USING p_id;
  RAISE NOTICE '✅ Promoción - Venta (4 docs)';

  RAISE NOTICE '';
  RAISE NOTICE '🎉 ESTRUCTURA V3 LIMPIA APLICADA';
  RAISE NOTICE '📊 Total: 35 documentos (COMPRA: 8 | R2B: 16 | Promoción: 11)';
  RAISE NOTICE '';
  RAISE NOTICE '✅ Ahora reinicia el backend y prueba "documentos" en el chat';
END $$;

