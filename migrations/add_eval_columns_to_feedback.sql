-- ============================================================================
-- Migration: Add evaluation columns to agent_feedback table
-- Purpose: Enable LLM-based evaluations (tool selection, response quality, task success)
-- Date: 2025-11-20
-- ============================================================================

-- Add evaluation score columns
ALTER TABLE public.agent_feedback 
ADD COLUMN IF NOT EXISTS tool_selection_score FLOAT,
ADD COLUMN IF NOT EXISTS response_quality_score FLOAT,
ADD COLUMN IF NOT EXISTS task_success_score FLOAT,
ADD COLUMN IF NOT EXISTS eval_reasoning JSONB,
ADD COLUMN IF NOT EXISTS eval_timestamp TIMESTAMPTZ;

-- Create index for faster queries on eval_timestamp
CREATE INDEX IF NOT EXISTS idx_agent_feedback_eval_timestamp 
ON public.agent_feedback (eval_timestamp DESC NULLS LAST);

-- Add comment to document the schema
COMMENT ON COLUMN public.agent_feedback.tool_selection_score IS 'Score from 0.0 to 1.0 indicating if correct tools were selected';
COMMENT ON COLUMN public.agent_feedback.response_quality_score IS 'Score from 0.0 to 1.0 from LLM-as-Judge evaluating response quality';
COMMENT ON COLUMN public.agent_feedback.task_success_score IS 'Score from 0.0 to 1.0 indicating if task was completed successfully (verified in DB)';
COMMENT ON COLUMN public.agent_feedback.eval_reasoning IS 'JSONB with detailed reasoning for each evaluation layer';
COMMENT ON COLUMN public.agent_feedback.eval_timestamp IS 'Timestamp when the evaluation pipeline completed';

-- Verify columns were added
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public' 
  AND table_name = 'agent_feedback'
  AND column_name IN ('tool_selection_score', 'response_quality_score', 'task_success_score', 'eval_reasoning', 'eval_timestamp')
ORDER BY ordinal_position;

