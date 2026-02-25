# Presentation

## 1. Overview

A **Presentation** in this system is an AI-generated HTML slide deck embedded directly in the chat. It is not a PowerPoint file — each slide is a self-contained HTML document rendered in the browser at **1280×720 pixels**.

Presentations are created and edited through natural language in the chat. When the LLM detects a slide intent (`PPTX`), the workflow generates or updates the presentation automatically as part of the response.

**Scope and structure:**
- A presentation belongs to exactly one conversation
- A conversation can contain multiple presentations
- Only one presentation is "active" per conversation at any time (tracked via `active_presentation_id`)
- Each presentation consists of multiple pages (3–7 pages typically)

**Presentation fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `conversation_id` | UUID | FK to `conversations` — owner |
| `topic` | VARCHAR | Presentation subject (e.g., "Artificial Intelligence Basics") |
| `total_pages` | INTEGER | Current number of pages |
| `version` | INTEGER | Current version number, starts at 1, increments on each edit |
| `metadata` | JSONB | `{ "user_request": "original prompt" }` |
| `created_at` | TIMESTAMPTZ | When first created |
| `updated_at` | TIMESTAMPTZ | Last modification time |

---

## 2. Data Model — 4 Tables

The presentation system uses 4 tables with a clear separation between **current state** and **version history**:

```
  presentations
  ┌────────────────────────────────────────────────┐
  │ id, conversation_id, topic, total_pages,       │
  │ version, metadata, created_at, updated_at      │
  └──────────────┬─────────────────────────────────┘
                 │
        ┌────────┴─────────┐
        │                  │
        ▼                  ▼
  presentation_pages    presentation_versions
  (CURRENT pages)       (ARCHIVED version metadata)
  ┌──────────────────┐  ┌──────────────────────────┐
  │ presentation_id  │  │ presentation_id          │
  │ page_number      │  │ version                  │
  │ html_content     │  │ total_pages              │
  │ page_title       │  │ user_request             │
  └──────────────────┘  └──────────┬───────────────┘
  Always reflects                  │
  the latest version               ▼
                         presentation_version_pages
                         (ARCHIVED version pages)
                         ┌──────────────────────────┐
                         │ version_id               │
                         │ page_number              │
                         │ html_content             │
                         │ page_title               │
                         └──────────────────────────┘
```

### 2.1. `presentations` table

The main record representing a single presentation. It always reflects the **current (latest) version**:

- `topic` — updated on every edit to reflect the latest topic
- `version` — current version number, incremented on every edit
- `metadata.user_request` — the user's prompt that created **this version** (overwritten on each edit)

### 2.2. `presentation_pages` table (current pages)

Contains the pages of the **current version only**. On every edit, all rows for a `presentation_id` are deleted and replaced with the new pages.

Key constraint: `UNIQUE(presentation_id, page_number)` — no duplicate page numbers within a presentation.

### 2.3. `presentation_versions` table (archived version metadata)

Stores metadata for every **previous version**. Created automatically before each edit.

Key constraint: `UNIQUE(presentation_id, version)` — each version number can only exist once per presentation.

> Note: `presentation_versions` does not have a `topic` column — only `version`, `total_pages`, and `user_request` are archived.

### 2.4. `presentation_version_pages` table (archived pages)

Stores the full page content of every archived version. Linked to `presentation_versions` via `version_id`.

Key constraint: `UNIQUE(version_id, page_number)` — no duplicate page numbers within a version.

---

## 3. Presentation Lifecycle

### 3.1. Creation (CREATE_NEW)

```
  create_presentation(presentation, pages, user_request, db)
         │
         ▼
  Verify conversation.user_id == current_user_id   ← security check
         │
         ▼
  INSERT INTO presentations
  (conversation_id, topic, total_pages, version=1, metadata={user_request})
         │
         ▼
  db.flush()   ← get presentation.id without committing
         │
         ▼
  INSERT INTO presentation_pages
  (presentation_id, page_number, html_content, page_title)
  ← one row per page
         │
         ▼
  UPDATE conversations
  SET active_presentation_id = new_presentation.id
         │
         ▼
  db.commit()
  └── returns presentation dict with id
```

### 3.2. Edit — Version Archiving

Every edit **archives the current version before replacing it**. This ensures complete history is preserved.

```
  update_presentation(presentation, new_pages, user_request, db)
         │
         ▼
  Get current presentation, verify ownership
  current_version = presentation.version  (e.g., 2)
  new_version = current_version + 1       (e.g., 3)
         │
         ▼
  ┌─────── ARCHIVE PHASE ───────────────────────────┐
  │                                                  │
  │  INSERT INTO presentation_versions              │
  │  (presentation_id, version=2, total_pages,      │
  │   user_request=old_user_request)                │
  │  db.flush()  ← get version_id                   │
  │                                                  │
  │  INSERT INTO presentation_version_pages         │
  │  (version_id, page_number, html_content,        │
  │   page_title)                                   │
  │  ← copy all current pages to archive            │
  │                                                  │
  └──────────────────────────────────────────────────┘
         │
         ▼
  ┌─────── REPLACE PHASE ───────────────────────────┐
  │                                                  │
  │  DELETE FROM presentation_pages                 │
  │  WHERE presentation_id = X                      │
  │  ← remove all old pages                         │
  │                                                  │
  │  INSERT INTO presentation_pages                 │
  │  (presentation_id, page_number, html_content,   │
  │   page_title)                                   │
  │  ← insert new pages                             │
  │                                                  │
  └──────────────────────────────────────────────────┘
         │
         ▼
  UPDATE presentations
  SET version=3, topic=new_topic,
      total_pages=new_total, metadata={user_request=new_request}
         │
         ▼
  db.commit()

  set_active_presentation(conversation_id, presentation_id)
  └── UPDATE conversations SET active_presentation_id = X
```

### 3.3. Version number progression

```
  User: "Create a slide about AI"
  → create_presentation()
  → presentations.version = 1
  → presentation_pages: [Page 1, Page 2, Page 3]
  → presentation_versions: (empty)

  User: "Edit the intro page"
  → update_presentation()
  → Archive: presentation_versions version=1, version_pages: [Page 1, Page 2, Page 3]
  → Replace: presentation_pages: [Page 1 (new), Page 2, Page 3]
  → presentations.version = 2

  User: "Change the color scheme"
  → update_presentation()
  → Archive: presentation_versions version=2, version_pages: [Page 1 (new), Page 2, Page 3]
  → Replace: presentation_pages: [Page 1 (new), Page 2 (new), Page 3 (new)]
  → presentations.version = 3
```

All previous versions remain accessible — version 1 and version 2 are still queryable via `GET /presentations/{id}/versions/{version}`.

### 3.4. Deletion

Deleting a conversation cascades through all presentation data:

```
  DELETE conversation
  → DELETE presentations (CASCADE)
      → DELETE presentation_pages (CASCADE)
      → DELETE presentation_versions (CASCADE)
          → DELETE presentation_version_pages (CASCADE)
```

---

## 4. Page Structure

Each page in a presentation is a **complete, self-contained HTML document**. External stylesheets are not used — all CSS is inline or within a `<style>` tag inside the document.

**Page dimensions:** 1280×720 pixels (landscape, matching standard slide aspect ratio)

**Page fields:**

| Field | Type | Description |
|-------|------|-------------|
| `page_number` | INTEGER | 1-based index — always starts at 1 |
| `html_content` | TEXT | Full HTML document for this slide |
| `page_title` | VARCHAR | Human-readable title (e.g., "Introduction", "Key Points") |

**Typical slide structure (from `SLIDE_GENERATION_PROMPT`):**

```
  Page 1    → Introduction / Title slide
  Page 2    → First content section
  Page 3–N  → Main content pages
  Last page → Conclusion / Key takeaways
```

**Single-page edit behavior:** When a user edits only one specific page, the LLM generates just that page. The backend merges it back:

```
  Old pages: [Page 1] [Page 2] [Page 3] [Page 4]
  LLM output: [Page 2 (new)]
                   │
                   ▼ merge
  New pages: [Page 1] [Page 2 (new)] [Page 3] [Page 4]
```

The merged result is then saved through the normal `update_presentation()` flow — all four pages are written to `presentation_pages` as if the LLM had returned all of them.

---

## 5. Access Control

Presentations do not have a direct `user_id` column. Ownership is verified by joining through the `conversations` table:

```
  Ownership check pattern:
  ─────────────────────────────────────────────────
  SELECT presentations.*
  FROM presentations
  JOIN conversations ON presentations.conversation_id = conversations.id
  WHERE presentations.id = :presentation_id
    AND conversations.user_id = :user_id    ← ownership enforced here
```

This pattern is used consistently in every repository function — `load_presentation`, `update_presentation`, `get_presentation_versions`, `get_version_content`, `get_active_presentation`.

**`user_id` source — dual path:**

```
  Workflow context              API endpoint
  (generate_slide step)         (/presentations/* routes)
         │                              │
         ▼                              ▼
  get_current_user_id()         user_id passed explicitly
  ← from ContextVar             ← from get_current_user dependency
         │                              │
         └──────────────┬───────────────┘
                        ▼
              repository function
```

Repository functions accept an optional `user_id` parameter. If provided, it is used directly (API case). If not, it falls back to `get_current_user_id()` from ContextVar (workflow case).

---

## 6. Frontend Usage Flow

### 6.1. Receive slide from workflow response

When the AI generates or edits a slide, the workflow response includes everything the frontend needs to render it immediately — no additional API call is required:

```
  POST /workflows/chat/run
         │
         ▼
  Response result (intent = "PPTX"):
  {
    "intent": "PPTX",
    "answer": "I've created a 5-page presentation about AI.",
    "topic": "Artificial Intelligence Basics",
    "slide_id": "presentation-uuid",
    "total_pages": 5,
    "pages": [
      { "page_number": 1, "page_title": "Introduction", "html_content": "<html>...</html>" },
      { "page_number": 2, "page_title": "What is AI?",  "html_content": "<html>...</html>" },
      ...
    ]
  }
         │
         ▼
  FE: render answer text in chat bubble
  FE: open slide viewer with pages[].html_content
  FE: store slide_id for future edit requests
```

### 6.2. Load slide when opening an existing conversation

When the user reopens a conversation that had slides, the frontend loads slide data from two sources:

```
  GET /conversations/{id}/messages
  ← returns all messages including PPTX messages
  ← each PPTX message has:
    {
      intent: "PPTX",
      content: "I've created a slide about AI.",
      metadata: {
        pages: [...],         ← full HTML pages for this version
        total_pages: 5,
        topic: "...",
        slide_id: "uuid"
      }
    }
         │
         ▼
  FE renders slides directly from message metadata
  (no separate /presentations API call needed for basic display)

  GET /conversations/{id}/active-presentation
  ← returns { presentation_id: "uuid" | null }
         │
         ▼
  FE uses this to highlight/focus the current active slide in the viewer
```

### 6.3. Browse version history

The version history feature lets users view and compare previous versions of a slide:

```
  User clicks "Version History" button for a presentation
         │
         ▼
  GET /presentations/{id}/versions
  ← returns list of all versions (newest first):
  [
    { version: 3, total_pages: 5, is_current: true,  user_request: "Change the color scheme", timestamp: "..." },
    { version: 2, total_pages: 5, is_current: false, user_request: "Edit the intro page",     timestamp: "..." },
    { version: 1, total_pages: 3, is_current: false, user_request: "Create a slide about AI", timestamp: "..." }
  ]
         │
         ▼
  FE shows version list panel

  User clicks on version 1
         │
         ▼
  GET /presentations/{id}/versions/1
  ← returns pages content for version 1:
  {
    total_pages: 3,
    pages: [
      { page_number: 1, page_title: "Introduction", html_content: "<html>...</html>" },
      { page_number: 2, ... },
      { page_number: 3, ... }
    ]
  }
         │
         ▼
  FE renders that version's slides in the viewer
  (read-only — viewing old version does not change active_presentation_id)
```

Note: `user_request` in the version list tells the user **what prompt produced each version** — useful for understanding the history of changes.

### 6.4. Slide data embedded in message metadata

Every PPTX message stores the full slide snapshot at the time it was created. This means:

```
  Message history in chat:

  [Turn 1] User: "Create a slide about AI"
           Assistant: "Created 3-page slide about AI"  ← metadata.pages = version 1 pages

  [Turn 2] User: "Edit the intro"
           Assistant: "Updated the intro page"         ← metadata.pages = version 2 pages (merged)

  [Turn 3] User: "Change the color scheme"
           Assistant: "Updated the color scheme"       ← metadata.pages = version 3 pages
```

Each message's `metadata.pages` is a permanent snapshot — it does not change even if the presentation is edited later. This lets the frontend render the slide as it appeared at each turn in the conversation.

---

## 7. API Endpoints

All endpoints are prefixed with `/presentations` and require `Authorization: Bearer <token>`. These are **read-only** endpoints — presentations are created and modified exclusively through the workflow (`POST /workflows/chat/run`).

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| `GET` | `/presentations/{id}/versions` | List all versions with metadata | `List[VersionInfoResponse]` |
| `GET` | `/presentations/{id}/versions/{version}` | Get pages of a specific version | `VersionContentResponse` |

**`VersionInfoResponse`:**

| Field | Type | Description |
|-------|------|-------------|
| `version` | int | Version number |
| `total_pages` | int | Page count for this version |
| `is_current` | bool | Whether this is the live version |
| `user_request` | str (nullable) | The prompt that created this version |
| `created_at` | str (nullable) | ISO timestamp |
| `timestamp` | str (nullable) | Alias for `created_at` (FE compatibility) |

**`VersionContentResponse`:**

| Field | Type | Description |
|-------|------|-------------|
| `total_pages` | int | Number of pages |
| `pages` | `List[PageContentResponse]` | Page objects |

---

## 8. Presentation in Workflow Context

Presentations are created and modified exclusively by the **`generate_slide` step** in `ChatWorkflow`. The full generation logic — including intent detection, prompt assembly, LLM call, page merging, and DB save — is documented in detail in **05_Workflow.md, Section 5**.

Key points for reference:
- Presentations are **never created via REST API** — only through `POST /workflows/chat/run`
- The REST API under `/presentations` is **read-only** (version history browsing)
- `active_presentation_id` on the conversation is always updated after every create or edit
