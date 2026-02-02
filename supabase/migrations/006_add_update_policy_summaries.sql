-- ============================================
-- Migration: 006_add_update_policy_summaries
-- Date: 2026-03-01
-- Description: Add UPDATE policy for conversation_summaries
-- Reason: upsert() requires UPDATE policy to update existing rows
-- ============================================

-- Add UPDATE policy for conversation_summaries
-- This allows users to update their own summaries when using upsert()
CREATE POLICY "Users can update own summaries"
  ON conversation_summaries FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM conversations
      WHERE conversations.id = conversation_summaries.conversation_id
      AND conversations.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM conversations
      WHERE conversations.id = conversation_summaries.conversation_id
      AND conversations.user_id = auth.uid()
    )
  );

-- ============================================
-- Migration Complete
-- ============================================
-- Result:
-- - Added UPDATE policy for conversation_summaries
-- - Users can now update their own summaries via upsert()
-- - Policy checks ownership via conversations table (same pattern as INSERT/SELECT)
-- ============================================

