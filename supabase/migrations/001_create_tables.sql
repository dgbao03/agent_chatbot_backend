-- ============================================
-- Migration: 001_tables
-- Date: 2026-01-15
-- Description: All database tables (conversations, messages, user_facts, summaries, presentations)
-- ============================================

-- ============================================
-- CORE TABLES
-- ============================================

-- CONVERSATIONS
CREATE TABLE conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  title TEXT,
  
  -- Slide management
  active_presentation_id UUID NULL,
  next_presentation_id_counter INTEGER DEFAULT 1,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_created_at ON conversations(created_at DESC);

-- MESSAGES
CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content TEXT NOT NULL,
  intent TEXT NULL CHECK (intent IN ('PPTX', 'GENERAL') OR intent IS NULL),
  
  -- Memory Management
  is_in_working_memory BOOLEAN DEFAULT true,
  summarized_at TIMESTAMPTZ NULL,
  
  metadata JSONB NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_working_memory ON messages(conversation_id, is_in_working_memory, created_at)
  WHERE is_in_working_memory = true;

-- CONVERSATION SUMMARIES
CREATE TABLE conversation_summaries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  summary_content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(conversation_id, version)
);

CREATE INDEX idx_summaries_conversation_id ON conversation_summaries(conversation_id);
CREATE INDEX idx_summaries_conv_version ON conversation_summaries(conversation_id, version);

-- USER FACTS
CREATE TABLE user_facts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(user_id, key)
);

CREATE INDEX idx_user_facts_user_id ON user_facts(user_id);

-- ============================================
-- PRESENTATION TABLES
-- ============================================

-- PRESENTATIONS TABLE (CURRENT VERSION)
CREATE TABLE presentations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  topic TEXT NOT NULL,
  total_pages INTEGER NOT NULL,
  version INTEGER DEFAULT 1,
  metadata JSONB NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_presentations_conversation_id ON presentations(conversation_id);
CREATE INDEX idx_presentations_created_at ON presentations(created_at DESC);

-- PRESENTATION PAGES (CURRENT VERSION)
CREATE TABLE presentation_pages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  presentation_id UUID NOT NULL REFERENCES presentations(id) ON DELETE CASCADE,
  page_number INTEGER NOT NULL,
  html_content TEXT NOT NULL,
  page_title TEXT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(presentation_id, page_number)
);

CREATE INDEX idx_presentation_pages_presentation_id ON presentation_pages(presentation_id);
CREATE INDEX idx_presentation_pages_number ON presentation_pages(presentation_id, page_number);

-- PRESENTATION VERSIONS (ARCHIVED)
CREATE TABLE presentation_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  presentation_id UUID NOT NULL REFERENCES presentations(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  total_pages INTEGER NOT NULL,
  user_request TEXT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(presentation_id, version)
);

CREATE INDEX idx_presentation_versions_presentation_id ON presentation_versions(presentation_id);
CREATE INDEX idx_presentation_versions_combo ON presentation_versions(presentation_id, version);

-- PRESENTATION VERSION PAGES (ARCHIVED)
CREATE TABLE presentation_version_pages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  version_id UUID NOT NULL REFERENCES presentation_versions(id) ON DELETE CASCADE,
  page_number INTEGER NOT NULL,
  html_content TEXT NOT NULL,
  page_title TEXT NULL,
  UNIQUE(version_id, page_number)
);

CREATE INDEX idx_version_pages_version_id ON presentation_version_pages(version_id);
CREATE INDEX idx_version_pages_number ON presentation_version_pages(version_id, page_number);

-- ============================================
-- UPDATE CONVERSATIONS TABLE (ADD FOREIGN KEY)
-- ============================================
ALTER TABLE conversations
  ADD CONSTRAINT fk_active_presentation 
  FOREIGN KEY (active_presentation_id) 
  REFERENCES presentations(id) ON DELETE SET NULL;

CREATE INDEX idx_conversations_active_presentation ON conversations(active_presentation_id);

