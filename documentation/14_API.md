# API Reference

## Authentication

All protected endpoints require:
```
Authorization: Bearer <access_token>
```

Refresh token is stored in an **httpOnly cookie** (path `/auth`, not sent automatically to other paths).

---

## 1. Authentication (`/auth`)

### `POST /auth/register`

Register a new account with email and password.

**Request body:**
```json
{
  "email": "user@example.com",
  "password": "mypassword",
  "name": "John Doe"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | Valid email address |
| `password` | string | Yes | Min 6 characters |
| `name` | string | No | Display name |

**Response `200`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": "7cdadd1d-5238-4d48-af36-d011ee5ce131",
  "email": "user@example.com"
}
```
Cookie set: `refresh_token=<token>; HttpOnly; Path=/auth`

**Errors:**
- `400` — Email already registered

---

### `POST /auth/login`

Login with email and password.

**Request body:**
```json
{
  "email": "user@example.com",
  "password": "mypassword"
}
```

**Response `200`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": "7cdadd1d-5238-4d48-af36-d011ee5ce131",
  "email": "user@example.com"
}
```
Cookie set: `refresh_token=<token>; HttpOnly; Path=/auth`

**Errors:**
- `401` — Invalid email or password
- `401` — Account registered via Google (no password)

---

### `POST /auth/refresh`

Get a new access token using the refresh token stored in cookie. No request body needed — reads from cookie automatically.

**Cookie required:** `refresh_token`

**Response `200`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": "7cdadd1d-5238-4d48-af36-d011ee5ce131",
  "email": "user@example.com"
}
```

**Errors:**
- `401` — No refresh token cookie found
- `401` — Invalid or expired refresh token
- `401` — Token has been revoked (blacklisted after signout)
- `401` — User not found

---

### `POST /auth/signout`

Sign out by blacklisting the refresh token and clearing the cookie. No request body needed.

**Cookie required:** `refresh_token`

**Response `200`:**
```json
{
  "message": "Successfully signed out"
}
```
Cookie deleted: `refresh_token`

---

### `GET /auth/me`

Get current authenticated user information.

**Auth:** Bearer token required

**Response `200`:**
```json
{
  "user_id": "7cdadd1d-5238-4d48-af36-d011ee5ce131",
  "email": "user@example.com",
  "name": "John Doe",
  "avatar_url": "https://lh3.googleusercontent.com/...",
  "providers": ["email"],
  "email_verified": false,
  "created_at": "2026-02-20T16:22:46.819914Z"
}
```

**Errors:**
- `401` — Invalid or missing token

---

### `GET /auth/google`

Get Google OAuth authorization URL. Frontend redirects user to this URL to initiate OAuth flow.

**Response `200`:**
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "state": "a3f9bc12d4e8"
}
```

---

### `GET /auth/callback`

Google OAuth callback — called by Google after user authorizes. Not called directly by frontend.

**Query params:**

| Param | Type | Description |
|-------|------|-------------|
| `code` | string | Authorization code from Google |
| `state` | string | CSRF state token |

**Response:** `302 RedirectResponse`
- Success → `{FRONTEND_URL}/auth/callback?access_token=<token>` + cookie set
- Failure → `{FRONTEND_URL}/login?error=<reason>`

---

### `GET /auth/check-providers`

Check which authentication providers are registered for an email. Used by frontend login page to show the correct login options.

**Query params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | Email to check |

**Response `200`:**
```json
{
  "providers": ["email", "google"]
}
```

Possible values in `providers`: `"email"`, `"google"`. Returns `["email", "google"]` if email is not registered yet.

---

### `POST /auth/forgot-password`

Request a password reset email. Always returns `200` regardless of whether the email exists (prevents email enumeration).

**Request body:**
```json
{
  "email": "user@example.com"
}
```

**Response `200`:**
```json
{
  "message": "If an account exists with that email, you will receive a reset link."
}
```

> Note: Only works for accounts registered with `"email"` provider. Google OAuth accounts have no password.

---

### `GET /auth/verify-reset-token`

Verify that a password reset token is still valid. Used by frontend to check before showing the reset password form.

**Query params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `token` | string | Yes | Reset token from email link |

**Response `200`:**
```json
{
  "valid": true
}
```

**Errors:**
- `400` — Invalid or expired reset token (15 min expiry)

---

### `POST /auth/reset-password`

Set a new password using the reset token from email.

**Request body:**
```json
{
  "token": "abc123def456...",
  "new_password": "mynewpassword"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `token` | string | Yes | Reset token from email link |
| `new_password` | string | Yes | New password, min 6 characters |

**Response `200`:**
```json
{
  "message": "Password reset successful. Please login with your new password."
}
```

**Errors:**
- `400` — Invalid or expired reset token
- `500` — Failed to update password

---

## 2. Conversations (`/api/conversations`)

All endpoints require `Authorization: Bearer <access_token>`. All data is scoped to the authenticated user — other users' conversations are never returned.

---

### `GET /api/conversations`

Get all conversations for the current user, ordered by most recent first.

**Response `200`:**
```json
[
  {
    "id": "ba4fef4d-439d-40fa-8bb8-a14da06275ba",
    "user_id": "7cdadd1d-5238-4d48-af36-d011ee5ce131",
    "title": "Artificial Intelligence Overview",
    "active_presentation_id": "c1e2f3a4-...",
    "created_at": "2026-02-20T16:22:46.819914Z",
    "updated_at": "2026-02-20T16:25:10.123456Z"
  }
]
```

---

### `GET /api/conversations/{conversation_id}`

Get a single conversation by ID.

**Path params:**

| Param | Type | Description |
|-------|------|-------------|
| `conversation_id` | UUID | Conversation ID |

**Response `200`:**
```json
{
  "id": "ba4fef4d-439d-40fa-8bb8-a14da06275ba",
  "user_id": "7cdadd1d-5238-4d48-af36-d011ee5ce131",
  "title": "Artificial Intelligence Overview",
  "active_presentation_id": null,
  "created_at": "2026-02-20T16:22:46.819914Z",
  "updated_at": "2026-02-20T16:22:46.819914Z"
}
```

**Errors:**
- `404` — Conversation not found or does not belong to current user

---

### `GET /api/conversations/{conversation_id}/exists`

Check if a conversation exists and belongs to the current user. Used by frontend to validate a stored conversation ID before loading.

**Path params:**

| Param | Type | Description |
|-------|------|-------------|
| `conversation_id` | UUID | Conversation ID |

**Response `200`:**
```json
{
  "exists": true
}
```

---

### `PATCH /api/conversations/{conversation_id}`

Update a conversation's title.

**Path params:**

| Param | Type | Description |
|-------|------|-------------|
| `conversation_id` | UUID | Conversation ID |

**Request body:**
```json
{
  "title": "New Conversation Title"
}
```

**Response `200`:** Updated conversation object (same as `GET /api/conversations/{id}`)

**Errors:**
- `404` — Conversation not found or does not belong to current user

---

### `DELETE /api/conversations/{conversation_id}`

Delete a conversation and all its associated data (messages, summaries, presentations, presentation pages, version history).

**Path params:**

| Param | Type | Description |
|-------|------|-------------|
| `conversation_id` | UUID | Conversation ID |

**Response `204`:** No content

**Errors:**
- `404` — Conversation not found or does not belong to current user

---

### `GET /api/conversations/{conversation_id}/messages`

Get all messages in a conversation, ordered oldest first. Includes both working memory and summarized messages.

**Path params:**

| Param | Type | Description |
|-------|------|-------------|
| `conversation_id` | UUID | Conversation ID |

**Response `200`:**
```json
[
  {
    "id": "msg-uuid-...",
    "conversation_id": "ba4fef4d-...",
    "role": "user",
    "content": "Create a slide about AI",
    "intent": null,
    "metadata": null,
    "created_at": "2026-02-20T16:22:51.538440Z"
  },
  {
    "id": "msg-uuid-...",
    "conversation_id": "ba4fef4d-...",
    "role": "assistant",
    "content": "I've created a 5-page presentation about Artificial Intelligence.",
    "intent": "PPTX",
    "metadata": {
      "slide_id": "c1e2f3a4-...",
      "topic": "Artificial Intelligence",
      "total_pages": 5,
      "pages": [
        {
          "page_number": 1,
          "page_title": "Introduction",
          "html_content": "<!DOCTYPE html>..."
        }
      ]
    },
    "created_at": "2026-02-20T16:22:55.327998Z"
  }
]
```

**`intent` values:**
- `null` — user messages
- `"GENERAL"` — regular assistant text response
- `"PPTX"` — assistant response containing slide data in `metadata`

---

### `GET /api/conversations/{conversation_id}/active-presentation`

Get the active (most recently created/edited) presentation ID for a conversation.

**Path params:**

| Param | Type | Description |
|-------|------|-------------|
| `conversation_id` | UUID | Conversation ID |

**Response `200`:**
```json
{
  "presentation_id": "c1e2f3a4-b5d6-7890-abcd-ef1234567890"
}
```

Returns `null` for `presentation_id` if no presentation exists in the conversation:
```json
{
  "presentation_id": null
}
```

---

## 3. Presentations (`/api/presentations`)

Read-only endpoints for version history. Presentations are created and modified exclusively through `POST /workflows/chat/run`.

All endpoints require `Authorization: Bearer <access_token>`.

---

### `GET /api/presentations/{presentation_id}/versions`

Get all versions of a presentation, including metadata about what user request produced each version.

**Path params:**

| Param | Type | Description |
|-------|------|-------------|
| `presentation_id` | UUID | Presentation ID |

**Response `200`:**
```json
[
  {
    "version": 3,
    "total_pages": 5,
    "is_current": true,
    "user_request": "Change the color scheme to dark mode",
    "created_at": "2026-02-20T16:30:00.000000Z",
    "timestamp": "2026-02-20T16:30:00.000000Z"
  },
  {
    "version": 2,
    "total_pages": 5,
    "is_current": false,
    "user_request": "Edit the introduction page",
    "created_at": "2026-02-20T16:25:00.000000Z",
    "timestamp": "2026-02-20T16:25:00.000000Z"
  },
  {
    "version": 1,
    "total_pages": 3,
    "is_current": false,
    "user_request": "Create a slide about AI",
    "created_at": "2026-02-20T16:22:55.000000Z",
    "timestamp": "2026-02-20T16:22:55.000000Z"
  }
]
```

> `timestamp` is an alias for `created_at` — both fields contain the same value for frontend compatibility.

**Errors:**
- `404` — Presentation not found or does not belong to current user

---

### `GET /api/presentations/{presentation_id}/versions/{version}`

Get the full page content of a specific version.

**Path params:**

| Param | Type | Description |
|-------|------|-------------|
| `presentation_id` | UUID | Presentation ID |
| `version` | integer | Version number (e.g. `1`, `2`, `3`) |

**Response `200`:**
```json
{
  "total_pages": 3,
  "pages": [
    {
      "page_number": 1,
      "page_title": "Introduction",
      "html_content": "<!DOCTYPE html><html>...</html>"
    },
    {
      "page_number": 2,
      "page_title": "What is AI?",
      "html_content": "<!DOCTYPE html><html>...</html>"
    },
    {
      "page_number": 3,
      "page_title": "Conclusion",
      "html_content": "<!DOCTYPE html><html>...</html>"
    }
  ]
}
```

> For `is_current = true` versions, pages are read from `presentation_pages`. For archived versions, pages are read from `presentation_version_pages`.

**Errors:**
- `404` — Version not found

---

## 4. Workflow (`/workflows`)

### `POST /workflows/chat/run`

The main endpoint for all AI interactions — chat, slide generation, and slide editing. This single endpoint handles all user inputs.

**Auth:** Bearer token required

**Request body:**
```json
{
  "start_event": {
    "user_input": "Create a slide about machine learning",
    "conversation_id": "ba4fef4d-439d-40fa-8bb8-a14da06275ba"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `start_event.user_input` | string | Yes | The user's message. Cannot be empty or whitespace |
| `start_event.conversation_id` | UUID | No | Existing conversation ID. Omit or set `null` to start a new conversation |

---

**Success response `200` — `intent: GENERAL` (regular chat):**
```json
{
  "status": "completed",
  "result": {
    "value": {
      "result": {
        "intent": "GENERAL",
        "answer": "Machine learning is a subset of AI...",
        "conversation_id": "ba4fef4d-...",
        "title": "Machine Learning Basics"
      }
    }
  }
}
```

> `conversation_id` and `title` are only present when a **new** conversation was created (i.e., `conversation_id` was not provided in the request).

---

**Success response `200` — `intent: PPTX` (slide created/edited):**
```json
{
  "status": "completed",
  "result": {
    "value": {
      "result": {
        "intent": "PPTX",
        "answer": "I've created a 5-page presentation about Machine Learning.",
        "topic": "Machine Learning Fundamentals",
        "slide_id": "c1e2f3a4-b5d6-7890-abcd-ef1234567890",
        "total_pages": 5,
        "pages": [
          {
            "page_number": 1,
            "page_title": "Introduction",
            "html_content": "<!DOCTYPE html><html>...</html>"
          },
          {
            "page_number": 2,
            "page_title": "What is Machine Learning?",
            "html_content": "<!DOCTYPE html><html>...</html>"
          }
        ],
        "conversation_id": "ba4fef4d-...",
        "title": "Machine Learning Slide"
      }
    }
  }
}
```

---

**Success response `200` — `intent: SYSTEM_EXPLOIT` (security rejection):**
```json
{
  "status": "completed",
  "result": {
    "value": {
      "result": {
        "intent": "SYSTEM_EXPLOIT",
        "answer": "I'm sorry, I can't help with that request.",
        "conversation_id": "ba4fef4d-..."
      }
    }
  }
}
```

---

**Response fields summary:**

| Field | Present when | Description |
|-------|-------------|-------------|
| `intent` | Always | `GENERAL`, `PPTX`, or `SYSTEM_EXPLOIT` |
| `answer` | Always | Text response shown to user in chat |
| `conversation_id` | New conversation created | ID of the newly created conversation |
| `title` | New conversation created | Auto-generated title for the new conversation |
| `topic` | `intent = PPTX` | Presentation topic/title |
| `slide_id` | `intent = PPTX` | Presentation UUID for version history queries |
| `total_pages` | `intent = PPTX` | Number of pages in the presentation |
| `pages` | `intent = PPTX` | Array of page objects with `page_number`, `page_title`, `html_content` |

---

**Error responses:**

`422` — Empty user input:
```json
{
  "status": "error",
  "error": "user_input is required and cannot be empty"
}
```

`403` — Authentication context missing:
```json
{
  "status": "error",
  "error": "user_id is missing or invalid. Authentication failed."
}
```

`500` — Unexpected internal error:
```json
{
  "status": "error",
  "error": "Sorry, I encountered an error processing your request. Please try again."
}
```

---

## 5. Utility Endpoints

### `GET /health`

Health check endpoint. Not logged.

**Response `200`:**
```json
{
  "status": "ok",
  "version": "2.0.0"
}
```

---

### `GET /`

Root info endpoint.

**Response `200`:**
```json
{
  "message": "Agent Chat API",
  "version": "2.0.0",
  "docs": "/docs",
  "health": "/health"
}
```

