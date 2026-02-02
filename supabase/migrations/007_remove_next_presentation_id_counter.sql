-- ============================================
-- Migration: 007_remove_next_presentation_id_counter
-- Date: 2026-03-01
-- Description: Remove unused next_presentation_id_counter column from conversations table
-- Reason: Legacy field from JSON storage era, no longer used (presentations now use UUID)
-- ============================================

-- Remove unused column
ALTER TABLE conversations 
  DROP COLUMN IF EXISTS next_presentation_id_counter;

-- ============================================
-- Migration Complete
-- ============================================
-- Result:
-- - Removed next_presentation_id_counter column from conversations table
-- - This field was legacy from JSON storage era when presentations used counter-based IDs (slide_001, slide_002)
-- - Current implementation uses UUID for presentation IDs, so counter is no longer needed
-- ============================================

