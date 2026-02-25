# Tools

## 1. Overview

Tools extend the AI's capabilities beyond pure text generation — they allow the LLM to take actions and retrieve real-time information that it cannot produce from its training data alone.

In this system, tools are only available in **Step 2 (Route and Answer)** of the workflow. The LLM decides autonomously when and which tools to call based on the user's message and the tool descriptions provided.

### Tool categories

| Category | Tools | Purpose |
|----------|-------|---------|
| `external_api` | `get_weather`, `get_stock_price` | Fetch real-time data from external sources |
| `user_data` | `add_user_fact`, `update_user_fact`, `delete_user_fact` | Manage user's long-term personal memory |
| `content` | `extract_url_content` | Read and extract content from web pages |

### All tools at a glance

| Tool name | Category | Trigger condition | Input | Output |
|-----------|----------|-------------------|-------|--------|
| `get_weather` | `external_api` | User asks about weather in a city | `city: str` | Temperature + weather summary |
| `get_stock_price` | `external_api` | User asks about a stock price | `symbol: str` | Current price + change % |
| `add_user_fact` | `user_data` | User asks to **remember** something | `key: str, value: str` | Confirmation message |
| `update_user_fact` | `user_data` | User asks to **change** saved info | `key: str, value: str` | Confirmation message |
| `delete_user_fact` | `user_data` | User asks to **forget** saved info | `key: str` | Confirmation message |
| `extract_url_content` | `content` | User provides a URL and asks to **read/summarize** | `url: str` | Article title + text (max 5000 chars) |

---

## 2. Architecture

### 2.1. BaseTool — Abstract Base Class

All tools inherit from `BaseTool`, which enforces a consistent interface across every tool implementation.

```
  BaseTool (abstract)
  ─────────────────────────────────────────────────────
  Class attributes (REQUIRED — validated at class definition):
    name        : str    ← unique identifier used by LLM to call the tool
    summary     : str    ← one-line description injected into system prompt
    description : str    ← detailed description for OpenAI function calling schema
    category    : str    ← grouping label (external_api / user_data / content)
    enabled     : bool   ← defaults to True, set False to disable without removing

  Abstract method (REQUIRED — must be implemented):
    execute(**kwargs) -> Any

  Provided methods (inherited, no override needed):
    to_llama_tool()  -> FunctionTool   ← converts to LlamaIndex FunctionTool
    get_metadata()   -> dict           ← returns all attributes as dict
```

**Validation at class definition time:** `BaseTool` uses `__init_subclass__` to check that every concrete subclass defines all four required class attributes. If any is missing, Python raises a `TypeError` immediately when the class is defined — not at runtime when the tool is called.

**Two text representations — different purposes:**

| Attribute | Used in | Audience | Detail level |
|-----------|---------|----------|-------------|
| `summary` | System prompt text (`AVAILABLE TOOLS:` section) | LLM reads as part of instructions | One sentence, concise |
| `description` | OpenAI function calling JSON schema (`tools=` parameter) | LLM uses to decide arguments | Multi-sentence with trigger examples and "Do NOT use when" rules |

The `summary` gives the LLM a quick overview of all tools at the top of the system prompt. The `description` is what the LLM reads in detail when it's deciding whether and how to call a specific tool.

### 2.2. ToolRegistry

`ToolRegistry` is a centralized manager for all tools. There is exactly **one global instance** (`registry`) shared across the entire application.

**Key methods:**

```
  registry.register(tool)
  ├── Raises ValueError if tool.name already registered
  └── Stores tool in internal dict keyed by name

  registry.execute_tool(name, **kwargs)
  ├── Tool not found  → return "Error: Tool '{name}' not found"
  ├── Tool disabled   → return "Error: Tool '{name}' is disabled"
  ├── execute() raises → return "Error executing tool '{name}': {str(e)}"
  └── Success         → return execute() result

  registry.get_llama_tools()
  └── Returns List[FunctionTool] for all enabled tools
      ← used by workflow to build the tools= parameter

  registry.get_tool_instructions()
  └── Returns formatted text block injected into system prompt:
      "AVAILABLE TOOLS:
       - get_weather: Get current weather information..."

  registry.get_tools_summary()
  └── Returns stats dict: total, enabled, disabled, categories, tool metadata list
```

**Error handling design of `execute_tool`:** All errors are caught and returned as plain strings. The method **never raises an exception** — it always returns something the LLM can read. This ensures a failing tool never crashes the tool calling loop.

### 2.3. Tool Registration at Module Load

All tools are registered when `app.tools` is first imported — which happens at application startup when the workflow module is loaded.

```
  Application startup
         │
         ▼
  import app.tools          ← triggers app/tools/__init__.py
         │
         ▼
  registry = ToolRegistry()  ← empty registry created
         │
         ▼
  _ALL_TOOLS = [             ← all tools instantiated
      WeatherTool(),         ← external_api
      StockTool(),           ← external_api
      AddUserFactTool(),     ← user_data
      UpdateUserFactTool(),  ← user_data
      DeleteUserFactTool(),  ← user_data
      URLExtractorTool(),    ← content
  ]
         │
         ▼
  for tool in _ALL_TOOLS:
      registry.register(tool)  ← all 6 tools registered
         │
         ▼
  Global registry ready.
  Workflow imports and uses: from app.tools import registry
```

The global `registry` is the single source of truth for all tools in the system.

---

## 3. Integration with OpenAI Function Calling

### 3.1. Two channels to the LLM

Tool information reaches the LLM through two separate channels simultaneously:

```
  ┌──────────────────────────────────────────────────────────┐
  │  Channel 1: System Prompt text (via get_tool_instructions)│
  │                                                          │
  │  AVAILABLE TOOLS:                                        │
  │  - get_weather: Get current weather for a city...        │
  │  - get_stock_price: Get stock price by ticker symbol...  │
  │  - add_user_fact: Save user's personal info (key-value)  │
  │  ...                                                     │
  │                                                          │
  │  Uses: tool.summary (one-liner)                          │
  │  Purpose: LLM awareness of what tools exist              │
  └──────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────┐
  │  Channel 2: tools= parameter (via get_llama_tools)        │
  │                                                          │
  │  [                                                       │
  │    {                                                     │
  │      "type": "function",                                 │
  │      "function": {                                       │
  │        "name": "get_weather",                            │
  │        "description": "Fetch current weather for a city. │
  │          Use when user explicitly asks about weather...  │
  │          Do NOT use when city name appears without       │
  │          a weather request...",                          │
  │        "parameters": {                                   │
  │          "type": "object",                               │
  │          "properties": {                                 │
  │            "city": { "type": "string" }                  │
  │          },                                              │
  │          "required": ["city"]                            │
  │        }                                                 │
  │      }                                                   │
  │    },                                                    │
  │    ...                                                   │
  │  ]                                                       │
  │                                                          │
  │  Uses: tool.description (detailed)                       │
  │  Purpose: LLM knows HOW to call the tool and WHEN        │
  └──────────────────────────────────────────────────────────┘
```

### 3.2. Tool calling loop

```
  messages = [system_prompt, user_message]
         │
         ▼
  ┌─────────────────────────────────────────┐
  │  llm.achat(messages, tools=openai_tools) │ ◄──────────────────────┐
  └──────────────┬──────────────────────────┘                         │
                 │                                                    │
           ┌─────┴──────┐                                             │
           │            │                                             │
      tool_calls     no tool_calls                                    │
      in response    (final response)                                 │
           │            │                                             │
           ▼            ▼                                             │
     For each call:   Parse RouterOutput JSON                         │
                        │                                             │
     1. Extract name = call.function.name                             │
        args = json.loads(call.function.arguments)                    │
                        │                                             │
     2. registry.execute_tool(name, **args)                           │
        → returns result string (or error string)                     │
                        │                                             │
     3. Append to messages:                                           │
        ChatMessage(                                                  │
          role = TOOL,                                                │
          content = tool_result,                                      │
          tool_call_id = call.id                                      │
        )                                                             │
           │                                                          │
           └──────────────────────────────────────────────────────────┘
           (all tool calls in the batch executed before next LLM call)
```

**Important behaviors:**
- All tool calls returned in a single LLM response are executed **sequentially** before the next LLM call
- The loop has **no iteration limit** — it continues until the LLM responds without any tool calls
- If the LLM call itself fails (API error, timeout), the loop breaks and a generic error response is returned

### 3.3. Error propagation

Tools never crash the loop. All error scenarios produce a string that is fed back to the LLM as the tool result:

```
  User: "What is the weather in Hanoi?"
         │
         ▼
  LLM calls get_weather(city="Hanoi")
         │
         ▼
  execute() raises an exception (e.g., network error)
         │
         ▼
  execute_tool catches exception
  → returns: "Error executing tool 'get_weather': <error details>"
         │
         ▼
  Tool result appended to messages as TOOL role
         │
         ▼
  LLM called again with the error result
  → LLM decides how to respond to the user
    (e.g., "I'm sorry, I couldn't fetch the weather right now.")
```

The LLM receives the error string as data and formulates an appropriate response — the user gets a helpful message instead of an HTTP 500.

### 3.4. Tool results are ephemeral

Tool messages (`role=TOOL`) exist only within the in-memory `messages` list during the tool calling loop. They are **never written to the database**. Once the request ends, tool results are gone.

This means:
- Future requests do not see raw tool results in chat history
- The `messages` table only contains `user` and `assistant` messages
- The LLM's final `assistant` response (which incorporates tool results) is what gets saved and remembered

---

## 4. Adding a New Tool

To add a new tool to the system, three steps are required:

**Step 1 — Create the tool class**

Create a new file in `app/tools/implementations/`:

```python
from app.tools.base import BaseTool

class MyNewTool(BaseTool):
    name        = "my_tool_name"          # unique, snake_case
    summary     = "One-line description for system prompt."
    description = """Detailed description for OpenAI function calling.
    Use when user explicitly asks about X (keywords: "...").
    Do NOT use when Y appears without Z request.
    Returns: ..."""
    category    = "external_api"          # external_api / user_data / content

    def execute(self, param1: str, param2: str) -> str:
        # implementation
        return f"Result: {param1}, {param2}"
```

**Step 2 — Export from implementations package**

Add the class to `app/tools/implementations/__init__.py`:

```python
from app.tools.implementations.my_new_tool import MyNewTool

__all__ = [
    ...,
    "MyNewTool",
]
```

**Step 3 — Register in the global registry**

Add an instance to `_ALL_TOOLS` in `app/tools/__init__.py`:

```python
from app.tools.implementations import (
    ...,
    MyNewTool,
)

_ALL_TOOLS = [
    ...,
    MyNewTool(),   # ← add here, in the appropriate category group
]
```

The tool is automatically registered, injected into the system prompt, and made available to the LLM on the next application start.

---

## 5. Key Design Decisions

### Tools are synchronous

All `execute()` methods are regular synchronous functions, not `async`. They are called from within the async workflow using `registry.execute_tool()` — Python allows calling sync functions from async context directly as long as they don't block the event loop for extended periods.

Current tools (mock data + DB calls) are fast enough that this is not a problem. If a tool needed to make a slow network call (e.g., a real weather API), it should use `asyncio.to_thread()` or be refactored to an async execute.

### `user_data` tools access context via ContextVar

`user_data` tools need the current user's ID and database session to read/write user facts. Rather than passing these as parameters (which would expose them to the LLM as callable arguments), they are retrieved from `ContextVar` at execution time:

```python
def execute(self, key: str, value: str) -> str:
    user_id = get_current_user_id()    ← from ContextVar
    db = get_current_db_session()      ← from ContextVar
    ...
```

This keeps the LLM-facing function signature clean (`key` and `value` only) while tools internally have access to the full request context.

### All errors return strings — never raise

`registry.execute_tool()` wraps every call in try/except and returns error strings. Individual tool implementations also catch their own exceptions and return descriptive error strings. This design:
- Prevents any single tool failure from crashing the entire request
- Gives the LLM useful error information to pass back to the user
- Keeps the tool calling loop running regardless of individual tool outcomes

### Tool results are not persisted

Tool results (`role=TOOL` messages) are ephemeral within a request. Only the final LLM response that incorporates tool results is saved to the database as an `assistant` message. This keeps the `messages` table clean and prevents raw API responses or intermediate data from polluting the conversation history or future context.
