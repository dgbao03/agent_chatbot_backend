# Authentication

## 1. Overview

The system supports two authentication methods:

- **Email/Password** — classic registration and login with bcrypt-hashed passwords
- **Google OAuth 2.0** — sign in with Google using Authorization Code Flow

Both methods produce the same token pair on success:
- **Access token** — short-lived JWT returned in the response body; used by the frontend on every API call
- **Refresh token** — long-lived JWT stored in an `httpOnly` cookie; used to obtain a new access token without re-login

---

## 2. Token Strategy

### 2.1. Two-token model

```
  Login / Register / OAuth
           │
           ▼
  ┌───────────────────────┐     ┌──────────────────────────────┐
  │   Access Token (JWT)  │     │   Refresh Token (JWT)        │
  │   Expires: 30 min     │     │   Expires: 7 days            │
  │   Stored: FE memory   │     │   Stored: httpOnly cookie    │
  │   Used: Bearer header │     │   Used: POST /auth/refresh   │
  └───────────────────────┘     └──────────────────────────────┘
```

- Access token is short-lived — reduces exposure window if leaked
- Refresh token is in an `httpOnly` cookie — JavaScript cannot read it, mitigating XSS attacks
- The refresh token cookie is scoped to `path=/auth` — only sent on requests to `/auth/*` endpoints

### 2.2. JWT payload structure

Both tokens share the same payload structure but use **separate secret keys** and different `type` values:

```json
{
  "sub": "<user_id>",
  "type": "access" | "refresh",
  "exp": <unix_timestamp>,
  "jti": "<uuid4>"
}
```

- `sub` — user UUID (used for all authorization checks)
- `type` — prevents a refresh token from being used as an access token and vice versa
- `exp` — expiry enforced by the JWT library
- `jti` — unique JWT ID; used to blacklist specific refresh tokens on sign out

### 2.3. Token lifecycle

```
  User logs in
       │
       ▼
  Access token issued (30 min)
  Refresh token issued (7 days, httpOnly cookie)
       │
       │  [Access token expires]
       ▼
  POST /auth/refresh
  → Server reads refresh token from cookie
  → Verifies, checks blacklist
  → Issues new access token
       │
       │  [User signs out]
       ▼
  POST /auth/signout
  → Cookie cleared
  → Refresh token jti added to blacklist
  → Refresh token can no longer be used
```

---

## 3. Email/Password Authentication

### 3.1. Registration

```
  POST /auth/register
  { email, password, name }
         │
         ▼
  Check if email already exists
         │  [exists] → 422 Email already registered
         │
         ▼
  hash_password(password)   ← bcrypt with auto-generated salt
         │
         ▼
  create_user({ email, hashed_password, name, providers: ['email'] })
         │
         ▼
  create_access_token(user_id)
  create_refresh_token(user_id)
         │
         ▼
  Response:
    Body   → { access_token, user_id, email }
    Cookie → refresh_token (httpOnly, path=/auth, 7 days)
```

### 3.2. Login

```
  POST /auth/login
  { email, password }
         │
         ▼
  get_user_by_email(email)
         │  [not found] → 401 Invalid email or password
         │
         ▼
  Check user has hashed_password
         │  [null — OAuth-only account] → 401 Invalid login method
         │
         ▼
  verify_password(plain, hashed)   ← bcrypt.checkpw
         │  [mismatch] → 401 Invalid email or password
         │
         ▼
  create_access_token + create_refresh_token
         │
         ▼
  Response: same as register
```

> Login failures always return the same generic message (`"Invalid email or password"`) regardless of whether the email exists or the password is wrong — prevents user enumeration.

---

## 4. Google OAuth 2.0

### 4.1. Flow overview

The system uses the **Authorization Code Flow**:

```
  FE                    Backend                    Google
   │                       │                          │
   │── GET /auth/google ──▶│                          │
   │                       │ generate state token      │
   │◀── { authorization_url, state } ─────────────────│
   │                       │                          │
   │── redirect user ─────────────────────────────────▶│
   │                       │          user logs in    │
   │◀─────────────────────────────── redirect to      │
   │                       │         /auth/callback   │
   │                       │◀── ?code=...&state=... ──│
   │                       │                          │
   │                       │── exchange code ─────────▶│
   │                       │◀── access_token ─────────│
   │                       │                          │
   │                       │── get user info ─────────▶│
   │                       │◀── { email, name, picture}│
   │                       │                          │
   │                       │ get_or_create_oauth_user  │
   │                       │ create JWT tokens         │
   │                       │                          │
   │◀── redirect to FE /auth/callback?access_token=...─│
   │    + refresh_token cookie                        │
```

### 4.2. CSRF protection

A random `state` token (`secrets.token_urlsafe(32)`) is generated when building the authorization URL. Google echoes it back in the callback — the frontend is responsible for verifying the state matches to prevent CSRF attacks.

### 4.3. User account merging

`get_or_create_oauth_user` handles two scenarios:

```
  Google callback received
           │
           ▼
  get_user_by_email(email)
           │
     ┌─────┴──────┐
     │            │
  [exists]    [not exists]
     │            │
     ▼            ▼
  Add 'google'   Create new user
  to providers   providers: ['google']
  array if not   hashed_password: null
  already there  email_verified: true
  Update profile  │
  if fields empty │
     │            │
     └─────┬──────┘
           ▼
  Issue JWT tokens
  Redirect to FE /auth/callback?access_token=...
```

- If the user previously registered with email/password using the same email, Google is added to their `providers` array — the account is not duplicated
- OAuth users have `hashed_password = null` and cannot use email/password login
- `email_verified` is always set to `true` for OAuth users (Google verifies the email)

---

## 5. Token Refresh

```
  POST /auth/refresh
  (refresh token read from httpOnly cookie)
         │
         ▼
  Cookie exists?
         │  [no] → 401 Refresh token not found
         │
         ▼
  verify_refresh_token(token)
         │  [invalid/expired] → 401 Invalid refresh token
         │
         ▼
  Extract jti from payload
  is_token_blacklisted(jti)?
         │  [yes] → 401 Token has been revoked
         │
         ▼
  get_user_by_id(user_id) — confirm user still exists
         │  [not found] → 401 User not found
         │
         ▼
  create_access_token(user_id)
         │
         ▼
  Response:
    Body → { access_token, user_id, email }
    (refresh token cookie is NOT changed)
```

> Refresh token rotation (issuing a new refresh token on each refresh) is **not** implemented. The same refresh token remains valid until sign out or natural expiry.

---

## 6. Sign Out & Token Blacklist

### 6.1. Sign out flow

```
  POST /auth/signout
         │
         ▼
  Read refresh token from cookie
         │
         ▼
  Delete refresh token cookie (path=/auth)
         │
         ▼
  verify_refresh_token(token)
  Extract jti, exp, user_id
         │
         ▼
  add_token_to_blacklist(jti, user_id, 'refresh', expires_at)
  ← stores jti in token_blacklist table
         │
         ▼
  200 { message: "Successfully signed out" }
```

- Cookie is deleted regardless of whether blacklisting succeeds — sign out always completes from the user's perspective
- Blacklisting is **best-effort**: if token parsing fails, the cookie is still cleared

### 6.2. Why blacklist by jti

JWT tokens are stateless — the server cannot invalidate them directly after issuance. By storing the `jti` (unique JWT ID) of revoked tokens, the server can reject a stolen refresh token even if it has not yet expired.

Only **refresh tokens** are blacklisted. Access tokens are short-lived (30 min) and not blacklisted — the risk window is acceptable.

---

## 7. Forgot Password / Reset Password

### 7.1. Full flow

```
  POST /auth/forgot-password
  { email }
         │
         ▼
  get_user_by_email(email)
  Check 'email' in user.providers
         │  [not found / OAuth-only]
         ▼
  Always return 200             ← anti-enumeration: never reveal if email exists
         │  [found, email provider]
         ▼
  create_token(user_id, expires_minutes=15)
  ← generates secrets.token_urlsafe(32)
  ← stored in password_reset_tokens table
         │
         ▼
  send_password_reset_email(email, reset_link)
  ← async SMTP via aiosmtplib
  ← link: {FRONTEND_URL}/reset-password?token=...
         │
         ▼
  200 { message: "If an account exists..." }

  ───────────────────────────────────────────────

  GET /auth/verify-reset-token?token=...
         │
         ▼
  get_valid_token(token)
  ← checks: not expired, not used
         │  [invalid] → 400
         ▼
  200 { valid: true }

  ───────────────────────────────────────────────

  POST /auth/reset-password
  { token, new_password }
         │
         ▼
  get_valid_token(token)
         │  [invalid] → 422 Invalid or expired reset link
         ▼
  hash_password(new_password)
  update_user(user_id, { hashed_password })
         │
         ▼
  mark_token_used(token)
  ← sets used_at = now()
  ← token becomes permanently invalid
         │
         ▼
  200 { message: "Password reset successful" }
```

### 7.2. Token validity rules

A password reset token is considered valid only when **all three** conditions are met:
- Token string exists in the database
- `expires_at > now()` — not expired (15 minutes from creation)
- `used_at IS NULL` — not yet used

The DB check constraint `used_at <= expires_at` ensures a token can never be marked as used after it has already expired.

### 7.3. SMTP configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server hostname |
| `SMTP_PORT` | `587` | `587` = STARTTLS, `465` = SSL/TLS |
| `SMTP_USER` | — | SMTP username |
| `SMTP_PASSWORD` | — | SMTP password |
| `SMTP_FROM_EMAIL` | same as `SMTP_USER` | Sender email |
| `SMTP_FROM_NAME` | `Chat Assistant` | Sender display name |

If SMTP is not configured, `send_password_reset_email` returns `False` silently — the endpoint still returns 200.

---

## 8. Auth Context (ContextVar)

### 8.1. Problem

FastAPI routers receive `user_id` via `Depends(get_current_user)` and can pass it explicitly to repository functions. However, **LlamaIndex Workflow** executes steps as async tasks — there is no clean way to pass `user_id` as a parameter across workflow steps.

### 8.2. Solution: Python ContextVar

`app/auth/context.py` uses Python's `contextvars.ContextVar` to store `user_id` and `db` session in the context of the current async execution — accessible anywhere within the same request lifecycle without explicit parameter passing.

```
  POST /workflows/chat/run
         │
         ▼
  get_current_user()                ← FastAPI dependency
  extracts user_id from JWT
         │
         ▼
  set_current_user_id(user_id)      ← stored in ContextVar
  set_current_db_session(db)        ← stored in ContextVar
         │
         ▼
  ChatWorkflow.run()
         │
         ├── security_check step
         │   └── get_current_user_id()   ← reads from ContextVar
         │
         ├── route_and_answer step
         │   └── get_current_user_id()   ← reads from ContextVar
         │
         └── generate_slide step
             └── get_current_user_id()   ← reads from ContextVar
         │
         ▼
  finally:
  clear_current_user_id()           ← cleaned up after every request
  clear_current_db_session()
```

ContextVar is safe for async concurrent requests — each async task has its own context copy, so values from different simultaneous requests do not interfere with each other.

---

## 9. Background Token Cleanup

Expired tokens accumulate in the database over time. A background scheduler purges them automatically every 24 hours.

### 9.1. What gets cleaned up

| Table | Condition |
|-------|-----------|
| `token_blacklist` | `expires_at < now()` — token has naturally expired, blacklist entry is no longer needed |
| `password_reset_tokens` | `expires_at < now()` OR `used_at IS NOT NULL` — token is expired or already used |

### 9.2. Scheduler lifecycle

```
  Server startup (lifespan)
         │
         ▼
  start_scheduler()
  ← APScheduler BackgroundScheduler
  ← job: run_cleanup, interval: every 24h
         │
         ▼
  Server running...
  [every 24h] run_cleanup() executes:
    cleanup_expired_tokens(db)
    cleanup_expired_reset_tokens(db)
         │
         ▼
  Server shutdown (lifespan)
         │
         ▼
  stop_scheduler()   ← graceful shutdown, wait=False
```

The scheduler runs inside the FastAPI process — no external cron job or separate worker is needed.
