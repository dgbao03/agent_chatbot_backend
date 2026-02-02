-- ============================================
-- Migration: 005_update_conversation_summaries
-- Date: 2026-03-01
-- Description: Update conversation_summaries to only store latest version
-- Changes: Remove version column, set conversation_id as PRIMARY KEY
-- ============================================

-- Step 1: Cleanup existing data - Keep only the latest version for each conversation
-- Delete older versions, keeping only the one with the highest version number
DELETE FROM conversation_summaries cs1
WHERE EXISTS (
  SELECT 1 
  FROM conversation_summaries cs2 
  WHERE cs2.conversation_id = cs1.conversation_id 
    AND cs2.version > cs1.version
);

-- Step 2: Drop UNIQUE constraint on (conversation_id, version)
ALTER TABLE conversation_summaries 
  DROP CONSTRAINT IF EXISTS conversation_summaries_conversation_id_version_key;

-- Step 3: Drop index that includes version column
DROP INDEX IF EXISTS idx_summaries_conv_version;

-- Step 4: Drop PRIMARY KEY constraint on id column
ALTER TABLE conversation_summaries 
  DROP CONSTRAINT IF EXISTS conversation_summaries_pkey;

-- Step 5: Drop id column (no longer needed)
ALTER TABLE conversation_summaries 
  DROP COLUMN IF EXISTS id;

-- Step 6: Drop version column
ALTER TABLE conversation_summaries 
  DROP COLUMN IF EXISTS version;

-- Step 7: Set conversation_id as PRIMARY KEY (ensures 1 row per conversation)
ALTER TABLE conversation_summaries 
  ADD CONSTRAINT conversation_summaries_pkey PRIMARY KEY (conversation_id);

-- Step 8: Verify - conversation_id index already exists (idx_summaries_conversation_id)
-- No need to recreate, it's still valid

-- ============================================
-- Migration Complete
-- ============================================
-- Result:
-- - conversation_summaries now has conversation_id as PRIMARY KEY
-- - Only 1 row per conversation (latest summary)
-- - Removed: id, version columns
-- - Removed: UNIQUE(conversation_id, version) constraint
-- - Removed: idx_summaries_conv_version index
-- - Kept: idx_summaries_conversation_id index (still useful for JOINs)
-- ============================================

