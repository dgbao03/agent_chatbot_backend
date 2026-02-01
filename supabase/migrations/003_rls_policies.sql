-- ============================================
-- Migration: 003_rls_policies
-- Date: 2026-02-01
-- Description: Row Level Security policies for all tables
-- ============================================

-- ============================================
-- ENABLE RLS
-- ============================================
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_facts ENABLE ROW LEVEL SECURITY;

-- ============================================
-- RLS POLICIES FOR CONVERSATIONS
-- ============================================
-- Users can view their own conversations
CREATE POLICY "Users can view own conversations"
  ON conversations FOR SELECT
  USING (auth.uid() = user_id);

-- Users can create their own conversations
CREATE POLICY "Users can create own conversations"
  ON conversations FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Users can update their own conversations
CREATE POLICY "Users can update own conversations"
  ON conversations FOR UPDATE
  USING (auth.uid() = user_id);

-- Users can delete their own conversations
CREATE POLICY "Users can delete own conversations"
  ON conversations FOR DELETE
  USING (auth.uid() = user_id);

-- ============================================
-- RLS POLICIES FOR MESSAGES
-- ============================================
-- Users can view messages from their conversations
CREATE POLICY "Users can view own messages"
  ON messages FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM conversations
      WHERE conversations.id = messages.conversation_id
      AND conversations.user_id = auth.uid()
    )
  );

-- Users can insert messages to their conversations
CREATE POLICY "Users can insert own messages"
  ON messages FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM conversations
      WHERE conversations.id = messages.conversation_id
      AND conversations.user_id = auth.uid()
    )
  );

-- Users can update their messages
CREATE POLICY "Users can update own messages"
  ON messages FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM conversations
      WHERE conversations.id = messages.conversation_id
      AND conversations.user_id = auth.uid()
    )
  );

-- Users can delete their messages
CREATE POLICY "Users can delete own messages"
  ON messages FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM conversations
      WHERE conversations.id = messages.conversation_id
      AND conversations.user_id = auth.uid()
    )
  );

-- ============================================
-- RLS POLICIES FOR SUMMARIES
-- ============================================
CREATE POLICY "Users can view own summaries"
  ON conversation_summaries FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM conversations
      WHERE conversations.id = conversation_summaries.conversation_id
      AND conversations.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert own summaries"
  ON conversation_summaries FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM conversations
      WHERE conversations.id = conversation_summaries.conversation_id
      AND conversations.user_id = auth.uid()
    )
  );

-- ============================================
-- RLS POLICIES FOR USER_FACTS
-- ============================================
CREATE POLICY "Users can view own facts"
  ON user_facts FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own facts"
  ON user_facts FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own facts"
  ON user_facts FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own facts"
  ON user_facts FOR DELETE
  USING (auth.uid() = user_id);

-- ============================================
-- ENABLE RLS FOR PRESENTATIONS
-- ============================================
ALTER TABLE presentations ENABLE ROW LEVEL SECURITY;
ALTER TABLE presentation_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE presentation_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE presentation_version_pages ENABLE ROW LEVEL SECURITY;

-- ============================================
-- RLS FOR PRESENTATIONS
-- ============================================
CREATE POLICY "Users can view own presentations"
  ON presentations FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM conversations
      WHERE conversations.id = presentations.conversation_id
      AND conversations.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert own presentations"
  ON presentations FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM conversations
      WHERE conversations.id = presentations.conversation_id
      AND conversations.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can update own presentations"
  ON presentations FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM conversations
      WHERE conversations.id = presentations.conversation_id
      AND conversations.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can delete own presentations"
  ON presentations FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM conversations
      WHERE conversations.id = presentations.conversation_id
      AND conversations.user_id = auth.uid()
    )
  );

-- ============================================
-- RLS FOR PRESENTATION_PAGES
-- ============================================
CREATE POLICY "Users can view own presentation pages"
  ON presentation_pages FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM presentations p
      JOIN conversations c ON c.id = p.conversation_id
      WHERE p.id = presentation_pages.presentation_id
      AND c.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert own presentation pages"
  ON presentation_pages FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM presentations p
      JOIN conversations c ON c.id = p.conversation_id
      WHERE p.id = presentation_pages.presentation_id
      AND c.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can update own presentation pages"
  ON presentation_pages FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM presentations p
      JOIN conversations c ON c.id = p.conversation_id
      WHERE p.id = presentation_pages.presentation_id
      AND c.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can delete own presentation pages"
  ON presentation_pages FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM presentations p
      JOIN conversations c ON c.id = p.conversation_id
      WHERE p.id = presentation_pages.presentation_id
      AND c.user_id = auth.uid()
    )
  );

-- ============================================
-- RLS FOR PRESENTATION_VERSIONS
-- ============================================
CREATE POLICY "Users can view own presentation versions"
  ON presentation_versions FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM presentations p
      JOIN conversations c ON c.id = p.conversation_id
      WHERE p.id = presentation_versions.presentation_id
      AND c.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert own presentation versions"
  ON presentation_versions FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM presentations p
      JOIN conversations c ON c.id = p.conversation_id
      WHERE p.id = presentation_versions.presentation_id
      AND c.user_id = auth.uid()
    )
  );

-- ============================================
-- RLS FOR PRESENTATION_VERSION_PAGES
-- ============================================
CREATE POLICY "Users can view own version pages"
  ON presentation_version_pages FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM presentation_versions pv
      JOIN presentations p ON p.id = pv.presentation_id
      JOIN conversations c ON c.id = p.conversation_id
      WHERE pv.id = presentation_version_pages.version_id
      AND c.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert own version pages"
  ON presentation_version_pages FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM presentation_versions pv
      JOIN presentations p ON p.id = pv.presentation_id
      JOIN conversations c ON c.id = p.conversation_id
      WHERE pv.id = presentation_version_pages.version_id
      AND c.user_id = auth.uid()
    )
  );

