-- Migration: Document Framework V3 (COMPRA / R2B / Promoción)
-- Updates the document structure to match the new business logic:
-- 1. COMPRA (Compulsory)
-- 2. R2B (Diseño -> Venta OR Venta+PM)
-- 3. Promoción (Obra -> Venta)

CREATE OR REPLACE FUNCTION public.seed_documents_v3(p_id uuid)
RETURNS void AS $$
DECLARE
  sid text := public.shortid(p_id);
  sch text := format('prop_%s__documents_framework', sid);
BEGIN
  -- 1. COMPRA (Compulsory for ALL)
  -- Group: COMPRA, Subgroup: ''
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

  -- 2. R2B - Docs diseño + facturas (Step 1 of R2B)
  -- Group: R2B, Subgroup: Diseño
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

  -- 2.1 R2B - Venta R2B (Option A)
  -- Group: R2B, Subgroup: Venta
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

  -- 2.2 R2B - Venta R2B + Project Manager (Option B)
  -- Group: R2B, Subgroup: Venta + PM
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

  -- 3. Promoción
  -- Group: Promoción, Subgroup: Obra
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

  -- 3. Promoción - Venta en Promoción
  -- Group: Promoción, Subgroup: Venta
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

