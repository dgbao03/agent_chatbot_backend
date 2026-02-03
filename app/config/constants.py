"""
Constants - Centralized magic strings and configuration values.
All hardcoded strings should be defined here for maintainability.
"""

# ============================================
# ROLE CONSTANTS
# ============================================
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_SYSTEM = "system"

# ============================================
# INTENT CONSTANTS
# ============================================
INTENT_PPTX = "PPTX"
INTENT_GENERAL = "GENERAL"

# ============================================
# DATABASE FIELD NAMES
# ============================================
# Messages
FIELD_CONVERSATION_ID = "conversation_id"
FIELD_ROLE = "role"
FIELD_CONTENT = "content"
FIELD_INTENT = "intent"
FIELD_IS_IN_WORKING_MEMORY = "is_in_working_memory"
FIELD_SUMMARIZED_AT = "summarized_at"
FIELD_METADATA = "metadata"
FIELD_CREATED_AT = "created_at"
FIELD_ID = "id"

# Conversations
FIELD_TITLE = "title"

# Summaries
FIELD_SUMMARY_CONTENT = "summary_content"

# User Facts
FIELD_USER_ID = "user_id"
FIELD_KEY = "key"
FIELD_VALUE = "value"
FIELD_UPDATED_AT = "updated_at"

# Presentations
FIELD_PRESENTATION_ID = "presentation_id"
FIELD_TOPIC = "topic"
FIELD_TOTAL_PAGES = "total_pages"
FIELD_VERSION = "version"
FIELD_PAGE_NUMBER = "page_number"
FIELD_HTML_CONTENT = "html_content"
FIELD_PAGE_TITLE = "page_title"
FIELD_ACTIVE_PRESENTATION_ID = "active_presentation_id"

# ============================================
# METADATA KEYS (for message.metadata JSONB)
# ============================================
METADATA_KEY_PAGES = "pages"
METADATA_KEY_TOTAL_PAGES = "total_pages"
METADATA_KEY_TOPIC = "topic"
METADATA_KEY_SLIDE_ID = "slide_id"
METADATA_KEY_USER_REQUEST = "user_request"

# ============================================
# TABLE NAMES
# ============================================
TABLE_MESSAGES = "messages"
TABLE_CONVERSATIONS = "conversations"
TABLE_CONVERSATION_SUMMARIES = "conversation_summaries"
TABLE_USER_FACTS = "user_facts"
TABLE_PRESENTATIONS = "presentations"
TABLE_PRESENTATION_PAGES = "presentation_pages"
TABLE_PRESENTATION_VERSIONS = "presentation_versions"
TABLE_PRESENTATION_VERSION_PAGES = "presentation_version_pages"

# ============================================
# RPC FUNCTION NAMES
# ============================================
RPC_GET_ACTIVE_PRESENTATION = "get_active_presentation"
RPC_SET_ACTIVE_PRESENTATION = "set_active_presentation"
RPC_GET_PRESENTATION_PAGES = "get_presentation_pages"
RPC_GET_VERSION_PAGES = "get_version_pages"
RPC_GET_PRESENTATION_VERSIONS = "get_presentation_versions"
RPC_ARCHIVE_PRESENTATION_VERSION = "archive_presentation_version"

# RPC Parameter Names
RPC_PARAM_CONV_ID = "conv_id"
RPC_PARAM_P_ID = "p_id"
RPC_PARAM_V_NUM = "v_num"

# ============================================
# DEFAULT VALUES
# ============================================
DEFAULT_IS_IN_WORKING_MEMORY = True
DEFAULT_PRESENTATION_VERSION = 1

