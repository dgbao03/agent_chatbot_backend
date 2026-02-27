# Agent Chat Application (Backend Server)

**FastAPI + LlamaIndex backend for an AI-powered chat application with slide presentation generation.**

Built around a multi-step LLM workflow that handles security, intent routing, tool calling, and HTML slide generation — all within a single agent architecture.

---

## Frontend

> **Frontend Repository:** [agent_chat_application_frontend](https://github.com/dgbao03/agent_chat_application_frontend)

A companion React-based frontend is available to visually interact with this backend. It provides a full chat UI, conversation management, and an inline AI slide viewer — making it easy to see how the entire system works end-to-end without needing to call the API manually.

---

## Tech Stack

| Category | Technology |
|----------|-----------|
| Framework | FastAPI |
| AI / LLM | LlamaIndex, OpenAI API |
| Database | PostgreSQL, SQLAlchemy |
| Authentication | JWT, Google OAuth 2.0 |
| Email | aiosmtplib (async SMTP) |
| Background Tasks | APScheduler |
| Logging | structlog → Promtail → Loki → Grafana |
| Deployment | Docker, Docker Compose |

---

## LLM Workflow

Every user message goes through a 3-step `ChatWorkflow` powered by LlamaIndex:

```
              User Message
                  │
                  ▼
  ┌─────────────────────────────────────────────┐
  │  Step 1: Security Check                     │
  │  Classify input as SAFE or EXPLOIT          │
  │  Model: LLM_SECURITY_MODEL (temperature=0)  │
  └───────────────┬─────────────────────────────┘
                  │ SAFE
                  ▼
  ┌─────────────────────────────────────────────┐
  │  Step 2: Route & Answer                     │
  │  Detect intent: GENERAL or PPTX             │
  │  Tool calling loop (weather, stock, URL...) │
  │  Generate answer via LLM                    │
  └───────────────┬─────────────────────────────┘
                  │ intent = PPTX
                  ▼
  ┌─────────────────────────────────────────────┐
  │  Step 3: Slide Generation                   │
  │  Detect action: CREATE_NEW / EDIT           │
  │  Generate HTML pages via LLM                │
  │  Merge pages (for single-page edits)        │
  │  Archive previous version → save to DB      │
  └─────────────────────────────────────────────┘
```

### Step 1 — Security Check

Classifies every user message before any business logic runs.

- Uses a **dedicated LLM** (`LLM_SECURITY_MODEL`, `temperature=0`) for deterministic output
- Output: `SAFE` → continue to Step 2 | `EXPLOIT` → return rejection immediately
- Detects: jailbreak attempts, prompt injection, requests to view system instructions
- **Fail-open behavior**: if the security LLM call fails, the request proceeds to Step 2 (availability over strict security)

### Step 2 — Route & Answer

The main conversation step. Handles both regular chat and tool-augmented responses.

- **Intent detection** via prompt-enforced JSON (LLM cannot use `response_format` and `tools` simultaneously — intent is extracted from the response text)
- **Tool calling loop**: LLM can call multiple tools sequentially; each result is added to the conversation before the next LLM call
- If `intent = GENERAL` → return answer directly
- If `intent = PPTX` → pass to Step 3

### Step 3 — Slide Generation

Generates or edits HTML slide presentations (1280×720px, 3–7 pages).

```
  Detect slide action (CREATE_NEW / EDIT_ACTIVE / EDIT_SPECIFIC)
         │
         ▼
  Load previous slide HTML (only when editing a single specific page)
         │
         ▼
  LLM generates pages → structured output (SlideOutput Pydantic model)
         │
         ▼
  Merge new page into existing pages (single-page edit only)
         │
         ▼
  Archive current version → save new pages to DB
         │
         ▼
  Update active_presentation_id on conversation
```

**Version archiving** happens automatically on every edit — previous versions remain accessible via `GET /api/presentations/{id}/versions/{version}`.

---

## Memory System

The system maintains three layers of memory per user:

### Short-term — Recent Conversation

- Holds the recent conversation turns in LlamaIndex's `ChatMemoryBuffer`
- Hard limit: **2000 tokens**
- When the buffer overflows, truncated messages are moved to long-term memory via summarization

### Long-term — Conversation Summary

- When `ChatMemoryBuffer` overflows, the oldest **80%** of messages are summarized by a dedicated LLM (`LLM_SUMMARY_MODEL`)
- The remaining **20%** stay in the buffer (always starting with a user message)
- The summary is injected into the LLM system prompt on every subsequent turn — the agent stays aware of earlier context without re-reading raw history
- Summaries are **cumulative** — new summaries build on top of existing ones

### Long-term — User Facts

- Persistent key-value facts stored per user across all conversations (e.g., `name: "Bao"`, `location: "Hanoi"`)
- Managed exclusively by the agent via three tools: `AddUserFact`, `UpdateUserFact`, `DeleteUserFact`
- Injected into the system prompt on every turn — the agent "knows" personal context without the user repeating it

```
  ┌──────────────────────────────────────────────────────┐
  │  Short-term                                          │
  │  ChatMemoryBuffer (≤2000 tokens)                     │
  │  Recent N turns of raw messages                      │
  └──────────────────────┬───────────────────────────────┘
                         │ overflow → summarize 80%
  ┌──────────────────────▼───────────────────────────────┐
  │  Long-term: Conversation Summary                     │
  │  Compressed history of what was discussed            │
  │  Injected into system prompt                         │
  └──────────────────────────────────────────────────────┘
  ┌──────────────────────────────────────────────────────┐
  │  Long-term: User Facts                               │
  │  Persistent personal facts across all conversations  │
  │  Injected into system prompt                         │
  └──────────────────────────────────────────────────────┘
```

---

## Context Sent to LLM

What the LLM "sees" differs per workflow step:

**Step 1 — Security Check:**
- System prompt (`SECURITY_CHECK_PROMPT`)
- Current user message only — no history, no tools

**Step 2 — Route & Answer:**
- System prompt (`ROUTER_ANSWER_PROMPT`) with User Facts and Conversation Summary injected inline
- Tool instructions (plain-text usage guide for each tool, injected into system prompt)
- Tool definitions (as JSON schema — sent to OpenAI `tools` parameter)
- Chat history from `ChatMemoryBuffer` (up to 2000 tokens)
- Current user message

**Step 3 — Slide Generation:**
- System prompt (`SLIDE_GENERATION_PROMPT`)
- Current user message
- Previous slide HTML — **loaded conditionally**: only when editing a single specific page (to minimize token usage); not loaded for full-presentation edits or new creations

**What is never in context:**
- Messages already moved to summary (only the summary text is included)
- Slide HTML from other conversations
- User facts belonging to other users

---

## Getting Started

The system runs entirely via **Docker Compose**

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

---

### 1. Clone the repository

```bash
git clone <repo-url>
cd agent_chat_backend
```

---

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in the required values.

Generate secure random secret keys:

```bash
openssl rand -hex 32    # run twice — once for JWT_SECRET_KEY, once for REFRESH_SECRET_KEY
```

---

### 3. Start all services

```bash
docker compose up -d
```

This starts 5 services in the correct order:

| Service | Description |
|---------|-------------|
| `db` | PostgreSQL 16 (internal only) |
| `backend` | FastAPI server — runs `alembic upgrade head` then starts uvicorn |
| `loki` | Log aggregation storage |
| `promtail` | Reads `logs/app.log` → pushes to Loki |
| `grafana` | Log visualization dashboard |

Verify all containers are running:

```bash
docker compose ps
```

---

### 4. Verify

```bash
curl http://localhost:4040/health
# → {"status": "ok", "version": "2.0.0"}
```

---

### 5. Logging Infrastructure

All logging services are included in Docker Compose — no additional installation needed.

**Service ports:**

| Service | Host Port | URL |
|---------|-----------|-----|
| Backend API | `4040` | http://localhost:4040 |
| Grafana | `3000` | http://localhost:3000 |
| Loki | `3100` | http://localhost:3100 |

**Connect Grafana to Loki (first time only):**

1. Open **http://localhost:3000**
2. Go to **Connections → Add new data source → Loki**
3. Set URL to `http://loki:3100`
4. Click **Save & Test**

**Example LogQL queries:**

```logql
# Trace a single request end-to-end by request_id
{job="agent-chat-backend"} |= `21fbdae51ee2`

# All errors
{job="agent-chat-backend"} | json | level="error"

# All workflow errors for a specific user
{job="agent-chat-backend"} | json | event="workflow_error"

# Filter by endpoint
{job="agent-chat-backend"} | json | path="/workflows/chat/run"
```

---

### 6. Common Docker commands

```bash
# View live logs from the backend
docker compose logs -f backend

# Stop all services
docker compose down

# Rebuild and restart after code changes
docker compose up -d --build

# Restart a single service
docker compose restart backend
```

---

## API

All protected endpoints require: `Authorization: Bearer <access_token>`

| Group | Prefix | Description |
|-------|--------|-------------|
| Authentication | `/auth` | Register, login, OAuth, token refresh, password reset |
| Conversations | `/api/conversations` | CRUD, message history, active presentation |
| Presentations | `/api/presentations` | Version history (read-only) |
| Workflow | `/workflows` | AI chat — the main interaction endpoint |
| Utility | `/health`, `/` | Health check, root info |

**Main endpoint:**

```
POST /workflows/chat/run
Body: { "start_event": { "user_input": "...", "conversation_id": "uuid | null" } }
```

→ See [14_API.md](documentation/14_API.md) for full endpoint reference.

---

## Documentation

Detailed documentation for each component:

| File | Topic |
|------|-------|
| [01_Overview.md](documentation/01_Overview.md) | Project overview and key features |
| [02_Server.md](documentation/02_Server.md) | Project structure, layered architecture, multi-tenancy |
| [03_Database.md](documentation/03_Database.md) | PostgreSQL schema, relationships, constraints |
| [04_Authentication.md](documentation/04_Authentication.md) | JWT, Google OAuth, token lifecycle |
| [05_Workflow.md](documentation/05_Workflow.md) | 3-step LlamaIndex workflow — full details |
| [06_Context.md](documentation/06_Context.md) | What is sent to the LLM in each step |
| [07_Memory.md](documentation/07_Memory.md) | Short-term and long-term memory system |
| [08_Tools.md](documentation/08_Tools.md) | Tool architecture, registry, tool calling loop |
| [09_Conversation.md](documentation/09_Conversation.md) | Conversation lifecycle, title generation, access control |
| [10_Presentation.md](documentation/10_Presentation.md) | Slide data model, version archiving, frontend flow |
| [11_Exception.md](documentation/11_Exception.md) | Exception hierarchy, error handling patterns |
| [12_Configuration.md](documentation/12_Configuration.md) | Environment variables, config modules, data type definitions |
| [13_Logging.md](documentation/13_Logging.md) | Structured logging, sanitization, Promtail → Loki → Grafana |
| [14_API.md](documentation/14_API.md) | Full API endpoint reference |

---

## License

MIT License

Copyright (c) 2026 BaoDo

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
