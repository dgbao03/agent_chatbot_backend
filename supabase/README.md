# Supabase Database Migrations

This directory contains all database migrations for the Agent Chat Application.

## 📋 Applied Migrations

- [x] **001** - 2026-01-15 - All database tables (core + presentations)
- [x] **002** - 2026-02-01 - All RPC functions and triggers
- [x] **003** - 2026-02-01 - Row Level Security policies
- [x] **004** - 2026-02-01 - Update RPC functions (remove SECURITY DEFINER, add ownership validation)

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
    ├── 001_tables.sql              # All database tables
    ├── 002_rpc_functions.sql       # All RPC functions & triggers
    ├── 003_rls_policies.sql        # Row Level Security policies
    └── 004_update_rpc_functions.sql # Update RPC functions (security improvements)
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
