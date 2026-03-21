# Conversation

## 1. Overview

A **Conversation** is the primary container in the system. Every user message, AI response, memory summary, and slide presentation belongs to a conversation.

```
  Conversation
  ├── Messages        (user + assistant turns)
  ├── Summary         (compressed memory of older messages)
  └── Presentations   (HTML slides generated in this conversation)
```

**Conversation fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key, auto-generated |
| `user_id` | UUID | Owner — FK to `users` table |
| `title` | VARCHAR | Auto-generated from first message, can be renamed by user |
| `active_presentation_id` | UUID (nullable) | FK to the most recently used presentation |
| `created_at` | TIMESTAMPTZ | When the conversation was started |
| `updated_at` | TIMESTAMPTZ | Last activity timestamp — used to sort sidebar |

---

## 2. Conversation Lifecycle

```
  User sends first message (conversation_id = null)
         │
         ▼
  Workflow creates conversation (title = null)
  → generate_conversation_title(user_input)
  → update conversation title
         │
         ▼
  Chat continues across multiple turns
  → messages accumulate
  → memory summarized when token limit reached
  → presentations created/updated if slide intent detected
  → active_presentation_id updated on each slide change
         │
         ▼
  User deletes conversation
  → cascade deletes all associated data
```

### 2.1. Creation

Conversations are **created automatically by the workflow** — there is no explicit "create conversation" API. When the frontend sends a message without a `conversation_id`, the workflow creates one mid-execution:

```
  POST /workflows/chat/run
  { start_event: { user_input: "...", conversation_id: null } }
         │
         ▼
  self.conversation_service.get_or_create_conversation(user_id, None, user_input)
  → conversation_repo.create_new_conversation(user_id)
    → INSERT INTO conversations (user_id, title=null)
    → returns conversation_id
         │
         ▼
  generate_conversation_title(user_input)
  → returns title string (max 60 chars, no LLM)
         │
         ▼
  conversation_repo.update_conversation_title(conversation_id, title, user_id)
         │
         ▼
  Workflow result includes:
  { "conversation_id": "...", "title": "...", "intent": ..., "answer": ... }
  ← Frontend uses these to add the new conversation to the sidebar
```

### 2.2. During chat

Each request with a `conversation_id` adds to the existing conversation:
- New messages are appended to the `messages` table
- `updated_at` is updated automatically via SQLAlchemy `onupdate`
- If a slide is generated or edited, `active_presentation_id` is updated to that presentation

### 2.3. Deletion

Deleting a conversation triggers a cascade that removes all associated data:

```
  DELETE conversation
         │
         ▼
  ┌──────────────────────────────────────────────┐
  │  Cascaded deletions (DB ON DELETE CASCADE):  │
  │                                              │
  │  messages                                    │
  │  conversation_summaries                      │
  │  presentations                               │
  │    └── presentation_pages                   │
  │    └── presentation_versions                │
  │          └── presentation_version_pages     │
  └──────────────────────────────────────────────┘
```

No manual cleanup is needed — the database foreign key constraints handle everything.

---

## 3. Title Generation

Conversation titles are generated **without any LLM call** — using a pure Python N-gram and pattern-matching approach. This keeps title generation fast and free of API cost.

```
                user_input (first message)
                         │
                         ▼
  ┌─────────────────────────────────────────────────┐
  │  Step 1: Short input?                           │
  │  len(user_input) <= 60 chars                    │
  │  → YES: return user_input as-is                 │
  └──────────────────────┬──────────────────────────┘
                         │ NO
                         ▼
  ┌─────────────────────────────────────────────────┐
  │  Step 2: Pattern matching                       │
  │  Find phrases matching patterns:                │
  │  - "about/for/on/regarding [phrase]"            │
  │  - "create/make/build [a/an] [phrase]"          │
  │  - "presentation/report about [phrase]"         │
  │  Also: find 2-3 word technical phrases          │
  │  (consecutive non-stop-words)                   │
  │  → FOUND: format_title(phrase) and return       │
  └──────────────────────┬──────────────────────────┘
                         │ NOT FOUND
                         ▼
  ┌─────────────────────────────────────────────────┐
  │  Step 3: Keyword extraction                     │
  │  Find longest non-stop-word (> 3 chars)         │
  │  → FOUND: format_title(keyword) and return      │
  └──────────────────────┬──────────────────────────┘
                         │ NOT FOUND
                         ▼
  ┌─────────────────────────────────────────────────┐
  │  Step 4: Smart truncate (fallback)              │
  │  Cut at punctuation or word boundary            │
  │  Max 60 chars, append "..." if truncated        │
  └─────────────────────────────────────────────────┘
```

**`format_title()`** — applied to extracted phrases before returning:
- Capitalizes each word (`"machine learning"` → `"Machine Learning"`)
- Removes trailing punctuation (`"AI basics."` → `"AI Basics"`)

**Workflow fallback:** If `generate_conversation_title()` throws any exception, the workflow catches it and uses a simple truncation: `user_input[:60].strip() + "..."`.

---

## 4. Access Control

### 4.1. API layer

All conversation endpoints require a valid JWT token. `user_id` is extracted from the token by `get_current_user` dependency and passed explicitly to every repository function.

Repository functions always filter by `user_id`:

```python
self.db.query(Conversation).filter(
    Conversation.id == conversation_id,
    Conversation.user_id == user_id    ← ownership enforced here
).first()
```

If the conversation does not exist or belongs to a different user, the query returns `None` — the repository returns `None`/`False`/`[]`, and the router raises `HTTP 404`. **No information about other users' conversations is ever leaked.**

### 4.2. Workflow layer

When the frontend sends a request with an existing `conversation_id`, the workflow validates ownership via `ConversationService`:

```python
# Inside a workflow step — service is injected via ChatWorkflow.__init__
self.conversation_service.validate_conversation_access(user_id, conversation_id)

# Inside ConversationService (no db parameter — uses self.conversation_repo internally)
def validate_conversation_access(self, user_id: str, conversation_id: str) -> None:
    conversation = self.conversation_repo.get_conversation_by_id(conversation_id, user_id)
    if not conversation:
        raise NotFoundError("Conversation", conversation_id)
```

**Double check — two code paths:**

```
  POST /workflows/chat/run
         │
         ▼
  security_check step
  ├── [EXPLOIT detected]
  │   └── validate_conversation_access()  ← check 1
  │       → save rejection message to correct conversation
  │
  └── [SAFE]
      └── route_and_answer step
          └── validate_conversation_access()  ← check 2
              → proceed with normal flow
```

The check runs in both paths because the EXPLOIT path also needs to save the rejection message — it must validate ownership before writing to the conversation.

---

## 5. Frontend Usage Flow

### 5.1. Load sidebar on page open

```
  User opens the app
         │
         ▼
  GET /conversations
  ← returns all conversations, ordered by updated_at desc
  ← fields: id, title, active_presentation_id, created_at, updated_at
         │
         ▼
  FE renders conversation list in sidebar
```

### 5.2. Open an existing conversation

```
  User clicks a conversation in sidebar
         │
         ▼
  GET /conversations/{id}/messages
  ← returns ALL messages (including summarized ones)
  ← each message: { id, role, content, intent, metadata, created_at }
         │
         ▼
  FE renders full chat history

         │ (in parallel)
         ▼
  GET /conversations/{id}/active-presentation
  ← returns { presentation_id: "..." | null }
         │
    ┌────┴────┐
    │         │
  has id     null
    │         │
    ▼         ▼
  Load slide  No slide panel shown
  for display
```

The `metadata` field of PPTX messages contains `pages` (full HTML) and `slide_id` — the frontend uses these to render the slide viewer inline in chat history.

### 5.3. Send a message to an existing conversation

```
  User types and sends a message
         │
         ▼
  POST /workflows/chat/run
  {
    start_event: {
      user_input: "What is the weather in Hanoi?",
      conversation_id: "existing-uuid"
    }
  }
         │
         ▼
  Response:
  {
    status: "completed",
    result: {
      value: {
        result: {
          intent: "GENERAL",
          answer: "The weather in Hanoi is 30°C..."
        }
      }
    }
  }
         │
         ▼
  FE appends assistant message to chat
  FE does NOT need to reload the conversation list (no new conversation created)
```

### 5.4. Start a new conversation

```
  User types the first message (no conversation selected)
         │
         ▼
  POST /workflows/chat/run
  {
    start_event: {
      user_input: "Tell me about machine learning",
      conversation_id: null
    }
  }
         │
         ▼
  Workflow creates conversation internally, returns:
  {
    status: "completed",
    result: {
      value: {
        result: {
          conversation_id: "new-uuid",   ← NEW: add to sidebar
          title: "Machine Learning",     ← NEW: use as sidebar label
          intent: "GENERAL",
          answer: "Machine learning is..."
        }
      }
    }
  }
         │
         ▼
  FE reads conversation_id + title from result
  → Adds new conversation to top of sidebar
  → Sets active conversation to new-uuid
  → Renders assistant message in chat
```

### 5.5. Receive a slide response (intent = PPTX)

```
  User: "Create a presentation about AI"
         │
         ▼
  POST /workflows/chat/run
         │
         ▼
  Response result:
  {
    intent: "PPTX",
    answer: "I've created a 5-page presentation about AI.",
    topic: "Artificial Intelligence Basics",
    slide_id: "presentation-uuid",
    total_pages: 5,
    pages: [
      { page_number: 1, page_title: "Introduction", html_content: "<html>...</html>" },
      { page_number: 2, page_title: "What is AI", html_content: "<html>...</html>" },
      ...
    ]
  }
         │
         ▼
  FE reads intent == "PPTX"
  → Renders answer text in chat bubble
  → Opens slide viewer with pages[].html_content
  → Stores slide_id for future edit requests
```

The slide HTML is embedded directly in the response — no additional API call is needed to render slides.

### 5.6. Rename a conversation

```
  User edits the conversation title in sidebar
         │
         ▼
  PATCH /conversations/{id}
  { "title": "New Title" }
         │
         ▼
  Response: updated ConversationResponse
  FE updates sidebar label
```

### 5.7. Delete a conversation

```
  User clicks delete on a conversation
         │
         ▼
  DELETE /conversations/{id}
  ← 204 No Content on success
  ← 404 if not found or not owned
         │
         ▼
  FE removes conversation from sidebar
  FE clears chat area if deleted conversation was active
```

### 5.8. Check conversation existence

```
  GET /conversations/{id}/exists
  ← { exists: true | false }
```

Used by the frontend to verify that a locally stored `conversation_id` still exists on the server (e.g., after a page refresh or if the conversation was deleted from another session). Unlike `GET /conversations/{id}`, this endpoint always returns 200 — never 404 — making it safe to call without error handling.

---

## 6. API Endpoints

All endpoints are prefixed with `/conversations` and require `Authorization: Bearer <token>`.

| Method | Path | Description | Success | Error |
|--------|------|-------------|---------|-------|
| `GET` | `/conversations` | List all conversations (updated_at desc) | `200` | — |
| `GET` | `/conversations/{id}` | Get one conversation | `200` | `404` |
| `GET` | `/conversations/{id}/exists` | Check existence | `200 { exists: bool }` | — |
| `PATCH` | `/conversations/{id}` | Update title | `200` | `404` |
| `DELETE` | `/conversations/{id}` | Delete + cascade | `204` | `404` |
| `GET` | `/conversations/{id}/messages` | All messages (FE display) | `200` | — |
| `GET` | `/conversations/{id}/active-presentation` | Active presentation ID | `200` | — |

---

## 7. Message Access: Two Query Modes

The system exposes two different ways to query messages from the same `messages` table, serving two different consumers:

```
  messages table
  ┌────────────────────────────────────────────────────────────┐
  │ id │ role │ content │ is_in_working_memory │ summarized_at │
  ├────┼──────┼─────────┼──────────────────────┼───────────────┤
  │ 1  │ user │ Hello   │ FALSE                │ 2024-01-10    │  ← summarized
  │ 2  │ asst │ Hi!     │ FALSE                │ 2024-01-10    │  ← summarized
  │ 3  │ user │ Weather?│ TRUE                 │ NULL          │  ← working memory
  │ 4  │ asst │ 30°C    │ TRUE                 │ NULL          │  ← working memory
  │ 5  │ user │ Stocks? │ TRUE                 │ NULL          │  ← working memory
  └────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  load_all_messages_for_conversation  load_chat_history
  (GET /messages endpoint)            (Workflow Step 2)
  Returns: ALL rows (1,2,3,4,5)       Returns: rows with TRUE (3,4,5)
  Purpose: FE displays full history   Purpose: LLM context (token-limited)
```

The frontend always shows the full conversation — users can scroll back and read everything, even messages the LLM no longer has in its active memory.

---

## 8. Conversation and Presentation Relationship

A conversation can contain **multiple presentations**, but only one is "active" at any time:

```
  Conversation
  ├── active_presentation_id ──┐
  │                            │
  ├── Presentation A ◄─────────┘  ← currently active
  │   ├── Page 1
  │   ├── Page 2
  │   └── Page 3
  │
  └── Presentation B              ← older, not active
      ├── Page 1
      └── Page 2
```

`active_presentation_id` is updated by `set_active_presentation()` every time a slide is created or edited. When the frontend opens a conversation, it uses `GET /conversations/{id}/active-presentation` to know which slide to display.