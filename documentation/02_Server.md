# Backend Server

## 1. Overview

The backend is a **FastAPI** application. It serves as the central API layer between the frontend client and all backend services — authentication, AI workflow, conversation storage, and presentation management.

The server is structured in layers: every incoming request passes through middleware, is handled by a router, delegated to a service for business logic, then down to a repository for database access.

## 2. Project Structure

```
agent_chat_backend/
├── main.py                             # FastAPI app, middleware, routers, lifespan
├── schema.sql                          # PostgreSQL schema definition (legacy reference)
├── alembic.ini                         # Alembic configuration
├── alembic/                            # Database migrations
│   ├── env.py                          # Migration env: connects Alembic to Base and DATABASE_URL
│   ├── script.py.mako                  # Template for generated migration files
│   └── versions/                       # Migration files (one file per schema change)
├── Dockerfile                          # Docker image definition (python:3.12-slim)
├── entrypoint.sh                       # Container entrypoint: runs alembic upgrade head then uvicorn
├── docker-compose.yml                  # Orchestrates: backend, db, loki, promtail, grafana
├── .dockerignore                       # Excludes venv, .env, logs, docs from image
├── promtail-config.yml                 # Promtail: tails logs/app.log → pushes to Loki
├── requirements.txt
├── .env.example
│
└── app/
    │
    ├── auth/
    │   ├── context.py                  # ContextVar for user_id and db session (used by Workflow)
    │   ├── dependencies.py             # FastAPI get_current_user dependency (JWT verification)
    │   ├── oauth.py                    # Google OAuth flow (authorization URL, code exchange, user info)
    │   └── utils.py                    # JWT create/verify, password hash/verify
    │
    ├── config/
    │   ├── llm.py                      # LLM factory (get_llm, get_security_llm, get_summary_llm)
    │   ├── prompts.py                  # All LLM system prompts (security, router, slide, summary)
    │   ├── settings.py                 # Centralized env var config (LLM models, CORS, cookie)
    │
    ├── types/                          # Centralized type definitions (schemas + internal types)
    │   ├── http/                       # Pydantic request/response schemas for HTTP boundary
    │   │   ├── auth.py
    │   │   ├── conversation.py
    │   │   ├── presentation.py
    │   │   └── workflow.py
    │   ├── internal/                   # TypedDict definitions shared across code layers
    │   │   ├── conversation.py
    │   │   ├── presentation.py
    │   │   └── user_facts.py
    │   └── llm/
    │       └── outputs.py              # Pydantic schemas for LLM structured outputs
    │
    ├── database/
    │   └── session.py                  # SQLAlchemy engine, SessionLocal, Base, get_db dependency (Base is used by Alembic)
    │
    ├── exceptions.py                   # Custom exception hierarchy (AppException and subclasses)
    │
    ├── logging/
    │   ├── __init__.py                 # setup_logging(), get_logger()
    │   ├── config.py                   # structlog + stdlib logging configuration
    │   ├── context.py                  # request_id and user_id context (ContextVar)
    │   ├── middleware.py               # RequestLoggingMiddleware (request_id, lifecycle logging)
    │   └── sanitizer.py               # Strips sensitive fields before logging
    │
    ├── models/                         # SQLAlchemy ORM models (one file per table)
    │   ├── user.py
    │   ├── conversation.py
    │   ├── message.py
    │   ├── conversation_summary.py
    │   ├── user_fact.py
    │   ├── presentation.py
    │   ├── presentation_page.py
    │   ├── presentation_version.py
    │   ├── presentation_version_page.py
    │   ├── token_blacklist.py
    │   └── password_reset_token.py
    │
    ├── repositories/                   # Data access layer — DB queries only, no business logic
    │   ├── user_repository.py
    │   ├── conversation_repository.py
    │   ├── chat_repository.py
    │   ├── summary_repository.py
    │   ├── presentation_repository.py
    │   ├── user_facts_repository.py
    │   ├── token_blacklist_repository.py
    │   └── password_reset_token_repository.py
    │
    ├── routers/                        # HTTP endpoint handlers
    │   ├── auth.py                     # /auth — register, login, refresh, OAuth, forgot/reset password
    │   ├── conversations.py            # /api/conversations — CRUD conversations and messages
    │   ├── presentations.py            # /api/presentations — presentation versions and page content
    │   └── workflow.py                 # /workflows/chat/run — triggers ChatWorkflow
    │
    ├── services/                       # Business logic layer
    │   ├── auth_service.py             # register, login, token refresh, OAuth callback, password reset
    │   ├── conversation_service.py     # validate_conversation_access, get_or_create_conversation, list/get/update/delete CRUD
    │   ├── context_service.py          # build_chat_context, build_slide_context (LLM system-prompt assembly)
    │   ├── email_service.py            # Send password reset email via SMTP
    │   ├── memory_service.py           # load_conversation_memory, split_messages_for_summary, create_summary
    │   ├── message_service.py          # save_user_message, save_assistant_message
    │   └── presentation_service.py     # detect_presentation_intent (CREATE_NEW / EDIT), get_presentation_versions, get_version_content
    │
    ├── tasks/
    │   └── cleanup.py                  # APScheduler — purge expired tokens every 24h
    │
    ├── tools/
    │   ├── base.py                     # BaseTool abstract class
    │   ├── registry.py                 # ToolRegistry (register, execute, get_llama_tools)
    │   └── implementations/
    │       ├── weather.py              # get_weather
    │       ├── stock.py                # get_stock_price
    │       ├── user_facts.py           # add_user_fact, update_user_fact, delete_user_fact
    │       └── url_extractor.py        # extract_url_content
    │
    ├── utils/
    │   ├── formatters.py               # format_messages_for_summary
    │   ├── helpers.py                  # find_fact_by_key
    │   └── title_generator.py          # generate_conversation_title (no LLM, pattern-based)
    │
    └── workflows/
        ├── workflow.py                 # ChatWorkflow — security_check, route_and_answer, generate_slide
        └── memory_manager.py          # process_memory_truncation, summarization trigger
```

## 3. Directory Organization Pattern

The project uses a **Layer-based** folder structure — folders are grouped by **technical role** (what the code does), not by feature or domain.

```
  routers/        ←  all API endpoints (HTTP handlers)
  services/       ←  all business logic
  repositories/   ←  all database queries
  types/http/     ←  all Pydantic request / response models (HTTP boundary)
  types/internal/ ←  all TypedDict internal types (between code layers)
  types/llm/      ←  all Pydantic models for structured LLM outputs
  models/         ←  all SQLAlchemy ORM entities
```

Each folder contains only **one type of responsibility**. A router never writes SQL. A repository never contains business logic. The boundary between layers is strict — data flows in one direction, top to bottom.

**Rules:**
- Router can only call Service or Repository — never writes SQL directly
- Service contains business logic — can call multiple Repositories
- Repository only writes SQL — no business logic allowed
- Types only defines the shape of data — no logic

## 4. Architecture Layers

Each incoming HTTP request flows through the following layers:

```
      HTTP Request
           │
           ▼
┌─────────────────────┐
│      Middleware     │  ← RequestLoggingMiddleware, CORSMiddleware
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│       Router        │  ← auth / conversations / presentations / workflow
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Auth Dependency    │  ← get_current_user (JWT verification)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Service (if any)   │  ← Business logic, access control
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    Repository       │  ← DB queries (SQLAlchemy)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│     PostgreSQL      │
└─────────────────────┘
```

- **Router** — receives the HTTP request, validates request body (Pydantic schema), calls service or repository
- **Service** — business logic: ownership validation, orchestration across multiple repositories
- **Repository** — executes SQL queries only; returns plain data dictionaries; no business logic allowed

## 5. Multi-Tenant Design

The system is **multi-tenant by user**: every piece of data in the database is scoped to a specific user. Users can only access their own data — they cannot see or modify another user's conversations, presentations, or personal information.

```
  User A (JWT: user_id=A)         User B (JWT: user_id=B)
           │                                │
           ▼                                ▼
    get_current_user()              get_current_user()
           │                                │
           ▼                                ▼
    DB query WHERE                   DB query WHERE
    user_id = A                      user_id = B
           │                                │
           ▼                                ▼
  ┌─────────────────┐            ┌─────────────────┐
  │  Conversations  │            │  Conversations  │
  │  Presentations  │            │  Presentations  │
  │  User Facts     │            │  User Facts     │
  └─────────────────┘            └─────────────────┘
     (A's data only)               (B's data only)
```

### 5.1. Approach

The system does **not** use PostgreSQL Row Level Security (RLS). Instead, data isolation is enforced entirely at the **application layer** — every repository query includes an explicit `user_id` filter in the SQL `WHERE` clause. This is documented in the source code with comments:

```
# Security: filter by user_id    ← present throughout all repositories
# replaces RLS                    ← noted in auth/context.py
```

### 5.2. How `user_id` flows through the system

There are two mechanisms for passing `user_id` depending on the context:

**Mechanism 1 — Direct parameter** (used by Routers):

```
  JWT token in Authorization header
            │
            ▼
  get_current_user()        ← FastAPI dependency, runs on every protected route
  verifies JWT, extracts user_id
            │
            ▼
  user_id passed explicitly as parameter
  to repository functions
  e.g. list_conversations(user_id, db)
       get_conversation_by_id(id, user_id, db)
```

**Mechanism 2 — ContextVar** (used by Workflow):

```
  JWT token in Authorization header
            │
            ▼
  get_current_user()        ← same JWT verification
            │
            ▼
  set_current_user_id(user_id)
  stores user_id in Python ContextVar
  (scoped to the current async task)
            │
            ▼
  Workflow steps read user_id via get_current_user_id()
  and pass it explicitly to service and repository functions
```

The Workflow engine (LlamaIndex) does not support passing `user_id` as a function parameter across steps, so `contextvars.ContextVar` is used to propagate it safely within the scope of a single async request. Workflow steps read the value once via `get_current_user_id()` at the beginning of each step and then pass `user_id` explicitly as a parameter down through the service and repository layers.

### 5.3. Data isolation per table

Every data table that belongs to a user is filtered at the repository layer:

- **conversations** — `WHERE conversations.user_id = :user_id`

- **messages** — ownership verified via `conversations.user_id` first, then messages are queried for that conversation

- **presentations** — JOINed with `conversations`, filtered by `conversations.user_id`

- **presentation_pages / versions** — accessed only through a presentation that has passed the ownership check

- **user_facts** — `WHERE user_facts.user_id = :user_id`

- **conversation_summaries** — accessed only through a conversation that has passed the ownership check

- **token_blacklist** — scoped by `user_id`

- **password_reset_tokens** — scoped by `user_id`

### 5.4. Double ownership check in Workflow

For the chat workflow specifically, ownership is checked twice — once at the router level and once inside the workflow itself:

```
  POST /workflows/chat/run
            │
            ▼
  get_current_user()
  ← Layer 1: JWT verified, user_id extracted and stored in ContextVar
            │
            ▼
  ChatWorkflow.route_and_answer()
            │
            ▼
  conversation_service.get_or_create_conversation(user_id, conversation_id, ...)
  ← Layer 2: if conversation_id is provided, calls validate_conversation_access()
  ← raises NotFoundError (404) if the conversation doesn't exist or isn't owned
            │
            ▼
  Continue processing
```

This double check ensures that even if a request somehow bypasses the router dependency, the workflow will still reject any attempt to access a conversation that does not belong to the authenticated user.

## 6. Routers

The application exposes four routers:

```
┌─────────────────────────────────────────────────────────────┐
│  Router            │  Prefix               │  Tag           │
├─────────────────────────────────────────────────────────────┤
│  auth.router       │  /auth                │ authentication │
│  conversations     │  /api/conversations   │ conversations  │
│  presentations     │  /api/presentations   │ presentations  │
│  workflow          │  /workflows           │ workflows      │
└─────────────────────────────────────────────────────────────┘
```

- `/auth` — registration, login, token refresh, OAuth, password reset, sign out
- `/api/conversations` — CRUD for conversations and messages
- `/api/presentations` — read presentation versions and page content
- `/workflows/chat/run` — the main chat endpoint that triggers the AI workflow

## 7. Middleware

Middleware is applied in the following order (last registered = first executed):

```
     Incoming Request
              │
              ▼
┌───────────────────────────┐
│  RequestLoggingMiddleware │  ← runs first
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│      CORSMiddleware       │  ← runs second
└─────────────┬─────────────┘
              │
              ▼
         Route Handler
```

**RequestLoggingMiddleware** (`app/logging/middleware.py`):
- Generates a unique `request_id` for every request
- Binds `request_id`, `method`, and `path` to the structured log context so every log line within a request carries these fields
- Logs `request_started` at the beginning and `request_completed` (with status code and duration) at the end
- Skips logging for noise paths: `/health`, `/docs`, `/openapi.json`, `/favicon.ico`

**CORSMiddleware**:
- Allows cross-origin requests from frontend origins configured via `CORS_ORIGINS` environment variable
- Supports credentials, all methods, and all headers

## 8. Database Session

The database session is managed via a FastAPI dependency (`get_db`) injected into every router handler that needs database access.

```
  Request arrives
        │
        ▼
  get_db() opens a new SQLAlchemy session
        │
        ▼
  Session passed to router → service → repository
        │
        ▼
  Request completes (success or error)
        │
        ▼
  session.close() — always runs in finally block
```

- Each request gets its own isolated session
- Sessions are never shared across requests
- If an operation fails, the repository calls `db.rollback()` before returning

## 9. Database Migration

The project uses **Alembic** to track and manage all database schema changes. Every change to the schema is captured in a versioned migration file, and Alembic determines which files have not yet been applied by reading a special `alembic_version` table in the database.

### 9.1. How it works

```
  Modify SQLAlchemy model
          │
          ▼
  alembic revision --autogenerate
          │
          ▼
  Alembic compares models vs current DB schema
          │
          ▼
  Generates migration file in alembic/versions/
  (contains upgrade() and downgrade() SQL operations)
          │
          ▼
  alembic upgrade head
          │
          ▼
  Alembic reads alembic_version → finds unapplied files
          │
          ▼
  Applies each file in order → updates alembic_version
```

Each migration file has two functions:

- `upgrade()` — SQL to apply the change (e.g. `ALTER TABLE ... ADD COLUMN`)
- `downgrade()` — SQL to reverse the change (e.g. `ALTER TABLE ... DROP COLUMN`)

### 9.2. Project integration

Three components are wired together in `alembic/env.py`:

| Component | Source |
|---|---|
| `DATABASE_URL` | `app/config/settings.py` — loaded from `.env` |
| `Base` | `app/database/session.py` — SQLAlchemy declarative base |
| All ORM models | `app/models/__init__.py` — imports all models onto `Base.metadata` |

`target_metadata = Base.metadata` tells Alembic which tables to track. All models **must** be imported in `app/models/__init__.py` before running `autogenerate`, otherwise Alembic will not detect them.

### 9.3. Common commands

```bash
# Check which version the database is currently at
alembic current

# View full migration history
alembic history

# Apply all unapplied migrations
alembic upgrade head

# Roll back the most recent migration
alembic downgrade -1

# Generate a new migration file from model changes
alembic revision --autogenerate -m "description of change"
```

### 9.4. Workflow — making a schema change

```
Step 1: Edit the SQLAlchemy model in app/models/
        (add/remove/modify a column, table, index, etc.)

Step 2: If adding a new model, import it in app/models/__init__.py

Step 3: Generate migration file
        $ alembic revision --autogenerate -m "short description"

Step 4: Review the generated file in alembic/versions/
        Verify upgrade() and downgrade() are correct before applying

Step 5: Apply the migration
        $ alembic upgrade head

Step 6: Verify
        $ alembic current   ← should show the new version as (head)
```

### 9.5. Important notes

- **Always `downgrade` before deleting a migration file** — deleting the file first makes rollback impossible and leaves the database out of sync
- **Review autogenerated files** — `--autogenerate` is not always perfect; always inspect the generated SQL before applying to production
- **Alembic does not create the database** — for local development, the database itself must exist before running any migration commands; only tables and schema objects are managed by Alembic. When using Docker Compose, the `db` service (PostgreSQL container) automatically creates the database via the `POSTGRES_DB` environment variable — no manual setup required
- **Generate migrations against an empty database** — always run `alembic revision --autogenerate` against a fresh empty database to produce correct `CREATE TABLE` statements. Running against an existing database only generates a diff (ALTER statements), which will fail on any fresh deployment
- **Circular FK dependencies** — if two tables reference each other (e.g. `conversations ↔ presentations`), Alembic cannot resolve the creation order automatically. The correct approach: create one table without the circular FK, create the second table, then add the FK using `op.create_foreign_key()`

---

## 10. Application Lifespan

The server uses FastAPI's `lifespan` context manager to run startup and shutdown logic:

```
  Server starts
       │
       ▼
  setup_logging()          ← initialise structlog
  start_scheduler()        ← start APScheduler (token cleanup every 24h)
       │
       ▼
  Server is running...
       │
       ▼
  Server shuts down
       │
       ▼
  stop_scheduler()         ← graceful shutdown of background scheduler
```

## 11. Global Exception Handlers

Two exception handlers are registered in `main.py`, each targeting a different class of error:

**`AppException` handler** — catches any `AppException` subclass raised by service functions:
- Converts it to a JSON response using `exc.status_code` and `{"detail": exc.message}`
- Ensures that service-layer errors (auth failures, not-found, validation) reach the client with the correct HTTP status code and a safe, human-readable message
- Exception: the workflow router has its own `try/except AppException` block and returns `{"status": "error", "error": "..."}` — it never reaches this global handler

**Unhandled `Exception` handler** — catches any exception not already handled:
- Logs the full stack trace with `error_type`, `error_message`, HTTP method, and path
- Returns a generic `500 Internal Server Error` to the client without leaking internal details

See [11_Exception.md](11_Exception.md) for the full exception handling architecture and the two-pattern approach (REST vs Workflow).

## 12. Logging

The application uses **structlog** for structured JSON logging. Every log line is a JSON object with consistent fields — making it easy to search, filter, and ship to external log storage.

```
  Application code
        │
        ▼
  structlog (JSON formatter)
        │
        ▼
  Log file / stdout
        │
        ▼
  Promtail (collector) → Loki (storage) → Grafana (visualizer)
```

Key behaviors:
- Every request is assigned a unique `request_id` by `RequestLoggingMiddleware`, which is attached to all log lines within that request
- `user_id` is bound to the log context after JWT verification, so all downstream log lines include who made the request
- Sensitive data is sanitized before logging via `app/logging/sanitizer.py`

See [13_Logging.md](13_Logging.md) for full details.
 