-- ============================================================================
-- Script: Delete old feedbacks without evaluations
-- Purpose: Remove feedback entries created BEFORE the eval columns were added
-- Date: 2025-11-20
-- ============================================================================
--
-- IMPORTANTE: Este script elimina feedbacks antiguos que NO tienen evaluaciones.
-- Solo los feedbacks NUEVOS (después de ejecutar add_eval_columns_to_feedback.sql)
-- tienen las columnas de evaluación rellenas.
--
-- ¿Por qué eliminarlos?
-- - Los feedbacks antiguos hacen que el dashboard muestre "N/A" porque no tienen evaluaciones
-- - Al eliminarlos, el dashboard calculará promedios solo de los feedbacks nuevos
-- ============================================================================

-- Ver cuántos feedbacks se eliminarán (EJECUTA ESTO PRIMERO)
SELECT 
    COUNT(*) as total_to_delete,
    MIN(created_at) as oldest,
    MAX(created_at) as newest
FROM public.agent_feedback 
WHERE tool_selection_score IS NULL 
  AND response_quality_score IS NULL
  AND task_success_score IS NULL;

-- Si estás de acuerdo con eliminarlos, ejecuta este DELETE:
-- (Quita los comentarios -- antes de DELETE para ejecutarlo)

-- DELETE FROM public.agent_feedback 
-- WHERE tool_selection_score IS NULL 
--   AND response_quality_score IS NULL
--   AND task_success_score IS NULL;

-- Verificar resultados
SELECT 
    COUNT(*) as total_remaining,
    COUNT(CASE WHEN tool_selection_score IS NOT NULL THEN 1 END) as with_tool_score,
    COUNT(CASE WHEN response_quality_score IS NOT NULL THEN 1 END) as with_quality_score
FROM public.agent_feedback;

