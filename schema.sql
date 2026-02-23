-- ============================================================
-- EXTENSIONS
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ============================================================
-- TABLE: users
-- ============================================================

CREATE TABLE public.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email varchar(255) NOT NULL UNIQUE,
    hashed_password varchar(255),
    name varchar(255),
    avatar_url varchar(500),
    provider_user_id varchar(255),
    email_verified boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    providers text[] NOT NULL DEFAULT ARRAY['email']
);

CREATE UNIQUE INDEX idx_users_email ON public.users(email);


-- ============================================================
-- TABLE: conversations
-- ============================================================

CREATE TABLE public.conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    title text,
    active_presentation_id uuid,
    next_presentation_id_counter integer DEFAULT 1,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX idx_conversations_user_id ON public.conversations(user_id);
CREATE INDEX idx_conversations_active_presentation ON public.conversations(active_presentation_id);
CREATE INDEX idx_conversations_created_at ON public.conversations(created_at DESC);


-- ============================================================
-- TABLE: conversation_summaries
-- ============================================================

CREATE TABLE public.conversation_summaries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL UNIQUE,
    summary_content text NOT NULL,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_summaries_conversation_id ON public.conversation_summaries(conversation_id);


-- ============================================================
-- TABLE: messages
-- ============================================================

CREATE TABLE public.messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL,
    role text NOT NULL,
    content text NOT NULL,
    intent text,
    is_in_working_memory boolean DEFAULT true,
    summarized_at timestamptz,
    metadata jsonb,
    created_at timestamptz DEFAULT now(),

    CONSTRAINT messages_role_check
        CHECK (role IN ('user', 'assistant', 'system')),

    CONSTRAINT messages_intent_check
        CHECK (intent IN ('PPTX', 'GENERAL') OR intent IS NULL)
);

CREATE INDEX idx_messages_conversation_id
    ON public.messages(conversation_id);

CREATE INDEX idx_messages_working_memory
    ON public.messages(conversation_id, is_in_working_memory, created_at)
    WHERE is_in_working_memory = true;


-- ============================================================
-- TABLE: presentations
-- ============================================================

CREATE TABLE public.presentations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL,
    topic text NOT NULL,
    total_pages integer NOT NULL,
    version integer DEFAULT 1,
    metadata jsonb,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX idx_presentations_conversation_id
    ON public.presentations(conversation_id);

CREATE INDEX idx_presentations_created_at
    ON public.presentations(created_at DESC);


-- ============================================================
-- TABLE: presentation_pages
-- ============================================================

CREATE TABLE public.presentation_pages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    presentation_id uuid NOT NULL,
    page_number integer NOT NULL,
    html_content text NOT NULL,
    page_title text,
    created_at timestamptz DEFAULT now(),

    CONSTRAINT presentation_pages_presentation_id_page_number_key
        UNIQUE (presentation_id, page_number)
);

CREATE INDEX idx_presentation_pages_presentation_id
    ON public.presentation_pages(presentation_id);

CREATE INDEX idx_presentation_pages_number
    ON public.presentation_pages(presentation_id, page_number);


-- ============================================================
-- TABLE: presentation_versions
-- ============================================================

CREATE TABLE public.presentation_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    presentation_id uuid NOT NULL,
    version integer NOT NULL,
    total_pages integer NOT NULL,
    user_request text,
    created_at timestamptz DEFAULT now(),

    CONSTRAINT presentation_versions_presentation_id_version_key
        UNIQUE (presentation_id, version)
);

CREATE INDEX idx_presentation_versions_presentation_id
    ON public.presentation_versions(presentation_id);

CREATE INDEX idx_presentation_versions_combo
    ON public.presentation_versions(presentation_id, version);


-- ============================================================
-- TABLE: presentation_version_pages
-- ============================================================

CREATE TABLE public.presentation_version_pages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id uuid NOT NULL,
    page_number integer NOT NULL,
    html_content text NOT NULL,
    page_title text,

    CONSTRAINT presentation_version_pages_version_id_page_number_key
        UNIQUE (version_id, page_number)
);

CREATE INDEX idx_version_pages_version_id
    ON public.presentation_version_pages(version_id);

CREATE INDEX idx_version_pages_number
    ON public.presentation_version_pages(version_id, page_number);


-- ============================================================
-- TABLE: password_reset_tokens
-- ============================================================

CREATE TABLE public.password_reset_tokens (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    token varchar(64) NOT NULL UNIQUE,
    user_id uuid NOT NULL,
    expires_at timestamptz NOT NULL,
    used_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_used_before_expiry
        CHECK (used_at IS NULL OR used_at <= expires_at)
);

CREATE UNIQUE INDEX idx_password_reset_tokens_token
    ON public.password_reset_tokens(token);

CREATE INDEX idx_password_reset_tokens_user_id
    ON public.password_reset_tokens(user_id);

CREATE INDEX idx_password_reset_tokens_expires_at
    ON public.password_reset_tokens(expires_at);


-- ============================================================
-- TABLE: token_blacklist
-- ============================================================

CREATE TABLE public.token_blacklist (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    token_jti varchar(255) NOT NULL UNIQUE,
    user_id uuid NOT NULL,
    token_type varchar(20) NOT NULL,
    expires_at timestamptz NOT NULL,
    blacklisted_at timestamptz DEFAULT now()
);

CREATE INDEX idx_token_blacklist_user_id
    ON public.token_blacklist(user_id);

CREATE INDEX idx_token_blacklist_jti
    ON public.token_blacklist(token_jti);

CREATE INDEX idx_token_blacklist_expires_at
    ON public.token_blacklist(expires_at);


-- ============================================================
-- TABLE: user_facts
-- ============================================================

CREATE TABLE public.user_facts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    key text NOT NULL,
    value text NOT NULL,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),

    CONSTRAINT user_facts_user_id_key_key
        UNIQUE (user_id, key)
);

CREATE INDEX idx_user_facts_user_id
    ON public.user_facts(user_id);


-- ============================================================
-- FOREIGN KEYS
-- ============================================================

ALTER TABLE public.conversations
    ADD CONSTRAINT conversations_user_id_fkey
    FOREIGN KEY (user_id)
    REFERENCES public.users(id)
    ON DELETE CASCADE;

ALTER TABLE public.conversations
    ADD CONSTRAINT fk_active_presentation
    FOREIGN KEY (active_presentation_id)
    REFERENCES public.presentations(id)
    ON DELETE SET NULL;

ALTER TABLE public.conversation_summaries
    ADD CONSTRAINT conversation_summaries_conversation_id_fkey
    FOREIGN KEY (conversation_id)
    REFERENCES public.conversations(id)
    ON DELETE CASCADE;

ALTER TABLE public.messages
    ADD CONSTRAINT messages_conversation_id_fkey
    FOREIGN KEY (conversation_id)
    REFERENCES public.conversations(id)
    ON DELETE CASCADE;

ALTER TABLE public.presentations
    ADD CONSTRAINT presentations_conversation_id_fkey
    FOREIGN KEY (conversation_id)
    REFERENCES public.conversations(id)
    ON DELETE CASCADE;

ALTER TABLE public.presentation_pages
    ADD CONSTRAINT presentation_pages_presentation_id_fkey
    FOREIGN KEY (presentation_id)
    REFERENCES public.presentations(id)
    ON DELETE CASCADE;

ALTER TABLE public.presentation_versions
    ADD CONSTRAINT presentation_versions_presentation_id_fkey
    FOREIGN KEY (presentation_id)
    REFERENCES public.presentations(id)
    ON DELETE CASCADE;

ALTER TABLE public.presentation_version_pages
    ADD CONSTRAINT presentation_version_pages_version_id_fkey
    FOREIGN KEY (version_id)
    REFERENCES public.presentation_versions(id)
    ON DELETE CASCADE;

ALTER TABLE public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_user_id_fkey
    FOREIGN KEY (user_id)
    REFERENCES public.users(id)
    ON DELETE CASCADE;

ALTER TABLE public.token_blacklist
    ADD CONSTRAINT token_blacklist_user_id_fkey
    FOREIGN KEY (user_id)
    REFERENCES public.users(id)
    ON DELETE CASCADE;

ALTER TABLE public.user_facts
    ADD CONSTRAINT user_facts_user_id_fkey
    FOREIGN KEY (user_id)
    REFERENCES public.users(id)
    ON DELETE CASCADE;