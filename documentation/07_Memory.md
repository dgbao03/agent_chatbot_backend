# Memory

## 1. Overview

The system uses three distinct memory types to give the AI persistent awareness — both within a conversation and across conversations.

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                        Memory Types                              │
  │                                                                  │
  │  ┌────────────────────────────────────────────────────────────┐  │
  │  │  Short-term Memory (ChatMemoryBuffer)                      │  │
  │  │  Scope: current conversation, recent messages only         │  │
  │  │  Lifetime: per request (rebuilt from DB each time)         │  │
  │  └────────────────────────────────────────────────────────────┘  │
  │                                                                  │
  │  ┌────────────────────────────────────────────────────────────┐  │
  │  │  Long-term Memory — Conversation Summary                   │  │
  │  │  Scope: current conversation, compressed history           │  │
  │  │  Lifetime: persists until conversation is deleted          │  │
  │  └────────────────────────────────────────────────────────────┘  │
  │                                                                  │
  │  ┌────────────────────────────────────────────────────────────┐  │
  │  │  Long-term Memory — User Facts                             │  │
  │  │  Scope: all conversations of the same user                 │  │
  │  │  Lifetime: until user explicitly deletes a fact            │  │
  │  └────────────────────────────────────────────────────────────┘  │
  └──────────────────────────────────────────────────────────────────┘
```

**Summary comparison:**

| | Short-term | Summary | User Facts |
|-|------------|---------|------------|
| Scope | Current conversation | Current conversation | All conversations (per user) |
| Storage | `messages` table (`is_in_working_memory = TRUE`) | `conversation_summaries` table | `user_facts` table |
| Trigger | Every request | Auto on truncation | User explicit request |
| Token limit | 2000 tokens | No limit | No limit |
| Managed by | ChatMemoryBuffer + DB | `process_memory_truncation()` | User Facts tools |

---

## 2. Short-term Memory — ChatMemoryBuffer

### 2.1. Mechanism

Short-term memory is implemented with LlamaIndex's **`ChatMemoryBuffer`** with a fixed `token_limit=2000`. It holds the most recent messages from the current conversation that fit within the token budget.

Key characteristic: **it is not a persistent object**. Every request recreates the buffer from the database, populates it with the current working memory messages, and discards it at the end of the request.

```
  Start of each request:
         │
         ▼
  load_chat_history(conversation_id)
  ← DB: SELECT * FROM messages
        WHERE conversation_id = X
          AND is_in_working_memory = TRUE
        ORDER BY created_at ASC
         │
         ▼
  memory = ChatMemoryBuffer(token_limit=2000)
  for each message: memory.put(message)
         │
         ▼
  history = memory.get()
  ← returns the SUBSET of messages that fits within 2000 tokens
  ← oldest messages are dropped if total exceeds the limit
         │
         ▼
  history → injected into system prompt
```

### 2.2. Message lifecycle within a request

```
  [Before LLM call]
  Load DB messages (is_in_working_memory=TRUE) → fill ChatMemoryBuffer
         │
         ▼
  memory.get() → inject into system prompt as chat history
         │
         ▼
  [LLM call + tool calls]
         │
         ▼
  [After LLM responds]
  save_message(user_message)      → DB, is_in_working_memory=TRUE
  save_message(assistant_message) → DB, is_in_working_memory=TRUE
         │
         ▼
  memory.put(user_message with message_id)
  memory.put(assistant_message with message_id)
         │
         ▼
  ctx.store.set("chat_history", memory)
         │
         ▼
  process_memory_truncation(ctx, memory)  ← check and handle if truncated
```

### 2.3. Message ID tracking

When messages are put into the buffer, their database ID is stored in `additional_kwargs`:

```python
memory.put(ChatMessage(
    role=MessageRole.USER,
    content=user_input,
    additional_kwargs={"message_id": user_msg_id}
))
```

This ID is later used during summarization to identify which specific database rows to mark as `is_in_working_memory = FALSE`. Without tracking this, the system would not be able to update the correct rows.

### 2.4. Database representation

The `messages` table uses two fields to manage working memory status:

| Column | Type | Meaning |
|--------|------|---------|
| `is_in_working_memory` | `BOOLEAN` | `TRUE` = included in short-term memory, `FALSE` = summarized/archived |
| `summarized_at` | `TIMESTAMPTZ` | Timestamp when the message was moved out of working memory |

All messages are saved with `is_in_working_memory = TRUE` by default. They remain `TRUE` until the summarization process runs.

---

## 3. Long-term Memory — Conversation Summary

### 3.1. Why summary is needed

`ChatMemoryBuffer` can only hold messages within a 2000-token budget. As a conversation grows longer, the oldest messages get pushed out of the buffer and are no longer visible to the LLM. Without any mechanism to preserve this context, the LLM would effectively "forget" everything beyond the token limit.

The conversation summary solves this by **compressing older messages into a compact narrative** that is always appended to the context, regardless of conversation length.

### 3.2. When summarization is triggered

After every successful response (intent `GENERAL` or `PPTX`), the system calls:

```python
await process_memory_truncation(ctx, memory)
```

This function checks whether truncation has occurred. If it has, summarization runs automatically — no manual intervention or scheduled job is needed.

### 3.3. Truncation detection

The system detects whether the buffer has dropped any messages by comparing the **first message** across two views of the buffer:

```python
all_messages      = memory.get_all()   # all messages ever put into buffer
truncated_list    = memory.get()       # messages that fit within token limit

# If first message differs → some messages were dropped
```

Direct content comparison would be expensive for long messages. Instead, a lightweight **MD5 hash** is computed from a fingerprint of the content:

```python
def create_hash(content: str) -> str:
    if len(content) < 40:
        combined = content           # short content: use as-is
    else:
        combined = content[:20] + content[-20:]   # long content: prefix + suffix
    return hashlib.md5(combined.encode('utf-8')).hexdigest()
```

If `hash(all_messages[0]) != hash(truncated_list[0])` → truncation detected.

**Special case — empty truncation:** If `memory.get()` returns an empty list but `memory.get_all()` is not empty, it means every message in the buffer exceeded the token limit. This is flagged as `is_empty_truncated = True` and handled differently in the split algorithm.

### 3.4. Split algorithm — 80/20 rule

When truncation is detected, messages are split into two groups:

```
  All messages in buffer:
  ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐
  │ U │ │ A │ │ U │ │ A │ │ U │ │ A │ │ U │ │ A │ │ U │ │ A │
  └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘
  ◄──────────────── 80% summarize ───────────────►◄── 20% keep ──►
                                                  │
                                                  └─ always starts with a user message
                                                     always aligned to user-assistant pairs
```

**Split rules (`split_messages_for_summary`):**

1. Calculate `target_keep_count = max(2, int(total * 0.2))` — minimum 2 messages (1 pair)
2. Find the last `user` message in all messages — keep boundary must start here or earlier
3. Collect valid user-assistant pairs from the keep boundary to the end
4. If not enough pairs to reach `target_keep_count`, search backward for more pairs
5. `messages_to_summarize` = everything before the keep boundary
6. `messages_to_keep` = the collected pairs from the keep boundary

**Edge case — `is_empty_truncated = True`:**
All messages are sent to summarize, nothing is kept. This handles the scenario where a single message is longer than the entire token budget.

**Minimum guarantee:** The algorithm always keeps at least 1 user-assistant pair (minimum 2 messages), ensuring the LLM always has some immediate context.

### 3.5. Summary generation

After the split, `create_summary()` generates the summary text using a dedicated LLM instance (`llm_summary`).

**First-time summary (no existing summary):**

```
System: SUMMARY_INITIAL_PROMPT
        "Briefly summarize the key points of the conversation.
         Focus on: main topics, important info, conclusions."

User:   "Please summarize the following conversation:
         User: What is the weather in Hanoi?
         Assistant: The weather in Hanoi is 30°C...
         ..."
```

**Incremental update (summary already exists):**

```
System: SUMMARY_UPDATE_PROMPT
        "Create a new summary by combining old summary with new conversation.
         Retain important info from old summary, add new info, no repetition."

User:   "Previous summary:
         The user asked about weather and stocks...

         New conversation:
         User: Remember my name is Bao
         Assistant: Saved: name = Bao
         ...

         Please create a new summary combining both sections."
```

The summary always overwrites the previous one (`ON CONFLICT ... DO UPDATE`) — the table stores exactly 1 cumulative summary per conversation, not a history of summaries.

**Fallback if LLM call fails:**

```python
return (
    f"[SUMMARY] Summarized {user_count} user messages and "
    f"{assistant_count} assistant responses from the previous conversation."
)
```

A minimal count-based summary is returned so the process never leaves the conversation without any summary record.

### 3.6. Database updates after summarization

Two writes happen atomically after a successful summary:

**1. Mark messages as summarized:**

```python
memory_service.summary_repo.mark_messages_as_summarized(message_ids_to_summarize)
```

```sql
UPDATE messages
SET is_in_working_memory = FALSE,
    summarized_at = now()
WHERE id IN (...)
```

Messages are never deleted — they remain in the `messages` table for the frontend to display the full conversation history. They are just excluded from future context loading.

**2. Upsert conversation summary:**

```python
memory_service.summary_repo.upsert_summary(conversation_id, summary_text)
```

```sql
INSERT INTO conversation_summaries (conversation_id, summary_content)
VALUES (...)
ON CONFLICT (conversation_id) DO UPDATE
SET summary_content = excluded.summary_content
```

### 3.7. Memory rebuild

After summarization, a fresh `ChatMemoryBuffer` is created containing only `messages_to_keep`:

```python
new_memory = ChatMemoryBuffer.from_defaults(token_limit=memory.token_limit)
for msg in messages_to_keep:
    new_memory.put(msg)

await ctx.store.set("chat_history", new_memory)
```

This ensures that the next step in the same request (if any) operates with a clean, non-truncated buffer.

---

## 4. Long-term Memory — User Facts

### 4.1. What user facts are

User facts are **explicit key-value pairs** the user has asked the system to remember about themselves. They persist indefinitely across all conversations until the user explicitly removes them.

Examples:
- `name: Bao`
- `city: Hanoi`
- `company: Acme Corp`
- `preferred_language: Vietnamese`

**Critical rule:** The system **never automatically infers or saves** facts from conversation. Facts are only created when the user uses explicit trigger phrases: "Remember that...", "Save that...", "Store...", etc.

### 4.2. Managing facts via tools

User facts are managed entirely through three tools. All three tools access `user_id` and `db` via ContextVar — no parameters need to be passed explicitly.

**`add_user_fact(key, value)`**

```
  User: "Remember that my name is Bao"
         │
         ▼
  add_user_fact(key="name", value="Bao")
         │
         ▼
  upsert_user_fact({ user_id, key="name", value="Bao" })
  ← INSERT if not exists
  ← UPDATE value if key already exists for this user
         │
         ▼
  Returns: "Saved: name = Bao"
```

**`update_user_fact(key, value)`**

```
  User: "Update my name to Do Bao"
         │
         ▼
  update_user_fact(key="name", value="Do Bao")
         │
         ▼
  Check: load_user_facts(user_id) → find_fact_by_key(facts, "name")
         │
    ┌────┴────┐
    │         │
  found    not found
    │         │
    ▼         ▼
  upsert     "No information found for key: name.
  new value   Use add_user_fact to add new."
```

**`delete_user_fact(key)`**

```
  User: "Forget my name"
         │
         ▼
  delete_user_fact(key="name")
         │
         ▼
  Check: load_user_facts(user_id) → find_fact_by_key(facts, "name")
         │
    ┌────┴────┐
    │         │
  found    not found
    │         │
    ▼         ▼
  DELETE     "No information found for key: name"
  WHERE user_id = X AND key = "name"
```

**Case-insensitive key lookup:** `find_fact_by_key()` normalizes both the search key and stored keys to lowercase before comparing — "Name", "name", and "NAME" all match the same fact.

### 4.3. Database representation

```
  user_facts table:
  ┌──────────┬─────────────────┬──────────┬─────────────┬────────────┬────────────┐
  │ id       │ user_id         │ key      │ value       │ created_at │ updated_at │
  ├──────────┼─────────────────┼──────────┼─────────────┼────────────┼────────────┤
  │ uuid     │ user-uuid       │ name     │ Bao         │ ...        │ ...        │
  │ uuid     │ user-uuid       │ city     │ Hanoi       │ ...        │ ...        │
  │ uuid     │ user-uuid       │ company  │ Acme Corp   │ ...        │ ...        │
  └──────────┴─────────────────┴──────────┴─────────────┴────────────┴────────────┘

  UNIQUE constraint: (user_id, key)  ← same key cannot exist twice for a user
```

### 4.4. How user facts are used in context

At the start of every `route_and_answer` step, user facts are loaded and formatted for injection into the system prompt via `build_chat_context` in `context_service.py`:

```python
user_facts_text = self._get_user_facts_text(user_id)
```

```python
# private method in ContextService (class-based — uses self.user_facts_repo internally)
def _get_user_facts_text(self, user_id: str) -> str:
    facts = self.user_facts_repo.load_user_facts(user_id)
    lines = ["USER FACTS (Information about the user):"]
    for fact in facts:
        lines.append(f"- {fact['key']}: {fact['value']}")
    return "\n".join(lines) if len(lines) > 1 else ""
```

Injected into system prompt:

```
USER FACTS (Information about the user):
- city: Hanoi
- company: Acme Corp
- name: Bao
```

Facts are loaded sorted by `key` (alphabetical order) so the output is deterministic.

If the user has no facts, this section is skipped entirely — no empty block is appended.

---

## 5. Full Message Lifecycle

This diagram shows the complete journey of a message from creation to archival:

```
  User sends message
         │
         ▼
  save_message(role="user", is_in_working_memory=TRUE)
  → DB: messages row, summarized_at=NULL
         │
         ▼
  LLM processes, tools execute
         │
         ▼
  save_message(role="assistant", is_in_working_memory=TRUE)
  → DB: messages row, summarized_at=NULL
         │
         ▼
  memory.put(user_msg), memory.put(assistant_msg)
  → ChatMemoryBuffer now includes these messages
         │
         ▼
  process_memory_truncation()
         │
    ┌────┴─────────────┐
    │                  │
  No truncation    Truncation detected
    │                  │
    ▼                  ▼
  Done           split_messages_for_summary()
                 → messages_to_summarize (80%)
                 → messages_to_keep (20%)
                        │
                        ▼
                 create_summary()
                 → LLM generates summary text
                 → save_summary() (upsert in conversation_summaries)
                        │
                        ▼
                 mark_messages_as_summarized(ids of messages_to_summarize)
                 → UPDATE messages
                    SET is_in_working_memory = FALSE,
                        summarized_at = now()
                    WHERE id IN (...)
                        │
                        ▼
                 Rebuild ChatMemoryBuffer with messages_to_keep only

  ─────────────────────────────────────────────────────────────
  Future requests:
  load_chat_history() returns only is_in_working_memory=TRUE rows
  → summarized messages are no longer loaded into the buffer
  → but they remain in DB, visible to frontend via load_all_messages_for_conversation()
```

---

## 6. Memory and Conversation Boundaries

| Scenario | Short-term | Summary | User Facts |
|----------|-----------|---------|------------|
| New conversation started | Empty — no history | Empty — no summary | Loaded from user account |
| Conversation continues | Grows until token limit | Created/updated on truncation | Unchanged unless tools called |
| User switches to another conversation | Rebuilt from that conversation's DB | Loaded from that conversation's summary | Same user facts (cross-conversation) |
| User deletes a conversation | Messages cascade-deleted | Summary cascade-deleted | Not affected |
| New user account | Empty | Empty | Empty |

**User facts are the only memory that crosses conversation boundaries.** Everything else is scoped strictly to one conversation.