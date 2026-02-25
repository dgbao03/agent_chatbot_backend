# Chat Workflow

## 1. Overview

The Chat Workflow is the core processing engine of the system. Every user message sent via the chat API passes through this workflow before a response is returned.

It is built on top of **LlamaIndex Workflow** — a framework for orchestrating multi-step, event-driven async pipelines. Instead of a linear function call chain, each processing stage is an isolated `@step` that communicates with other steps by emitting typed Events.

### Three-step processing pipeline

```
     User Message (POST /workflows/chat/run)
           │
           ▼
  ┌─────────────────┐
  │ security_check  │  Step 1 — Is this an exploit attempt?
  └────────┬────────┘
           │ SAFE
           ▼
  ┌─────────────────────┐
  │  route_and_answer   │  Step 2 — Answer with tools, detect intent
  └────────┬────────────┘
           │ intent == PPTX
           ▼
  ┌─────────────────────┐
  │   generate_slide    │  Step 3 — Generate or edit HTML slide
  └─────────────────────┘
```

If `security_check` detects an exploit, the workflow stops immediately at Step 1 — Step 2 and Step 3 are never reached.

If `route_and_answer` detects `intent == GENERAL`, the workflow stops at Step 2 — Step 3 is skipped.

### LLM instances

The workflow uses **three separate LLM instances**, each for a distinct purpose:

| Instance | Purpose | Note |
|----------|---------|------|
| `llm` | Main chat, tool calling, slide generation | Heavier model |
| `llm_security` | Security classification in Step 1 | Lightweight, fast |
| `llm_summary` | Conversation summarization (memory) | Called outside workflow steps |

---

## 2. Event-Driven Architecture

### How LlamaIndex Workflow works

A LlamaIndex `Workflow` is a class where each method decorated with `@step` is an independent async processing unit. Steps do not call each other directly — instead they communicate through **typed Events**.

```
  Step A                           Step B
  ───────                          ───────
  @step                            @step
  async def step_a(StartEvent)     async def step_b(MyEvent)
      ...                              ...
      return MyEvent(data=...)         return StopEvent(result=...)
         │                                    ▲
         └────────────────────────────────────┘
                    Event routing
```

The workflow runtime inspects the return type of each step and automatically routes the event to the next step that accepts it as input.

### Events in this system

| Event | Emitted by | Consumed by | Payload |
|-------|-----------|-------------|---------|
| `StartEvent` | API router | `security_check` | `user_input`, `conversation_id` |
| `BusinessRouterEvent` | `security_check` | `route_and_answer` | `user_input`, `conversation_id` |
| `GenerateSlideEvent` | `route_and_answer` | `generate_slide` | `user_input`, `new_conversation_id`, `new_conversation_title` |
| `StopEvent` | Any step | Workflow runtime | `result` (dict returned to caller) |

### Shared context store

Steps share data through `ctx.store` (the workflow's in-memory context):

```
  security_check:
    ctx.store.set("db", db)          ← DB session stored for later steps

  route_and_answer:
    ctx.store.set("user_id", ...)
    ctx.store.set("conversation_id", ...)
    ctx.store.set("chat_history", memory)

  generate_slide:
    ctx.store.get("conversation_id")
    ctx.store.get("db")
    ctx.store.get("chat_history")
```

This avoids threading `db` and `user_id` through every function call across steps.

---

## 3. Step 1 — Security Check

### Purpose

Before any business logic runs, every user message is screened by an LLM to detect **prompt injection and system exploitation attempts** — requests that try to manipulate the AI into ignoring its instructions, revealing system prompts, or performing unauthorized actions.

### Processing flow

```
  StartEvent { user_input, conversation_id }
         │
         ▼
  llm_security.achat(SECURITY_CHECK_PROMPT + user_input)
  → structured JSON output: SecurityOutput
         │
    ┌────┴────┐
    │         │
  EXPLOIT    SAFE
    │         │
    ▼         ▼
  Create/validate conversation    BusinessRouterEvent
  Save user message               → continue to Step 2
  Save rejection response
  Return StopEvent (rejection)
```

### EXPLOIT path

When the LLM classifies the message as `EXPLOIT`:

1. If no `conversation_id` provided → create a new conversation and generate its title
2. If `conversation_id` provided → validate ownership (user must own the conversation)
3. Save the user message to DB
4. Save the rejection message to DB (with `metadata.security_classification = "EXPLOIT"`)
5. Return `StopEvent` with the rejection answer — **workflow ends here**

### Fail-safe behavior

If the security LLM call fails for any reason (timeout, API error, parsing error), the step catches the exception and **allows the request to continue** by emitting `BusinessRouterEvent`. The system prefers availability over false positives.

---

## 4. Step 2 — Route and Answer

This is the main processing step. It handles conversation management, context assembly, tool execution, intent detection, and routing.

### 4.1. Conversation management

```
  conversation_id provided?
         │
    ┌────┴────┐
    │         │
   No        Yes
    │         │
    ▼         ▼
  Create new  validate_conversation_access(user_id, conversation_id)
  conversation  ← check user owns this conversation
  Generate title  ← 403 if not owned
```

If a new conversation is created, its `id` and generated `title` are included in the final response — the frontend needs these to update its UI.

### 4.2. Context construction

After conversation is established, the system assembles the full context to send to the LLM. See **06_Context.md** for a detailed breakdown of what goes into the context.

### 4.3. Tool Calling Loop

The LLM is called with the list of available tools via the **OpenAI function calling** protocol. In this mode, the LLM can either call one or more tools, or produce its final text response — and it decides which at each turn.

```
  messages = [system_prompt, user_message]
         │
         ▼
  ┌──────────────────────────────────┐
  │  llm.achat(messages, tools=...)  │ ◄──────────────────┐
  └──────────┬───────────────────────┘                    │
             │                                            │
       ┌─────┴──────┐                                     │
       │            │                                     │
  tool_calls     no tool_calls                            │
  in response    in response                              │
       │            │                                     │
       ▼            ▼                                     │
  Execute each   → LLM is done                           │
  tool call        (final text output)                   │
       │                                                  │
       ▼                                                  │
  Append tool results to messages ─────────────────────►─┘
  (loop continues — LLM is called again with tool results)
```

Key behaviors:
- All tool calls in a single LLM response are executed **in sequence** before calling the LLM again
- If a tool throws an exception, the error string is appended as the tool result — the loop continues regardless
- The loop has **no hard limit** on iterations; it runs until the LLM produces a response with no tool calls

### 4.4. Prompt-enforced JSON output

Unlike Step 1 and Step 3 which use OpenAI's JSON Schema `response_format` to constrain output at the API level, **Step 2 cannot use that mode** — because JSON Schema `response_format` and `tools` are mutually exclusive: when `tools` is active, the API controls output format through the function calling protocol, not through a schema constraint.

Instead, the `ROUTER_ANSWER_PROMPT` instructs the LLM to **always** produce a JSON response as its final output:

```
FINAL RESPONSE RULES (CRITICAL - NO EXCEPTIONS):
MANDATORY: You MUST always return the correct JSON format, NO EXCEPTIONS!
Even if you already know the information, you MUST still return JSON format!
NEVER return plain text, only return JSON!

{
  "intent": "PPTX | GENERAL",
  "answer": "string | null"
}
```

The LLM is responsible for honoring these instructions. After the tool calling loop ends, the raw text of the final LLM message is parsed:

```
  resp.message.content (raw text from LLM)
         │
         ▼
  RouterOutput.model_validate_json(raw_text)
         │
    ┌────┴──────────────┐
    │                   │
  success            parse error
    │                   │
    ▼                   ▼
  output.intent      Log warning
  GENERAL | PPTX     Save generic error message
                     Return StopEvent (error response)
```

### 4.5. Intent routing

| Intent | Meaning | Action |
|--------|---------|--------|
| `GENERAL` | Normal chat answer | Save assistant message → trigger memory management → `StopEvent` |
| `PPTX` | User wants a slide | `answer` is `null` here — Step 3 will generate and save the message → `GenerateSlideEvent` |

---

## 5. Step 3 — Slide Generation

This step is only reached when the LLM in Step 2 detects `intent == PPTX`. It consists of six sequential phases.

### 5.0. Phase overview

```
  GenerateSlideEvent { user_input }
         │
         ▼
  Phase 1: Intent Detection      ← separate LLM call: CREATE_NEW / EDIT_SPECIFIC / EDIT_ACTIVE
         │                                             + target_presentation_id + target_page_number
         ▼
  Phase 2: Load Previous Data    ← load current pages from DB (only if EDIT)
         │
         ▼
  Phase 3: Build Slide Prompt    ← base instructions + chat history + summary + slide HTML (conditional)
         │
         ▼
  Phase 4: LLM Generation        ← JSON Schema response_format → SlideOutput
         │
         ▼
  Phase 5: Page Merging          ← only if editing a single page
         │
         ▼
  Phase 6: Save + Archive        ← CREATE or update with version archiving
         │
         ▼
  Save assistant message + trigger memory management
  Return StopEvent { slide_id, pages, topic, ... }
```

---

### 5.1. Phase 1 — Presentation Intent Detection

Before any generation, a dedicated LLM sub-call classifies what the user wants to do with slides. This call uses JSON Schema `response_format` → `SlideIntentOutput`.

**What the LLM receives:**
- List of all presentations in the current conversation: `id`, `topic`, `total_pages`, which one is marked `(ACTIVE)`
- The user's original request

**Output — three possible actions:**

```
  ┌─────────────────┐   ┌────────────────────────┐   ┌──────────────────────┐
  │   CREATE_NEW    │   │    EDIT_SPECIFIC       │   │     EDIT_ACTIVE      │
  │                 │   │                        │   │                      │
  │ User wants a    │   │ User references a      │   │ User wants to edit   │
  │ brand new       │   │ specific presentation  │   │ but gives no target  │
  │ presentation    │   │ by topic or number     │   │ → use active slide   │
  │                 │   │                        │   │                      │
  │ target_id: null │   │ target_id: matched ID  │   │ target_id: active ID │
  └─────────────────┘   └────────────────────────┘   └──────────────────────┘
```

In addition to the action, the LLM also identifies:
- `target_page_number` — which page to edit (`null` = edit the entire presentation)

**Fallback rule:** If the LLM classifies `EDIT_SPECIFIC` or `EDIT_ACTIVE` but does not provide a `target_slide_id`, the system automatically falls back to the `active_presentation_id` of the current conversation.

---

### 5.2. Phase 2 — Loading Previous Slide Data

Previous slide data is only loaded when `target_presentation_id` is not null (i.e., any EDIT action).

```
  target_presentation_id != null?
         │
    ┌────┴────┐
    │         │
   Yes        No (CREATE_NEW)
    │         │
    ▼         ▼
  load_presentation(target_presentation_id)    previous_pages = None
  → { pages: List[PageContent], total_pages }
```

`load_presentation()` queries the database and returns the **current active version** of the presentation — all pages ordered by `page_number`, each containing:

| Field | Description |
|-------|-------------|
| `page_number` | Page index (starting from 1) |
| `html_content` | Full HTML document for this slide (1280×720px) |
| `page_title` | Human-readable title (e.g., "Introduction", "Conclusion") |

> Note: each `html_content` is a complete HTML document and can be several kilobytes. Loading all pages of a large presentation significantly increases prompt size — this is why the system applies conditional loading in the next phase.

---

### 5.3. Phase 3 — Building the Slide Prompt

The system prompt for slide generation is assembled by appending components in a fixed order:

```
  ┌─────────────────────────────────────────────────┐
  │             Slide System Prompt                  │
  │                                                  │
  │  1. SLIDE_GENERATION_PROMPT                      │  ← design rules, structure,
  │     (always present)                             │    output format requirements
  │                                                  │
  │  2. Recent chat history                          │  ← short-term memory
  │     (if available)                               │    from ChatMemoryBuffer
  │                                                  │
  │  3. Conversation summary                         │  ← long-term memory
  │     (if available)                               │    from summary table
  │                                                  │
  │  4. Previous slide content                       │  ← CONDITIONAL (see below)
  │     (only if EDIT)                               │
  │                                                  │
  │  5. Final action instruction                     │  ← CREATE / EDIT page / EDIT all
  │                                                  │
  └─────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────┐
  │  User Message: "User Request: {user_input}"      │
  └─────────────────────────────────────────────────┘
```

**Conditional slide content loading (component 4):**

The key optimization in Step 3 is that the amount of slide HTML injected into the prompt depends entirely on the edit scope:

```
  previous_pages available?
         │
    ┌────┴────┐
    │         │
   Yes        No → skip (CREATE_NEW)
    │
    ├─── target_page_number != null (single-page edit)
    │         │
    │         ▼
    │    Inject ONLY the target page:
    │    "===== PREVIOUS SLIDE - Page N (TARGET PAGE TO EDIT) ====="
    │    Page Title: ...
    │    HTML Content: <only this page's full HTML>
    │    + "Edit ONLY Page N. Output should contain ONLY this page."
    │    + "Backend will merge this with other unchanged pages."
    │         │
    │    [If page_number not found → reset target_page_number to null → fall through]
    │
    └─── target_page_number == null (full presentation edit)
              │
              ▼
         Inject ALL pages:
         "===== PREVIOUS SLIDE - All N Pages (for reference) ====="
         Page 1: <title> + <full HTML>
         Page 2: <title> + <full HTML>
         ...
         + "Return complete new presentation (all pages)."
         + "Maintain consistent design across all pages."
```

The single-page mode intentionally hides the HTML of all other pages from the LLM — this reduces token usage significantly while still giving the LLM enough context through chat history and summary to maintain design consistency.

---

### 5.4. Phase 4 — LLM Generation

The slide generation call uses **JSON Schema `response_format`** (unlike Step 2 which uses prompt-only enforcement) because this step does not use tool calling — `response_format` and `tools` cannot be used simultaneously.

```python
resp = await llm.achat(slide_messages, response_format={
    "type": "json_schema",
    "json_schema": {
        "name": "SlideOutput",
        "schema": SlideOutput.model_json_schema(),
    }
})
slide_output = SlideOutput.model_validate_json(resp.message.content)
```

**`SlideOutput` structure:**

| Field | Type | Description |
|-------|------|-------------|
| `intent` | `"PPTX"` | Always PPTX, used by frontend to identify slide responses |
| `answer` | `str` | Human-readable message shown in chat (e.g., "I've created a slide about AI") |
| `topic` | `str` | Presentation title (e.g., "Artificial Intelligence Basics") |
| `total_pages` | `int` | Number of pages |
| `pages` | `List[PageContent]` | List of pages with `page_number`, `html_content`, `page_title` |

**Expected pages in LLM output by scope:**

| Scope | LLM is instructed to return |
|-------|-----------------------------|
| `CREATE_NEW` | All pages (3–7 pages) |
| Full presentation edit | All pages (complete replacement) |
| Single-page edit | Exactly **1 page** (the edited page only) |

---

### 5.5. Phase 5 — Page Merging (single-page edit only)

When `target_page_number` is not null and the LLM returned exactly 1 page, the backend merges the new page back into the full presentation without touching the other pages:

```
  Before merge:
  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
  │ Page 1 │  │ Page 2 │  │ Page 3 │  │ Page 4 │   (old pages from DB)
  └────────┘  └────────┘  └────────┘  └────────┘
                  ▲
                  │ target_page_number = 2
                  │
  LLM output: [ Page 2 (new) ]

  After merge:
  ┌────────┐  ┌──────────────┐  ┌────────┐  ┌────────┐
  │ Page 1 │  │ Page 2 (new) │  │ Page 3 │  │ Page 4 │
  └────────┘  └──────────────┘  └────────┘  └────────┘
  (unchanged)   (replaced)      (unchanged) (unchanged)
```

After merging, `slide_output.pages` is replaced with the merged list and `slide_output.total_pages` is updated to match. The merged result is then passed to the save phase.

---

### 5.6. Phase 6 — Save with Version Archiving

**CREATE_NEW path:**

```
  create_presentation(presentation, pages, user_request)
  ├── Verify conversation belongs to current user
  ├── INSERT into presentations (topic, total_pages, version=1)
  ├── INSERT all pages into presentation_pages
  └── SET conversation.active_presentation_id = new_presentation.id
```

**EDIT path:**

```
  update_presentation(presentation, pages, user_request)
  ├── Verify presentation belongs to current user (via conversation join)
  ├── Archive current version:
  │   ├── INSERT into presentation_versions (version=N, total_pages, user_request)
  │   └── INSERT all current pages into presentation_version_pages
  ├── DELETE all rows in presentation_pages for this presentation_id
  ├── INSERT new pages into presentation_pages
  ├── UPDATE presentations SET version=N+1, topic=..., total_pages=...
  └── (commit)

  set_active_presentation(conversation_id, presentation_id)
  └── UPDATE conversations SET active_presentation_id = presentation_id
```

Every edit automatically archives the previous state — the complete version history is preserved in `presentation_versions` and `presentation_version_pages`.

**Version number after each operation:**

```
  Initial create  → version = 1
  First edit      → version = 2  (version 1 archived)
  Second edit     → version = 3  (version 2 archived)
  ...
```

---

### 5.7. Save Assistant Message

After the presentation is saved, the assistant message is written to the `messages` table with `intent = "PPTX"`:

| Field | Value |
|-------|-------|
| `content` | `slide_output.answer` — the human-readable text shown in chat |
| `intent` | `"PPTX"` |
| `metadata.pages` | Full list of pages with HTML (used by frontend to render slides) |
| `metadata.total_pages` | Number of pages |
| `metadata.topic` | Presentation topic |
| `metadata.slide_id` | `presentation_id` — used by frontend to load/reference the presentation |

> Only the `answer` text is added to `ChatMemoryBuffer` — not the HTML content. This prevents slide HTML from bloating the memory and being re-injected into future prompts.

---

## 6. Tool System

### 6.1. Architecture

```
  BaseTool (abstract)
      │
      ├── WeatherTool
      ├── StockTool
      ├── AddUserFactTool
      ├── UpdateUserFactTool
      ├── DeleteUserFactTool
      └── URLExtractorTool
           │
           ▼
      ToolRegistry
      ├── register(tool)
      ├── execute_tool(name, **kwargs)
      ├── get_llama_tools()          → List[FunctionTool] for LLM
      └── get_tool_instructions()   → text injected into system prompt
```

Every tool is a class that extends `BaseTool` and defines:
- `name` — unique identifier used by the LLM to invoke the tool
- `summary` — one-line description injected into the system prompt
- `description` — detailed description used in OpenAI function calling format
- `category` — grouping (`external_api`, `user_data`, `content`)
- `execute(**kwargs)` — the actual implementation

### 6.2. Available tools

| Tool name | Category | Trigger condition | Input | Output |
|-----------|----------|-------------------|-------|--------|
| `get_weather` | `external_api` | User asks about weather | `city: str` | Temperature and weather summary |
| `get_stock_price` | `external_api` | User asks about a stock price | `symbol: str` | Current price and change % |
| `add_user_fact` | `user_data` | User asks to **remember** something | `key: str, value: str` | Confirmation |
| `update_user_fact` | `user_data` | User asks to **update** saved info | `key: str, value: str` | Confirmation |
| `delete_user_fact` | `user_data` | User asks to **forget** saved info | `key: str` | Confirmation |
| `extract_url_content` | `content` | User provides a URL and asks to **read/summarize** it | `url: str` | Article title + text (max 5000 chars) |

### 6.3. How tools reach the LLM

```
  ToolRegistry.get_llama_tools()
  → List[FunctionTool]
  → Each converted to OpenAI tool schema:
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "...",
        "parameters": { ... }
      }
    }
  → Passed to llm.achat(messages, tools=openai_tools)
```

### 6.4. How `user_data` tools access the current user

`user_data` tools (UserFact tools) need the current `user_id` and `db` session to read/write the database. They get these from `ContextVar` (set at the start of the request) — no parameters need to be passed explicitly:

```
  AddUserFactTool.execute(key, value)
    │
    ├── user_id = get_current_user_id()    ← from ContextVar
    └── db = get_current_db_session()      ← from ContextVar
```

---

## 7. Memory (High Level)

The workflow uses a three-layer memory model to give the LLM both immediate context and long-term awareness. See **07_Memory.md** for full implementation details.

| Memory type | Scope | Managed by | Persisted |
|-------------|-------|-----------|-----------|
| Short-term | Current conversation, recent messages | `ChatMemoryBuffer` (token limit 2000) | `messages` table (`is_in_working_memory = TRUE`) |
| Summary | Current conversation, older messages | LLM summarization on truncation | `conversation_summaries` table |
| User Facts | All conversations, per user | `user_data` tools (explicit user request) | `user_facts` table |

---

## 8. Context (High Level)

At the start of `route_and_answer`, the system assembles a **System Prompt** containing all relevant context before calling the LLM. See **06_Context.md** for a detailed breakdown.

```
  ┌─────────────────────────────────────┐
  │            System Prompt            │
  │                                     │
  │  1. Router instructions             │  ← How to behave, output format
  │  2. Available tool list             │  ← Tool names + one-line summaries
  │  3. Tool best practices             │  ← When to use / not use tools
  │  4. User facts                      │  ← Long-term personal memory
  │  5. Recent chat history             │  ← Short-term memory
  │  6. Conversation summary            │  ← Long-term compressed memory
  │                                     │
  └─────────────────────────────────────┘
  ┌─────────────────────────────────────┐
  │           User Message              │
  └─────────────────────────────────────┘
```

The Slide Generation step (Step 3) builds a separate, dedicated system prompt that replaces the router instructions with slide-specific generation instructions and includes the existing slide content for reference when editing.

---

## 9. Structured Output (Pydantic)

The workflow relies on structured JSON output from the LLM at every decision point. Pydantic models define and validate these outputs.

### Models

| Model | Used in | Fields |
|-------|---------|--------|
| `SecurityOutput` | Step 1 | `classification: "SAFE" \| "EXPLOIT"`, `answer: str` |
| `RouterOutput` | Step 2 | `intent: "GENERAL" \| "PPTX"`, `answer: str` |
| `SlideIntentOutput` | Step 3 intent detection | `action`, `target_slide_id`, `target_page_number` |
| `SlideOutput` | Step 3 generation | `topic`, `total_pages`, `pages: List[SlidePage]`, `answer` |

### Why JSON Schema mode

All LLM calls that require structured output use OpenAI's **JSON Schema response format**:

```python
response_format={
    "type": "json_schema",
    "json_schema": {
        "name": "RouterOutput",
        "schema": RouterOutput.model_json_schema(),
    }
}
```

This **constrains the LLM's token generation** to only produce valid JSON matching the schema — eliminating the risk of the LLM adding prose, markdown fences, or extra fields around the JSON output.

### Error handling

If the LLM output cannot be parsed (invalid JSON, missing required fields):

```
  RouterOutput.model_validate_json(raw_text)
         │
    [parse error]
         ▼
  Log warning with raw output length
  save_error_response() → save generic error message to DB
  Return StopEvent with generic error answer
```

The system never crashes on bad LLM output — it always returns a graceful error message to the user.
