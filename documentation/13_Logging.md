# Logging

## 1. Overview

The system uses **structlog** to produce structured, machine-readable logs. Every log entry is a JSON object with consistent fields — making logs queryable and filterable rather than just plain text lines.

The full logging stack from application to visualization:

```
  Application (structlog)
         │  writes JSON lines
         ▼
  logs/app.log                    ← rotating file, max 50MB × 10 backups
         │  tailed continuously
         ▼
  Promtail (log collector)        ← reads file, parses JSON, adds labels
         │  pushes to
         ▼
  Loki (log storage)              ← stores logs, indexed by labels
         │  queried by
         ▼
  Grafana (visualization)         ← search, filter, dashboard, alerts
```

**Two output modes:**

| Mode | `LOG_FORMAT` | Use case | Output |
|------|-------------|----------|--------|
| Development | `console` | Local dev | Colorized, human-readable terminal output |
| Production | `json` | Deployed server | One JSON object per line, Promtail-ready |

---

## 2. Logging Architecture — 5 Files

```
  app/logging/
  ├── __init__.py     ← exports get_logger() — entry point for all modules
  ├── config.py       ← setup_logging() — builds processor pipeline and handlers
  ├── context.py      ← ContextVar storage for request_id and user_id
  ├── middleware.py   ← RequestLoggingMiddleware — assigns request_id, logs lifecycle
  └── sanitizer.py   ← sanitize_sensitive_data processor — masks secrets before output
```

**How they connect:**

```
  main.py
  ├── setup_logging()         ← called once at startup (lifespan)
  └── add_middleware(RequestLoggingMiddleware)
         │
         ▼ on every request
  middleware.py
  ├── generate request_id
  ├── set_request_id(request_id)       ← context.py ContextVar
  └── bind_contextvars(request_id, method, path)
         │
         ▼ downstream code calls
  get_logger(__name__).info("event", key=value)
         │
         ▼
  config.py processor pipeline
  └── sanitizer.py  ← runs last before rendering
```

---

## 3. Processor Pipeline

Every log entry passes through an 8-step processor chain before being rendered. This happens automatically — the caller just calls `logger.info(...)` and all context/metadata is injected automatically.

```
  logger.info("llm_call_completed", model="gpt-4o-mini", duration_ms=1852)
         │
         ▼
  1. merge_contextvars
     ← merges fields bound via structlog.contextvars (request_id, method, path)

  2. _inject_context_vars
     ← reads request_id and user_id from ContextVar
     ← adds them to event_dict if present

  3. add_log_level
     ← adds: "level": "info"

  4. add_logger_name
     ← adds: "logger": "app.workflows.workflow"

  5. TimeStamper (ISO UTC)
     ← adds: "timestamp": "2026-02-20T16:22:55.327998Z"

  6. StackInfoRenderer
     ← renders stack trace if exc_info was passed

  7. UnicodeDecoder
     ← ensures all string values are valid UTF-8

  8. sanitize_sensitive_data
     ← masks sensitive fields (password, token, api_key, ...)
     ← masks email partially (b***o@gmail.com)
         │
         ▼
  JSONRenderer    → {"model": "gpt-4o-mini", "duration_ms": 1852,
                     "event": "llm_call_completed", "level": "info",
                     "logger": "app.workflows.workflow",
                     "request_id": "7cf881fe7fc1",
                     "timestamp": "2026-02-20T16:22:55.327998Z"}

  (or ConsoleRenderer in dev — colorized, human-readable)
```

**Key design:** steps 1 and 2 together ensure that `request_id` and `user_id` are present on every log entry from any module — the calling code never has to pass them manually.

---

## 4. `request_id` and Request Context

### 4.1. How `request_id` flows through a request

`RequestLoggingMiddleware` runs on every incoming request (except skipped paths). It generates a unique `request_id` and binds it so all downstream log calls automatically include it:

```
  Incoming request: POST /workflows/chat/run
         │
         ▼
  RequestLoggingMiddleware.dispatch()
  ├── request_id = uuid4().hex[:12]   → "7cf881fe7fc1"
  ├── set_request_id(request_id)      ← stored in ContextVar
  ├── structlog.contextvars.bind_contextvars(
  │       request_id="7cf881fe7fc1",
  │       method="POST",
  │       path="/workflows/chat/run"
  │   )
  ├── logger.info("request_started")
         │
         ▼ FastAPI processes request, workflow runs...
         │  every logger.xxx() call automatically includes request_id
         ▼
  finally:
  ├── logger.info("request_completed", status_code=200, duration_ms=3792)
  └── structlog.contextvars.clear_contextvars()
      clear_request_id()
      clear_user_id()
```

### 4.2. Paths excluded from logging

```python
_SKIP_LOG_PATHS = {"/health", "/docs", "/openapi.json", "/favicon.ico"}
```

These endpoints are polled frequently (health checks, browser favicon requests) and would generate excessive noise in logs.

### 4.3. Full request lifecycle in logs

A single `POST /workflows/chat/run` generates this log sequence (all sharing `request_id`):

```json
{"event": "request_started",          "request_id": "7cf881fe7fc1", "path": "/workflows/chat/run"}
{"event": "security_check_started",   "request_id": "7cf881fe7fc1", "conversation_id": "ba4fef4d..."}
{"event": "security_check_llm_call",  "request_id": "7cf881fe7fc1", "model": "gpt-3.5-turbo", "duration_ms": 1761}
{"event": "security_check_completed", "request_id": "7cf881fe7fc1", "classification": "SAFE"}
{"event": "llm_call_completed",       "request_id": "7cf881fe7fc1", "model": "gpt-4o-mini", "prompt_tokens": 1324}
{"event": "intent_detected",          "request_id": "7cf881fe7fc1", "intent": "GENERAL", "duration_ms": 2005}
{"event": "request_completed",        "request_id": "7cf881fe7fc1", "status_code": 200, "duration_ms": 3792}
```

All 7 entries share the same `request_id` — in Grafana/Loki, querying by `request_id = "7cf881fe7fc1"` returns the complete trace of a single user interaction.

---

## 5. Sensitive Data Sanitization

`sanitize_sensitive_data` runs as the last processor before rendering — any sensitive value is masked before it ever reaches the log output.

### 5.1. Field masking (→ `***REDACTED***`)

Any field whose key matches the sensitive list is replaced with `***REDACTED***`:

```
  password, hashed_password, token, access_token, refresh_token,
  api_key, secret, secret_key, authorization, cookie,
  openai_api_key, tavily_api_key, weather_api_key, finnhub_api_key,
  google_client_secret, supabase_anon_key, supabase_service_key
```

Key matching is **case-insensitive** and normalizes hyphens to underscores (`Authorization` → `authorization`).

### 5.2. Email masking (partial)

Email addresses are not fully hidden — they are partially masked to preserve context:

```
  Input:  "baodoquang@gmail.com"
  Output: "b***g@gmail.com"
          └first  └last  └domain unchanged
```

This allows identifying which user an event belongs to without exposing the full email.

### 5.3. Nested dict handling

The sanitizer recurses into nested dicts, so nested sensitive fields are also masked:

```python
# Input
{"user": {"email": "baodoquang@gmail.com", "token": "abc123"}}

# After sanitization
{"user": {"email": "b***g@gmail.com", "token": "***REDACTED***"}}
```

### 5.4. Real example from `app.log`

```json
{
  "email": "b***o@gmail.com",
  "auth_method": "password",
  "event": "login_success",
  "request_id": "833899c3e2cc",
  "level": "info",
  "logger": "app.routers.auth",
  "timestamp": "2026-02-20T16:22:46.819914Z"
}
```

The email is masked but the domain is preserved — enough to identify the user's email provider without exposing personal data.

---

## 6. Log Entry Structure

Every log entry in JSON format contains **standard fields** (always present) and **business fields** (event-specific).

### 6.1. Standard fields

| Field | Source | Example |
|-------|--------|---------|
| `event` | Caller | `"llm_call_completed"` |
| `level` | `add_log_level` processor | `"info"` |
| `logger` | `add_logger_name` processor | `"app.workflows.workflow"` |
| `timestamp` | `TimeStamper` processor | `"2026-02-20T16:22:55.327998Z"` |
| `request_id` | `_inject_context_vars` | `"7cf881fe7fc1"` |
| `user_id` | `_inject_context_vars` | `"7cdadd1d-5238-4d48-af36-d011ee5ce131"` |
| `path` | `bind_contextvars` (middleware) | `"/workflows/chat/run"` |
| `method` | `bind_contextvars` (middleware) | `"POST"` |

### 6.2. Business-specific fields (examples)

| Event | Extra fields |
|-------|-------------|
| `request_completed` | `status_code`, `duration_ms` |
| `security_check_llm_call` | `model`, `duration_ms` |
| `security_check_completed` | `classification` (`SAFE`/`EXPLOIT`), `duration_ms` |
| `llm_call_completed` | `model`, `llm_call_number`, `duration_ms`, `prompt_tokens`, `completion_tokens`, `total_tokens` |
| `intent_detected` | `intent`, `conversation_id`, `llm_calls`, `tool_calls`, `duration_ms` |
| `login_success` | `email` (masked), `auth_method` |
| `workflow_error` | `error_type`, `detail` |
| `unhandled_error` | `error_type`, `error_message`, `stack_trace` |

### 6.3. Event naming convention

All event names use `snake_case` in the format `noun_verb` or `component_action`:

```
  security_check_started     ← component + started
  security_check_completed   ← component + completed
  llm_call_completed         ← component + completed
  login_success              ← action + outcome
  workflow_error             ← component + error
  request_started            ← noun + started
```

---

## 7. Log Output Modes

### 7.1. `LOG_FORMAT`

**`console`** (development default):

```
2026-02-20 16:22:55 [info     ] security_check_completed   classification=SAFE duration_ms=1762
```
Colorized, each field on one line — easy to scan in terminal.

**`json`** (production):

```json
{"classification": "SAFE", "duration_ms": 1762, "event": "security_check_completed", "level": "info", "logger": "app.workflows.workflow", "request_id": "7cf881fe7fc1", "timestamp": "2026-02-20T16:22:53.322772Z"}
```
One JSON object per line — machine-parseable, Promtail-ready.

### 7.2. `LOG_OUTPUT`

| Value | Behavior |
|-------|----------|
| `stdout` | Console only (default) |
| `file` | File only — writes to `LOG_FILE_PATH` with rotation |
| `both` | Both console and file (recommended for production) |

**File rotation settings (from `settings.py`):**

```
  LOG_FILE_PATH        = "logs/app.log"
  LOG_FILE_MAX_BYTES   = 52428800   (50 MB)
  LOG_FILE_BACKUP_COUNT = 10        (keeps app.log.1 ... app.log.10)
```

When `app.log` reaches 50MB, it is renamed to `app.log.1`, a new `app.log` is created. Up to 10 backup files are kept — total max log storage: ~550MB.

---

## 8. Third-party Library Noise Reduction

`setup_logging()` raises the minimum log level of 6 third-party libraries to `WARNING`, suppressing their verbose `INFO` output:

```python
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("authlib").setLevel(logging.WARNING)
```

**Why this is needed:**

| Library | What it logs at INFO | Why it's noisy |
|---------|---------------------|----------------|
| `uvicorn.access` | Every HTTP request | Duplicates `RequestLoggingMiddleware` output |
| `sqlalchemy.engine` | Every SQL query | Hundreds of queries per workflow run |
| `httpx` / `httpcore` | Every HTTP call to OpenAI | 2–5 calls per chat message |
| `openai` | Request/response details | Duplicates workflow step logs |
| `authlib` | OAuth handshake details | Verbose during Google OAuth flow |

These libraries still log `WARNING` and above — errors and exceptions from them are still captured.

---

## 9. Log Infrastructure — Promtail → Loki → Grafana

### 9.1. Overview

```
  logs/app.log  (JSON lines)
         │
         ▼
  Promtail  (port 9080)
  ├── tails app.log continuously
  ├── parses JSON fields: level, event, logger, request_id, user_id, timestamp
  ├── adds labels: job=agent-chat-backend, app=agent-chat, env=development
  └── pushes log streams to Loki
         │
         ▼
  Loki  (port 3100)
  ├── stores log lines indexed by labels
  └── exposes LogQL query API
         │
         ▼
  Grafana  (port 3000)
  ├── connects to Loki as data source
  ├── LogQL query editor
  └── dashboards, alerts
```

**Local vs Docker differences:**

| Setting | Local | Docker (via docker-compose) |
|---------|-------|-----------------------------|
| Log file path (`__path__`) | Absolute path on host machine | `/logs/app.log` (mounted volume) |
| Loki push URL | `http://localhost:3100` | `http://loki:3100` (service name) |
| Loki port (host) | `3100` | `3100` (or alternate if port conflict) |
| Grafana port (host) | `3000` | `3000` (or alternate if port conflict) |

In Docker Compose, services communicate via internal DNS using service names (`loki`, `grafana`, `backend`) — never `localhost`.

### 9.2. `promtail-config.yml` explained

```yaml
scrape_configs:
  - job_name: agent-chat-backend
    static_configs:
      - labels:
          job: agent-chat-backend     # ← identifies the log source in Loki
          app: agent-chat
          env: development
          __path__: /logs/app.log     # ← Docker: mounted volume path
                                      #   Local: absolute path on host machine

    pipeline_stages:
      - json:                         # parse JSON fields from each log line
          expressions:
            level: level
            event: event
            logger: logger
            request_id: request_id
            user_id: user_id
            timestamp: timestamp

      - labels:                       # promote these fields to Loki labels (indexed)
          level:                      # → enables filter: {level="error"}
          event:                      # → enables filter: {event="llm_call_completed"}
          logger:                     # → enables filter: {logger="app.workflows.workflow"}

      - timestamp:                    # use app timestamp instead of ingest time
          source: timestamp
          format: "2006-01-02T15:04:05.999999Z"
```

### 9.3. Example Grafana / LogQL queries

**Trace a single request end-to-end:**
```logql
{job="agent-chat-backend"} | json | request_id="7cf881fe7fc1"
```

**Find all errors in the last hour:**
```logql
{job="agent-chat-backend"} | json | level="error"
```

**Find all workflow errors for a specific user:**
```logql
{job="agent-chat-backend"} | json | user_id="7cdadd1d-..." | event="workflow_error"
```

**Monitor LLM call durations:**
```logql
{job="agent-chat-backend"} | json | event="llm_call_completed" | unwrap duration_ms
```

**Find all EXPLOIT security classifications:**
```logql
{job="agent-chat-backend"} | json | event="security_check_completed" | classification="EXPLOIT"
```
