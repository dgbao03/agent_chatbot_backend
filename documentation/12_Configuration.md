# Configuration

## 1. Overview

All application configuration is sourced from a single `.env` file. `app/config/settings.py` is the **single source of truth** — the only file in the entire codebase that calls `load_dotenv()` and `os.getenv()`. All other modules import constants directly from `settings.py`.

```
  .env
    │
    ▼
  app/config/settings.py   ← only file that reads .env
    │
    ├──► app/auth/utils.py          (JWT secret keys, token expiry)
    ├──► app/auth/oauth.py          (Google OAuth credentials)
    ├──► app/routers/auth.py        (FRONTEND_URL, REFRESH_TOKEN_EXPIRE_DAYS)
    ├──► app/services/email_service.py  (SMTP settings)
    ├──► app/database/session.py    (DATABASE_URL)
    └──► app/logging/config.py      (LOG_LEVEL, LOG_FORMAT, ...)
```

This ensures:
- One place to look when changing any configuration value
- No risk of modules using different defaults for the same variable
- `REFRESH_TOKEN_MAX_AGE` (cookie lifetime) is always in sync with `REFRESH_TOKEN_EXPIRE_DAYS` (JWT lifetime)

---

## 2. `app/config/settings.py` — Runtime Configuration

All environment variables with their defaults and types:

### LLM

| Variable | Default | Type | Description |
|----------|---------|------|-------------|
| `LLM_MODEL` | `gpt-4o-mini` | str | Model for main chat and slide generation |
| `LLM_SECURITY_MODEL` | `gpt-4o-mini` | str | Model for security classification |
| `LLM_SUMMARY_MODEL` | `gpt-4o-mini` | str | Model for memory summarization |
| `LLM_TIMEOUT` | `300` | float | Timeout (seconds) for main LLM calls |
| `LLM_SECURITY_TIMEOUT` | `30` | float | Timeout for security check calls |
| `LLM_SUMMARY_TIMEOUT` | `120` | float | Timeout for summary generation calls |

### Database

| Variable | Default | Type | Description |
|----------|---------|------|-------------|
| `DATABASE_URL` | — | str | PostgreSQL connection string. **Required** — app raises `ValueError` on startup if missing |

### JWT

| Variable | Default | Type | Description |
|----------|---------|------|-------------|
| `ACCESS_TOKEN_SECRET_KEY` | — | str | Signing key for access tokens. **Required** |
| `REFRESH_TOKEN_SECRET_KEY` | — | str | Signing key for refresh tokens. **Required** |
| `ALGORITHM` | `HS256` | str | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | int | Access token lifetime in minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | int | Refresh token lifetime in days |

### Google OAuth

| Variable | Default | Type | Description |
|----------|---------|------|-------------|
| `GOOGLE_CLIENT_ID` | — | str | Google OAuth app client ID |
| `GOOGLE_CLIENT_SECRET` | — | str | Google OAuth app client secret |
| `GOOGLE_REDIRECT_URI` | `http://localhost:4040/auth/callback` | str | OAuth redirect URI |

### Frontend / CORS / Cookie

| Variable | Default | Type | Description |
|----------|---------|------|-------------|
| `FRONTEND_URL` | `http://localhost:5174` | str | Frontend base URL (used in OAuth redirect) |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:5174` | list[str] | Comma-separated allowed origins |
| `COOKIE_SECURE` | `false` | bool | Set `true` in production (HTTPS only cookies) |

### SMTP

| Variable | Default | Type | Description |
|----------|---------|------|-------------|
| `SMTP_HOST` | `smtp.gmail.com` | str | SMTP server hostname |
| `SMTP_PORT` | `587` | int | SMTP port (587 = STARTTLS, 465 = SSL/TLS) |
| `SMTP_USER` | — | str | SMTP username / sender address |
| `SMTP_PASSWORD` | — | str | SMTP password |
| `SMTP_FROM_EMAIL` | fallback to `SMTP_USER` | str | From address (defaults to `SMTP_USER` if not set) |
| `SMTP_FROM_NAME` | `Chat Assistant` | str | Display name for sent emails |

> **Note:** `SMTP_USE_TLS` is not read from `.env` — it is derived from `SMTP_PORT` automatically: port `465` → `use_tls=True`, port `587` → `use_tls=False` (STARTTLS handled automatically by `aiosmtplib`).

### Logging

| Variable | Default | Type | Description |
|----------|---------|------|-------------|
| `LOG_LEVEL` | `INFO` | str | Minimum log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_FORMAT` | `console` | str | Output format: `console` (human-readable) or `json` (machine-readable for production) |
| `LOG_OUTPUT` | `stdout` | str | Output destination: `stdout`, `file`, or `both` |
| `LOG_FILE_PATH` | `logs/app.log` | str | Log file path (used when `LOG_OUTPUT` is `file` or `both`) |
| `LOG_FILE_MAX_BYTES` | `52428800` (50MB) | int | Max size before log rotation |
| `LOG_FILE_BACKUP_COUNT` | `10` | int | Number of rotated log files to keep |

### Memory

| Variable | Default | Type | Description |
|----------|---------|------|-------------|
| `MEMORY_TOKEN_LIMIT` | `2000` | int | Max tokens for `ChatMemoryBuffer` short-term memory |
| `MEMORY_KEEP_RATIO` | `0.2` | float | Fraction of messages to keep (not summarize) during memory truncation |

### Password Reset

| Variable | Default | Type | Description |
|----------|---------|------|-------------|
| `PASSWORD_RESET_EXPIRE_MINUTES` | `15` | int | Password reset token lifetime in minutes |

---

## 3. `app/config/llm.py` — LLM Factory

`llm.py` is a factory module that creates OpenAI LLM instances from settings. Rather than instantiating `OpenAI(...)` inline wherever it's needed, all LLM creation is centralized here.

```
  app/config/settings.py
  (LLM_MODEL, timeouts, ...)
         │
         ▼
  app/config/llm.py
  ┌───────────────────────────────────────────────────────────┐
  │  get_llm()           → main LLM (chat, slide generation)  │
  │  get_security_llm()  → security classification LLM        │
  │  get_summary_llm()   → memory summarization LLM           │
  └───────────────────────────────────────────────────────────┘
         │
         ├──► workflows/workflow.py   (get_llm, get_security_llm)
         └──► services/memory_service.py  (get_summary_llm)
```

**Three LLM instances and their differences:**

| Function | Used for | Special config |
|----------|----------|----------------|
| `get_llm(**overrides)` | Chat answers, slide generation, tool calling | Accepts `**overrides` to adjust model/temperature per call |
| `get_security_llm()` | Security classification in Step 1 | `temperature=0` — forces deterministic output, shorter timeout (30s) |
| `get_summary_llm()` | Memory summarization | Standard temperature, longer timeout (120s) |

`get_llm()` accepts keyword overrides, allowing callers to adjust behavior without creating a new factory:

```python
# Use default settings
llm = get_llm()

# Override model for a specific call
llm = get_llm(model="gpt-4o", temperature=0)
```

---

## 4. Three Ways to Define Data — Models, TypedDict, Pydantic

The system defines data in three distinct ways, each serving a different purpose:

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                                                                     │
  │  app/models/        → Talks to DATABASE                             │
  │  (SQLAlchemy ORM)     "Table conversations has columns id, ..."     │
  │                                                                     │
  │  app/config/types.py → Talks between CODE LAYERS                    │
  │  (TypedDict)           "When passing data in Python, it looks..."   │
  │                                                                     │
  │  app/config/pydantic_outputs.py → Talks to LLM                      │
  │  (Pydantic)            "LLM must return output in this format..."   │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘
```

---

### 4.1. SQLAlchemy Models (`app/models/`) — Talking to the Database

Each model class maps **1:1** to a PostgreSQL table. The system has **11 models** corresponding to 11 tables.

**Characteristics:**

- **Relationships** — defined via `relationship()`, enabling joins and cascade behavior:
  ```python
  # Conversation model
  messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
  presentations = relationship("Presentation", ...)
  ```
- **Constraints** — enforced at the database level:
  ```python
  # Message model
  CheckConstraint("role IN ('user', 'assistant', 'system')", name="check_message_role")
  CheckConstraint("intent IN ('PPTX', 'GENERAL') OR intent IS NULL", name="check_message_intent")
  ```
- **Server defaults** — id and timestamps auto-generated by PostgreSQL:
  ```python
  id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
  created_at = Column(TIMESTAMP(timezone=True), server_default=text("NOW()"))
  ```
- **Live objects** — SQLAlchemy model instances are connected to a DB session. They can lazy-load relationships on access. This is why they must not leave the Repository layer — passing them to Services or Workflow would cause session-detached errors.

**Used by:** Repository layer exclusively. All reads and writes to the database go through these models.

**The 11 models:**

```
  app/models/
  ├── user.py
  ├── conversation.py
  ├── message.py
  ├── conversation_summary.py
  ├── user_fact.py
  ├── presentation.py
  ├── presentation_page.py
  ├── presentation_version.py
  ├── presentation_version_page.py
  ├── token_blacklist.py
  └── password_reset_token.py
```

---

### 4.2. TypedDict (`app/config/types.py`) — Talking Between Code Layers

TypedDicts define the shape of Python dictionaries passed between layers. Repository functions convert SQLAlchemy model instances to dicts before returning — this keeps upper layers (Services, Workflow) free from DB session dependencies.

```
  Repository
    │  db.query(ConversationModel)...
    │  → SQLAlchemy object (live, tied to session)
    │  → convert to plain dict
    ▼
  TypedDict (Message, Conversation, Presentation, ...)
    │  plain Python dict — no DB connection, no session
    ▼
  Service / Workflow
    │  receives dict, uses it freely
    ▼
  API Response (converted to Pydantic schema for serialization)
```

**Characteristics:**

- Plain Python dicts — no runtime validation, no DB connection
- `total=False` on most types means all fields are optional when constructing the dict — the caller only includes what's available
- Type hints exist for IDE support and static analysis, but are not enforced at runtime

**TypedDicts defined:**

| TypedDict | Corresponds to | Used by |
|-----------|---------------|---------|
| `Message` | `messages` table | `chat_repository`, `workflow.py`, `helpers.py` |
| `SummaryDict` | `conversation_summaries` table | `summary_repository` |
| `Conversation` | `conversations` table | `conversation_repository` |
| `UserFact` | `user_facts` table | `user_facts_repository`, `user_facts` tool |
| `Presentation` | `presentations` table | `presentation_repository`, `workflow.py` |
| `PresentationWithPages` | `presentations` + `presentation_pages` (JOIN) | `presentation_repository` |
| `PresentationVersion` | `presentation_versions` table | `presentation_repository` |
| `VersionContent` | `presentation_version_pages` table | `presentation_repository` |

---

### 4.3. Pydantic Models (`app/config/pydantic_outputs.py`) — Talking to the LLM

Pydantic models define the **exact format the LLM must return**. Without structured output, the LLM returns free-form text — Pydantic enforces a schema so the application can reliably parse and use LLM responses.

```
  Workflow sends prompt to LLM
  + response_format = { JSON schema derived from Pydantic model }
         │
         ▼
  LLM returns JSON string conforming to schema
         │
         ▼
  Model.model_validate_json(response)
  → Pydantic object with validated fields
  → Parse failure → raise error immediately (no silent garbage)
```

**Key feature — `Field(description=...)`:**

The `description` in each `Field()` is sent to the LLM as part of the JSON schema. It acts as inline instructions telling the LLM what each field means and what value to put there:

```python
class RouterOutput(BaseModel):
    intent: Literal["PPTX", "GENERAL"] = Field(
        description="PPTX if user wants slides, GENERAL for regular conversation"
        # ↑ LLM reads this to understand what 'intent' means
    )
    answer: Optional[str] = Field(
        description="Answer text. Only set when intent is GENERAL, must be null for PPTX"
        # ↑ LLM reads this constraint and follows it
    )
```

**Five Pydantic output models:**

| Model | Used in | LLM call type | Fields |
|-------|---------|---------------|--------|
| `SecurityOutput` | Step 1 (security check) | `response_format` (JSON Schema) | `classification` (SAFE/EXPLOIT), `answer` |
| `RouterOutput` | Step 2 (route & answer) | Prompt-enforced JSON | `intent` (PPTX/GENERAL), `answer` |
| `SlideIntentOutput` | Step 3 (slide intent detection) | `response_format` (JSON Schema) | `action`, `target_slide_id`, `target_page_number` |
| `SlideOutput` | Step 3 (slide generation) | `response_format` (JSON Schema) | `intent`, `answer`, `topic`, `pages`, `total_pages` |
| `PageContent` | Step 3 (each slide page) | Nested inside `SlideOutput` | `page_number`, `html_content`, `page_title` |