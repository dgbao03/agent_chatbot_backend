-- ============================================
-- Migration: 004_update_rpc_functions
-- Date: 2026-02-01
-- Description: Update RPC functions - Remove SECURITY DEFINER from most functions, add ownership validation
-- ============================================

-- ============================================
-- DROP EXISTING FUNCTIONS AND TRIGGERS
-- ============================================

-- Drop Triggers first (before functions)
DROP TRIGGER IF EXISTS conversations_updated_at ON conversations;
DROP TRIGGER IF EXISTS user_facts_updated_at ON user_facts;
DROP TRIGGER IF EXISTS presentations_updated_at ON presentations;

-- Drop Functions
DROP FUNCTION IF EXISTS check_email_exists(TEXT);
DROP FUNCTION IF EXISTS update_updated_at_column();
DROP FUNCTION IF EXISTS mark_messages_as_summarized(UUID, UUID[]);
DROP FUNCTION IF EXISTS get_working_memory_messages(UUID);
DROP FUNCTION IF EXISTS archive_presentation_version(UUID);
DROP FUNCTION IF EXISTS get_presentation_pages(UUID);
DROP FUNCTION IF EXISTS get_version_pages(UUID, INTEGER);
DROP FUNCTION IF EXISTS get_presentation_versions(UUID);
DROP FUNCTION IF EXISTS get_active_presentation(UUID);
DROP FUNCTION IF EXISTS set_active_presentation(UUID, UUID);

-- Drop old function signature if exists
DROP FUNCTION IF EXISTS get_working_memory_messages(TEXT);

-- ============================================
-- UTILITY FUNCTIONS
-- ============================================

/* Check Email Existing */
CREATE OR REPLACE FUNCTION check_email_exists(user_email TEXT)
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM auth.users 
    WHERE email = user_email
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

/* Auto Update updated_at */
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- TRIGGERS FOR AUTO-UPDATE
-- ============================================

-- Trigger for conversations
CREATE TRIGGER conversations_updated_at
  BEFORE UPDATE ON conversations
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- Trigger for user_facts
CREATE TRIGGER user_facts_updated_at
  BEFORE UPDATE ON user_facts
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- Trigger for presentations
CREATE TRIGGER presentations_updated_at
  BEFORE UPDATE ON presentations
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- MEMORY MANAGEMENT FUNCTIONS
-- ============================================

/* Mark Messages as Summarized */
CREATE OR REPLACE FUNCTION mark_messages_as_summarized(
  conv_id UUID,
  message_ids UUID[]
)
RETURNS void AS $$
BEGIN
  UPDATE messages
  SET is_in_working_memory = false,
      summarized_at = NOW()
  WHERE conversation_id = conv_id
    AND id = ANY(message_ids);
END;
$$ LANGUAGE plpgsql;

/* Get Working Memory Messages */
CREATE OR REPLACE FUNCTION get_working_memory_messages(conv_id UUID)
RETURNS TABLE (
  id UUID,
  role TEXT,
  content TEXT,
  intent TEXT,
  created_at TIMESTAMPTZ
) AS $$
BEGIN
  RETURN QUERY
  SELECT m.id, m.role, m.content, m.intent, m.created_at
  FROM messages m
  WHERE m.conversation_id = conv_id
    AND m.is_in_working_memory = true
  ORDER BY m.created_at ASC;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- PRESENTATION MANAGEMENT FUNCTIONS
-- ============================================

/* Archive current version before update */
CREATE OR REPLACE FUNCTION archive_presentation_version(p_id UUID)
RETURNS UUID AS $$
DECLARE
  v_version_id UUID;
  v_current_version INTEGER;
  v_user_request TEXT;
BEGIN
  -- ✅ Validate ownership: User can only archive their own presentations
  IF NOT EXISTS (
    SELECT 1 
    FROM presentations p
    JOIN conversations c ON c.id = p.conversation_id
    WHERE p.id = p_id 
      AND c.user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'Access denied: You can only archive your own presentations'
      USING ERRCODE = 'P0001';
  END IF;
  
  -- Get current version and metadata
  SELECT version, metadata->>'user_request' 
  INTO v_current_version, v_user_request
  FROM presentations
  WHERE id = p_id;
  
  -- Create version record
  INSERT INTO presentation_versions (presentation_id, version, total_pages, user_request)
  SELECT id, version, total_pages, metadata->>'user_request'
  FROM presentations
  WHERE id = p_id
  RETURNING id INTO v_version_id;
  
  -- Copy current pages to version_pages
  INSERT INTO presentation_version_pages (version_id, page_number, html_content, page_title)
  SELECT v_version_id, page_number, html_content, page_title
  FROM presentation_pages
  WHERE presentation_id = p_id
  ORDER BY page_number;
  
  RETURN v_version_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

/* Get all pages of current version */
CREATE OR REPLACE FUNCTION get_presentation_pages(p_id UUID)
RETURNS TABLE (
  page_number INTEGER,
  html_content TEXT,
  page_title TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT pp.page_number, pp.html_content, pp.page_title
  FROM presentation_pages pp
  WHERE pp.presentation_id = p_id
  ORDER BY pp.page_number;
END;
$$ LANGUAGE plpgsql;

/* Get pages of specific version */
CREATE OR REPLACE FUNCTION get_version_pages(p_id UUID, v_num INTEGER)
RETURNS TABLE (
  page_number INTEGER,
  html_content TEXT,
  page_title TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT pvp.page_number, pvp.html_content, pvp.page_title
  FROM presentation_version_pages pvp
  JOIN presentation_versions pv ON pv.id = pvp.version_id
  WHERE pv.presentation_id = p_id
    AND pv.version = v_num
  ORDER BY pvp.page_number;
END;
$$ LANGUAGE plpgsql;

/* Get all versions metadata */
CREATE OR REPLACE FUNCTION get_presentation_versions(p_id UUID)
RETURNS TABLE (
  version INTEGER,
  total_pages INTEGER,
  user_request TEXT,
  created_at TIMESTAMPTZ,
  is_current BOOLEAN
) AS $$
DECLARE
  v_current_version INTEGER;
BEGIN
  -- Get current version
  SELECT presentations.version INTO v_current_version
  FROM presentations
  WHERE presentations.id = p_id;
  
  -- Return all versions from history
  RETURN QUERY
  SELECT 
    pv.version,
    pv.total_pages,
    pv.user_request,
    pv.created_at,
    FALSE as is_current
  FROM presentation_versions pv
  WHERE pv.presentation_id = p_id
  ORDER BY pv.version;
  
  -- Append current version
  RETURN QUERY
  SELECT 
    p.version,
    p.total_pages,
    p.metadata->>'user_request' as user_request,
    p.updated_at as created_at,
    TRUE as is_current
  FROM presentations p
  WHERE p.id = p_id;
END;
$$ LANGUAGE plpgsql;

/* Get active presentation for conversation */
CREATE OR REPLACE FUNCTION get_active_presentation(conv_id UUID)
RETURNS UUID AS $$
DECLARE
  v_presentation_id UUID;
BEGIN
  SELECT active_presentation_id INTO v_presentation_id
  FROM conversations
  WHERE id = conv_id;
  
  RETURN v_presentation_id;
END;
$$ LANGUAGE plpgsql;

/* Set active presentation */
CREATE OR REPLACE FUNCTION set_active_presentation(conv_id UUID, p_id UUID)
RETURNS VOID AS $$
BEGIN
  UPDATE conversations
  SET active_presentation_id = p_id
  WHERE id = conv_id;
END;
$$ LANGUAGE plpgsql;

