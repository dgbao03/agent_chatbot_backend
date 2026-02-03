-- ============================================
-- Migration: 008_check_user_auth_providers
-- Date: 2026-XX-XX
-- Description: Add function to check user auth providers
-- ============================================

/* Check User Auth Providers */
CREATE OR REPLACE FUNCTION check_user_auth_providers(user_email TEXT)
RETURNS JSONB AS $$
DECLARE
  v_providers JSONB;
BEGIN
  SELECT jsonb_agg(DISTINCT provider) INTO v_providers
  FROM auth.identities
  WHERE user_id IN (
    SELECT id FROM auth.users WHERE email = user_email
  );
  
  RETURN COALESCE(v_providers, '[]'::jsonb);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

