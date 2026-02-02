# Supabase Database Migrations

This directory contains all database migrations for the Agent Chat Application.

## 📋 Applied Migrations

- [x] **001** - 2026-01-15 - All database tables (core + presentations)
- [x] **002** - 2026-02-01 - All RPC functions and triggers
- [x] **003** - 2026-02-01 - Row Level Security policies
- [x] **004** - 2026-02-01 - Update RPC functions (remove SECURITY DEFINER, add ownership validation)
- [ ] **005** - 2026-03-01 - Update conversation_summaries (remove version column, conversation_id as PRIMARY KEY)
- [ ] **006** - 2026-03-01 - Add UPDATE policy for conversation_summaries (required for upsert())
- [ ] **007** - 2026-03-01 - Remove unused next_presentation_id_counter column from conversations

## 📊 Current Schema

### Core Tables
- `conversations` - User chat conversations
- `messages` - Chat messages with memory management
- `user_facts` - User-specific facts extracted from conversations
- `conversation_summaries` - Summarized chat history

### Presentation Tables
- `presentations` - Presentation metadata (current version)
- `presentation_pages` - Current version pages
- `presentation_versions` - Archived versions metadata
- `presentation_version_pages` - Archived version pages

## 🔧 RPC Functions

### Utility Functions
- `check_email_exists(user_email TEXT)` - Check if email exists in auth.users
- `update_updated_at_column()` - Trigger function to auto-update updated_at

### Memory Management
- `mark_messages_as_summarized(conv_id UUID, message_ids UUID[])` - Mark messages as summarized
- `get_working_memory_messages(conv_id UUID)` - Get messages in working memory

### Presentation Management
- `archive_presentation_version(p_id UUID)` - Archive current version before update
- `get_presentation_pages(p_id UUID)` - Get all pages of current version
- `get_version_pages(p_id UUID, v_num INTEGER)` - Get pages of specific version
- `get_presentation_versions(p_id UUID)` - Get all versions metadata
- `get_active_presentation(conv_id UUID)` - Get active presentation for conversation
- `set_active_presentation(conv_id UUID, p_id UUID)` - Set active presentation

## 🔒 Security

All tables have Row Level Security (RLS) enabled. Policies ensure:
- Users can only access their own data
- Conversations, messages, and presentations are isolated by user
- Most RPC functions use RLS (no SECURITY DEFINER)
- Only 2 functions use SECURITY DEFINER:
  - `check_email_exists` - Access auth.users (restricted resource)
  - `archive_presentation_version` - Complex operation with ownership validation

## 📝 How to Apply New Migration

1. Create new migration file: `004_description.sql`
2. Write SQL changes in the file
3. Test locally if possible
4. Copy content → Supabase Dashboard → SQL Editor → Run
5. Update this README:
   ```markdown
   - [x] 004 - YYYY-MM-DD - Description of changes
   ```
6. Commit to Git

## 🚨 Important Notes

- All IDs use UUID (gen_random_uuid())
- Timestamps use TIMESTAMPTZ with NOW() defaults
- Foreign keys have CASCADE or SET NULL deletion policies
- Most RPC functions use RLS (no SECURITY DEFINER) for automatic security
- Only 2 functions use SECURITY DEFINER (with ownership validation where needed)
- Migrations are already applied to production ✅

## 📂 Directory Structure

```
supabase/
├── README.md                     
└── migrations/
    ├── 001_create_tables.sql              # All database tables
    ├── 002_rpc_functions.sql              # All RPC functions & triggers
    ├── 003_rls_policies.sql               # Row Level Security policies
    ├── 004_update_rpc_functions.sql       # Update RPC functions (security improvements)
    ├── 005_update_conversation_summaries.sql # Update conversation_summaries schema
    ├── 006_add_update_policy_summaries.sql # Add UPDATE policy for conversation_summaries
    └── 007_remove_next_presentation_id_counter.sql # Remove unused counter column
```

## 📋 Migration Content Details

### 001_tables.sql
- Core tables: conversations, messages, user_facts, conversation_summaries
- Presentation tables: presentations, presentation_pages, presentation_versions, presentation_version_pages
- All indexes and foreign key constraints

### 002_rpc_functions.sql
- Utility functions (check_email_exists, update_updated_at_column)
- Memory management functions (mark_messages_as_summarized, get_working_memory_messages)
- Presentation management functions (archive, get pages, get versions, active presentation)
- All triggers (auto-update updated_at for conversations, user_facts, presentations)

### 003_rls_policies.sql
- RLS policies for core tables (conversations, messages, summaries, user_facts)
- RLS policies for presentation tables (presentations, pages, versions, version_pages)
- User data isolation and access control

### 004_update_rpc_functions.sql
- Removed SECURITY DEFINER from 7 RPC functions (now use RLS)
- Kept SECURITY DEFINER for 2 functions: check_email_exists, archive_presentation_version
- Added ownership validation to archive_presentation_version
- Security improvement: RLS now automatically protects most functions

### 005_update_conversation_summaries.sql
- Cleanup: Delete old summary versions, keep only latest per conversation
- Remove `version` column (no longer needed)
- Remove `id` column (use conversation_id as PRIMARY KEY instead)
- Set `conversation_id` as PRIMARY KEY (ensures 1 row per conversation)
- Remove UNIQUE constraint on (conversation_id, version)
- Remove index idx_summaries_conv_version
- Result: Only latest summary is stored per conversation

### 006_add_update_policy_summaries.sql
- Add UPDATE policy for conversation_summaries table
- Required for upsert() to work (allows updating existing rows)
- Policy checks ownership via conversations table (same pattern as INSERT/SELECT)
- Fixes 403 Forbidden error when updating summaries

### 007_remove_next_presentation_id_counter.sql
- Remove unused `next_presentation_id_counter` column from conversations table
- Legacy field from JSON storage era when presentations used counter-based IDs (slide_001, slide_002)
- Current implementation uses UUID for presentation IDs, so counter is no longer needed
- Cleanup: Removes unused database column
