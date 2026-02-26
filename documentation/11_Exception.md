# Exception Handling

## 1. Overview

The system uses a **centralized custom exception hierarchy** rooted at `AppException`. All application-level errors inherit from this base class, which provides:

- A `message` field — safe to return directly to the client
- A `status_code` field — maps directly to the HTTP response status
- A clear contract: **`AppException` = safe to show to client**, plain `Exception` = unexpected internal error

The core principle: exceptions are **raised deep** (in Repository/Service/Workflow layers) and **caught high** (at the Router layer only). Business logic never catches and swallows exceptions silently — it either re-raises or delegates to the graceful degradation pattern.

```
  app/exceptions.py
  ─────────────────────────────────────────────────────────────
  AppException (base)
  ├── AuthenticationError  (401)
  ├── NotFoundError        (404)
  ├── AccessDeniedError    (403)
  ├── ValidationError      (422)
  ├── LLMError             (502)
  ├── DatabaseError        (500)
  └── ExternalServiceError (502)
```

---

## 2. Exception Hierarchy

### 2.1. Class tree and descriptions

```
  AppException
  │  status_code = 400
  │  message: str  ← safe to expose to client
  │
  ├── AuthenticationError (401)
  │     Authentication failure (wrong credentials, invalid/expired token, etc.)
  │     Constructor: AuthenticationError(message: str = "Authentication failed")
  │     Example: AuthenticationError("Invalid email or password")
  │
  ├── NotFoundError (404)
  │     Resource not found (conversation, presentation, user, etc.)
  │     Constructor: NotFoundError(resource: str, resource_id: str = "")
  │     Example: NotFoundError("Conversation", "abc-123")
  │              → "Conversation not found: abc-123"
  │
  ├── AccessDeniedError (403)
  │     User does not own or cannot access the resource
  │     Constructor: AccessDeniedError(message: str = "Access denied")
  │     Example: AccessDeniedError("Unable to verify conversation ownership")
  │
  ├── ValidationError (422)
  │     Input failed validation (bad format, missing fields, logic errors)
  │     Constructor: ValidationError(message: str = "Validation failed")
  │     Example: ValidationError("target_presentation_id required for EDIT action")
  │
  ├── LLMError (502)
  │     LLM failure (timeout, output parsing, quota exceeded, etc.)
  │     Constructor: LLMError(message: str = "LLM processing failed")
  │     Example: LLMError(f"Intent detection failed: {e}")
  │
  ├── DatabaseError (500)
  │     Database operation failure (connection, query, transaction, etc.)
  │     Constructor: DatabaseError(message: str = "Database operation failed")
  │     Example: DatabaseError("Failed to create presentation")
  │
  └── ExternalServiceError (502)
        Third-party API or SMTP failure
        Constructor: ExternalServiceError(service: str, message: str = "")
        Example: ExternalServiceError("WeatherAPI", "Connection timeout")
                 → "WeatherAPI error: Connection timeout"
```

### 2.2. Quick reference table

| Exception | HTTP Code | Raised When |
|-----------|-----------|-------------|
| `AuthenticationError` | 401 | Wrong credentials, invalid/expired token, user not found during auth |
| `NotFoundError` | 404 | Resource doesn't exist (conversation, presentation, user) |
| `AccessDeniedError` | 403 | User doesn't own the resource, or `user_id` context missing |
| `ValidationError` | 422 | Missing required field, invalid input, business rule violation |
| `LLMError` | 502 | OpenAI call failed, response parse failed, quota exceeded |
| `DatabaseError` | 500 | DB insert/update/query failed unexpectedly |
| `ExternalServiceError` | 502 | Weather API, Stock API, SMTP, or other third-party failure |

---

## 3. Two Separate Error Handling Patterns

The system uses **two distinct approaches** to error handling, depending on which layer is handling the request:

### 3.1. REST API endpoints (Auth, Conversations, Presentations)

REST endpoints delegate business logic to service functions. Services raise `AppException` subclasses on failure. A **global exception handler** registered in `main.py` catches these and converts them into HTTP responses automatically — routers do not need explicit `try/except` blocks.

```
  POST /auth/login
         │
         ▼
  Router calls auth_service.login(email, password, db)
         │
         ▼
  Service raises AuthenticationError("Invalid email or password")
         │
         ▼
  Global handler in main.py catches AppException:
    → JSONResponse(status_code=401, content={"detail": "Invalid email or password"})
```

The global handler in `main.py`:

```python
@app.exception_handler(AppException)
async def app_exception_handler(request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )
```

Examples of exceptions raised by services:

```python
# services/auth_service.py
raise ValidationError("Email already registered")       # 422
raise AuthenticationError("Invalid email or password")  # 401
raise DatabaseError("Failed to create user")            # 500

# services/conversation_service.py
raise NotFoundError("Conversation", conversation_id)    # 404
raise AccessDeniedError("Unable to verify ownership")   # 403
```

### 3.2. Workflow endpoint (`POST /workflows/chat/run`)

The workflow router uses a **two-tier exception catch** to handle both known application errors and unexpected system errors:

```python
# routers/workflow.py
try:
    result = await handler        # run ChatWorkflow
    return { "status": "completed", "result": ... }

except AppException as e:         # known application error
    logger.warning("workflow_error", error_type=type(e).__name__, detail=e.message)
    return JSONResponse(
        status_code=e.status_code,
        content={"status": "error", "error": e.message}
    )

except Exception as e:            # unexpected internal error
    logger.error("workflow_unexpected_error", ...)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "error": ERROR_GENERAL}
    )
```

**Key difference between REST and Workflow:**

| | REST Endpoints | Workflow Endpoint |
|-|----------------|-------------------|
| Error class used | `AppException` subclasses (via service) | `AppException` subclasses |
| Catch location | Global handler in `main.py` | Explicit `try/except` in router |
| Unexpected error message | Global handler → HTTP 500 | `ERROR_GENERAL` constant (generic) |
| Error format | `{"detail": "..."}` | `{"status": "error", "error": "..."}` |

---

## 4. Workflow Error Handling: Graceful Degradation Pattern

Not all errors inside the workflow raise an exception. Some failures — particularly LLM call failures and database save failures — are handled with a **graceful degradation** approach: instead of crashing, the workflow saves a friendly error message to the database and returns it to the user as if it were a normal assistant response.

```
  Inside ChatWorkflow step:
  ─────────────────────────────────────────────────────────
  try:
    result = await llm.achat(...)       ← could fail
    ...
  except Exception as e:
    logger.error("step_failed", ...)
    result = await save_error_response(
        conversation_id, db,
        content=error_output.answer,    ← friendly message
        result_dict=error_output.model_dump(),
        memory=memory, ctx=ctx
    )
    return StopEvent(result=result)     ← workflow ends gracefully
```

### 4.1. `save_error_response()` utility

Defined in `app/services/message_service.py`. Called when workflow steps catch an unexpected exception and want to return a graceful response:

```
  save_error_response(conversation_id, db, content, result_dict, memory, ctx)
         │
         ▼
  Save assistant message to DB:
  { role: "assistant", intent: "GENERAL",
    content: ERROR_GENERAL, metadata: { error_fallback: True } }
         │
         ▼
  (if memory provided) Add to ChatMemoryBuffer
  (if ctx provided) Update ctx.store["chat_history"]
         │
         ▼
  Return result_dict  ← used as StopEvent result
```

The `metadata.error_fallback: True` flag marks the message as an error response in the database — useful for debugging without exposing error details to the user.

### 4.2. Raise vs. Graceful degradation — decision boundary

```
  Exception occurs inside workflow step
         │
         ├─── Is it an AppException (AccessDeniedError, ValidationError, etc.)?
         │         │
         │         ▼
         │    Bubble up (re-raise or let propagate)
         │    → caught at workflow router level
         │    → returns HTTP response with e.status_code
         │
         └─── Is it an unexpected Exception (LLM timeout, DB write fail, etc.)?
                   │
                   ▼
              Graceful degradation:
              save_error_response() → StopEvent(result=error_output)
              → returns HTTP 200 with friendly error text in "answer" field
              → user sees "Sorry, I encountered an error..." in chat
```

**Applied in workflow steps:**

| Step / Phase | Error type | Handling |
|---|---|---|
| `security_check` — LLM call fails | Unexpected `Exception` | Fail-open: allow request to continue to next step |
| `route_and_answer` — LLM call fails | Unexpected `Exception` | Graceful degradation: `save_error_response` |
| `route_and_answer` — tool call fails | Unexpected `Exception` | Graceful degradation |
| `route_and_answer` — save message fails | Unexpected `Exception` | Graceful degradation |
| `generate_slide` — LLM call fails | Unexpected `Exception` | Graceful degradation |
| `generate_slide` — DB save fails | `DatabaseError` | Graceful degradation |
| `generate_slide` — missing `target_presentation_id` | `ValidationError` | Re-raised (bubble up to router) |
| `security_check` / `route_and_answer` — missing `user_id` | `AccessDeniedError` | Re-raised (bubble up to router) |

> **Special case — `security_check` LLM failure:** if the security classification call fails, the system intentionally **allows the request to proceed** to `route_and_answer`. This is a fail-open design: it's better to process a potentially risky request than to block all users when the security LLM is unavailable.

---

## 5. Exception Flow by Layer

```
  ┌─────────────────────────────────────────────────────────────┐
  │  Router Layer                                               │
  │  (routers/workflow.py)                                      │
  │                                                             │
  │  catch AppException  → HTTP e.status_code, e.message        │
  │  catch Exception     → HTTP 500, ERROR_GENERAL              │
  └───────────────────────────┬─────────────────────────────────┘
                              │ raise (bubbles up)
  ┌───────────────────────────▼─────────────────────────────────┐
  │  Workflow Layer                                             │
  │  (workflows/workflow.py)                                    │
  │                                                             │
  │  raise AccessDeniedError — user_id missing/invalid          │
  │  raise ValidationError   — missing required field           │
  │  raise DatabaseError     — DB save returned None            │
  │                                                             │
  │  catch Exception → graceful degradation (save_error_response│
  └───────────────────────────┬─────────────────────────────────┘
                              │ raise (bubbles up)
  ┌───────────────────────────▼─────────────────────────────────┐
  │  Service Layer                                              │
  │  (services/chat_service.py, services/presentation_service)  │
  │                                                             │
  │  raise NotFoundError     — resource doesn't exist           │
  │  raise AccessDeniedError — ownership check failed           │
  │  raise LLMError          — intent detection LLM failed      │
  └───────────────────────────┬─────────────────────────────────┘
                              │ raise (bubbles up)
  ┌───────────────────────────▼─────────────────────────────────┐
  │  Repository Layer                                           │
  │  (repositories/conversation_repository.py, etc.)            │
  │                                                             │
  │  raise DatabaseError     — DB operation failed (w/ from e)  │
  │  return None             — "soft" not found (caller checks) │
  └─────────────────────────────────────────────────────────────┘
```

### 5.1. Who raises — who catches

| Exception | Raised by | Caught by | Client sees |
|-----------|-----------|-----------|-------------|
| `AuthenticationError` | Auth Service | Global handler (`main.py`) | HTTP 401 `{"detail": "Invalid email or password"}` |
| `NotFoundError` | Service | Workflow router / Global handler | HTTP 404 `{"error": "Conversation not found: abc"}` |
| `AccessDeniedError` | Workflow, Service | Workflow router | HTTP 403 `{"error": "Access denied"}` |
| `ValidationError` | Workflow | Workflow router | HTTP 422 `{"error": "target_presentation_id required..."}` |
| `LLMError` | Service | Workflow router | HTTP 502 `{"error": "LLM processing failed"}` |
| `DatabaseError` | Repository, Workflow, Auth Service | Workflow router / Global handler | HTTP 500 `{"error": "Database operation failed"}` |
| `ExternalServiceError` | Tools / Services | Workflow router | HTTP 502 `{"error": "WeatherAPI error: ..."}` |
| Unexpected `Exception` | Anywhere | Workflow router / Global handler | HTTP 500 `{"detail": "Internal server error"}` |

---

## 6. Error Cause Preservation (`from e` chaining)

When re-raising exceptions from caught errors, the system uses Python's `raise XxxError(...) from e` syntax to preserve the original exception as the cause:

```python
# repositories/conversation_repository.py
try:
    db.add(conversation)
    db.commit()
except Exception as e:
    raise DatabaseError(f"Failed to create conversation: {e}") from e

# services/chat_service.py
try:
    conversation = get_conversation_by_id(conversation_id, user_id, db)
    if not conversation:
        raise NotFoundError("Conversation", conversation_id)
except NotFoundError:
    raise                  # re-raise as-is (already correct type)
except Exception as e:
    raise AccessDeniedError("Unable to verify conversation ownership") from e
```

**Why this matters:**

```
  Original exception (e):        sqlalchemy.exc.IntegrityError
         │ preserved as __cause__
         ▼
  Re-raised as:                  DatabaseError("Failed to create conversation: ...")
         │ logged by router
         ▼
  Full traceback visible in logs, including original cause
  Client only sees: "Database operation failed"
```

Logging uses `logger.exception()` or `logger.error()` with structured fields — the full stack trace (including `__cause__`) is captured in Loki/Grafana without exposing internal details to the client.

---

## 7. `error_output` Fallback Constant

A module-level singleton is defined in `workflow.py` as the default error response content:

```python
# workflows/workflow.py
error_output = RouterOutput(
    intent="GENERAL",
    answer=ERROR_GENERAL,
)
```

Where `ERROR_GENERAL` is defined in `app/config/prompts.py`:

```
ERROR_GENERAL = "Sorry, I encountered an error processing your request. Please try again."
```

This constant is used as the `content` and `result_dict` arguments to every `save_error_response()` call inside the workflow:

```
  save_error_response(
      conversation_id=...,
      db=...,
      content=error_output.answer,        ← ERROR_GENERAL string
      result_dict=error_output.model_dump(),  ← {"intent": "GENERAL", "answer": ERROR_GENERAL}
      memory=memory,
      ctx=ctx
  )
```

**Design intent:**
- The user **always sees the same generic message** regardless of the actual internal error — no stack traces, no DB error details, no LLM failure reasons
- The **actual error** is fully logged with `logger.error(...)` including `error_type` and `error_message` fields for debugging in Grafana
- `metadata: { "error_fallback": True }` on the saved DB message allows post-hoc identification of error turns in the conversation history
