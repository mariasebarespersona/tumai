-- Agent Feedback & Evaluation System
-- Stores user feedback (thumbs up/down + comments) and automated evaluations

CREATE TABLE IF NOT EXISTS agent_feedback (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  
  -- Context
  property_id UUID REFERENCES properties(id) ON DELETE CASCADE,
  user_id TEXT,
  message_id TEXT NOT NULL UNIQUE,
  agent_name TEXT NOT NULL,
  
  -- Conversation data
  user_message TEXT NOT NULL,
  agent_response TEXT NOT NULL,
  tool_calls JSONB DEFAULT '[]',
  tool_results JSONB DEFAULT '[]',
  
  -- Layer 1: User feedback (manual, real-time)
  rating INT CHECK (rating IN (-1, 1)),  -- -1 = 👎, 1 = 👍
  comment TEXT,
  
  -- Layer 2: Tool selection eval (automated)
  tool_eval JSONB,
  -- {
  --   "accuracy": 0.9,
  --   "precision": 1.0,
  --   "expected_tools": ["add_property"],
  --   "actual_tools": ["add_property"],
  --   "intent": "create_property",
  --   "latency_ms": 234
  -- }
  
  -- Layer 3: Response quality eval (LLM-as-Judge)
  response_eval JSONB,
  -- {
  --   "relevance": 1.0,
  --   "completeness": 0.9,
  --   "accuracy": 1.0,
  --   "tone": 0.95,
  --   "overall": 0.96,
  --   "reasoning": "Response addressed request fully and professionally."
  -- }
  
  -- Layer 4: Task success eval (verifier)
  task_success_eval JSONB,
  -- {
  --   "success": true,
  --   "verification_steps": [
  --     {"check": "property_exists_in_db", "passed": true, "details": {"property_id": "abc-123"}},
  --     {"check": "frameworks_provisioned", "passed": true}
  --   ],
  --   "failures": []
  -- }
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_agent_feedback_property ON agent_feedback(property_id);
CREATE INDEX IF NOT EXISTS idx_agent_feedback_agent ON agent_feedback(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_feedback_rating ON agent_feedback(rating);
CREATE INDEX IF NOT EXISTS idx_agent_feedback_created ON agent_feedback(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_feedback_message ON agent_feedback(message_id);

-- RLS policies (multi-tenant support)
ALTER TABLE agent_feedback ENABLE ROW LEVEL SECURITY;

-- Allow users to view their own feedback
CREATE POLICY "Users can view their own feedback" 
  ON agent_feedback FOR SELECT 
  USING (auth.uid()::text = user_id OR user_id IS NULL);

-- Allow users to insert their own feedback
CREATE POLICY "Users can insert their own feedback" 
  ON agent_feedback FOR INSERT 
  WITH CHECK (auth.uid()::text = user_id OR user_id IS NULL);

-- Allow service role to update feedback (for automated evals)
CREATE POLICY "Service role can update feedback" 
  ON agent_feedback FOR UPDATE 
  USING (true);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_agent_feedback_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER agent_feedback_updated_at
  BEFORE UPDATE ON agent_feedback
  FOR EACH ROW
  EXECUTE FUNCTION update_agent_feedback_updated_at();

-- Comments
COMMENT ON TABLE agent_feedback IS 'Stores user feedback and automated evaluations for agent responses';
COMMENT ON COLUMN agent_feedback.rating IS '-1 for thumbs down, 1 for thumbs up';
COMMENT ON COLUMN agent_feedback.tool_eval IS 'Automated evaluation of tool selection accuracy';
COMMENT ON COLUMN agent_feedback.response_eval IS 'LLM-as-Judge evaluation of response quality';
COMMENT ON COLUMN agent_feedback.task_success_eval IS 'Verifier evaluation of task completion in DB';

