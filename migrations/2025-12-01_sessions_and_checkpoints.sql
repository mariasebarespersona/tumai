-- Migration: Production Deployment - Sessions and Checkpoints
-- Date: 2025-12-01
-- Purpose: Enable persistent session storage and LangGraph checkpoints for Railway deployment

-- ============================================================
-- PART 1: Sessions Table (replaces .sessions.json)
-- ============================================================

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

-- Policy: Service role has full access to sessions
DROP POLICY IF EXISTS "Service role has full access to sessions" ON sessions;
CREATE POLICY "Service role has full access to sessions"
ON sessions FOR ALL
USING (true)
WITH CHECK (true);

-- ============================================================
-- PART 2: LangGraph Checkpoint Tables
-- ============================================================

-- Main checkpoints table
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'utc'),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

-- Checkpoint blobs table
CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT NOT NULL,
    blob BYTEA,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'utc'),
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

-- Checkpoint writes table (updated schema for langgraph-checkpoint-postgres >= 2.0)
CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    blob BYTEA,
    task_path TEXT,  -- Added for langgraph-checkpoint-postgres >= 2.0
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'utc'),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id ON checkpoints(thread_id);
CREATE INDEX IF NOT EXISTS idx_checkpoint_blobs_thread_id ON checkpoint_blobs(thread_id);
CREATE INDEX IF NOT EXISTS idx_checkpoint_writes_thread_id ON checkpoint_writes(thread_id);

-- ============================================================
-- VERIFICATION
-- ============================================================

-- Verify tables were created
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'sessions') THEN
        RAISE NOTICE '✅ sessions table created';
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'checkpoints') THEN
        RAISE NOTICE '✅ checkpoints table created';
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'checkpoint_blobs') THEN
        RAISE NOTICE '✅ checkpoint_blobs table created';
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'checkpoint_writes') THEN
        RAISE NOTICE '✅ checkpoint_writes table created';
    END IF;
END $$;

