-- Migration: Clean Corrupted Session
-- Date: 2025-12-02
-- Purpose: Delete corrupted session 'web-ui' and its checkpoints to force fresh start
-- 
-- This fixes issues where the agent has accumulated too much context (44+ messages)
-- and is making wrong routing decisions due to corrupted history.

-- Step 1: Delete session data
DELETE FROM sessions WHERE session_id = 'web-ui';

-- Step 2: Delete LangGraph checkpoints for this thread
DELETE FROM checkpoints WHERE thread_id = 'web-ui';
DELETE FROM checkpoint_blobs WHERE thread_id = 'web-ui';
DELETE FROM checkpoint_writes WHERE thread_id = 'web-ui';

-- Verification
SELECT 
    'Sessions cleaned' as action,
    (SELECT COUNT(*) FROM sessions WHERE session_id = 'web-ui') as remaining_sessions,
    (SELECT COUNT(*) FROM checkpoints WHERE thread_id = 'web-ui') as remaining_checkpoints;

