# Agent Chat Backend v2

Backend hệ thống chat AI với khả năng tạo và quản lý presentation slides, sử dụng LlamaIndex Workflow và Supabase.

## 📁 Cấu Trúc Thư Mục

```
agent_chat_backend_v2/
├── app/                          # Application code chính
│   ├── config/                   # Cấu hình và constants
│   │   ├── auth_middleware.py    # JWT authentication middleware
│   │   ├── constants.py          # Magic strings và constants tập trung
│   │   ├── models.py             # Pydantic models cho LLM structured output
│   │   ├── supabase_client.py    # Supabase client initialization
│   │   ├── types.py              # TypedDict cho shared data structures
│   │   └── workflow_context.py  # ContextVar cho user_id và JWT token
│   │
│   ├── repositories/             # Data access layer (DAL)
│   │   ├── chat_repository.py   # CRUD operations cho messages
│   │   ├── presentation_repository.py  # CRUD operations cho presentations
│   │   ├── summary_repository.py      # CRUD operations cho summaries
│   │   └── user_facts_repository.py   # CRUD operations cho user facts
│   │
│   ├── services/                 # Business logic layer
│   │   ├── chat_service.py      # Business logic cho chat (ownership validation)
│   │   ├── memory_service.py    # Business logic cho memory management
│   │   └── presentation_service.py  # Business logic cho presentation intent detection
│   │
│   ├── tools/                    # LLM tools (function calling)
│   │   ├── user_facts.py         # Tools để add/update/delete user facts
│   │   ├── weather.py            # Tool để lấy thông tin thời tiết
│   │   └── stock.py              # Tool để lấy giá cổ phiếu
│   │
│   ├── utils/                     # Utility functions
│   │   ├── formatters.py         # Format functions (user facts, messages)
│   │   └── helpers.py            # Helper functions
│   │
│   └── workflows/                # LlamaIndex Workflows
│       ├── router_workflow.py   # Main workflow: routing và answering
│       ├── slide_workflow.py     # Slide generation workflow
│       └── memory_manager.py     # Memory truncation và summarization logic
│
├── supabase/                     # Database migrations
│   ├── migrations/               # SQL migration files
│   │   ├── 001_create_tables.sql
│   │   ├── 002_rpc_functions.sql
│   │   ├── 003_rls_policies.sql
│   │   └── ...
│   └── README.md                 # Migration tracking
│
├── server.py                     # Entry point - WorkflowServer setup
└── requirements.txt              # Python dependencies
```

## 🏗️ Kiến Trúc Hệ Thống

Hệ thống được tổ chức theo **Layered Architecture** với các tầng rõ ràng:

### 1. **Config Layer** (`app/config/`)
- **constants.py**: Tập trung tất cả magic strings (roles, intents, field names, table names, RPC functions)
- **types.py**: TypedDict definitions cho shared data structures
- **models.py**: Pydantic models cho LLM structured output
- **supabase_client.py**: Khởi tạo Supabase client với JWT token handling
- **auth_middleware.py**: JWT authentication middleware cho WorkflowServer
- **workflow_context.py**: ContextVar để truyền user_id và JWT token qua async calls

### 2. **Repository Layer** (`app/repositories/`)
- **Trách nhiệm**: Data access layer - chỉ tương tác với database
- **Pattern**: Mỗi repository chứa các hàm CRUD cho một domain entity
- **Sử dụng**: Constants từ `config/constants.py` và types từ `config/types.py`
- **Không chứa**: Business logic, chỉ có data access

### 3. **Service Layer** (`app/services/`)
- **Trách nhiệm**: Business logic layer - xử lý logic nghiệp vụ
- **Ví dụ**:
  - `chat_service.py`: Validate conversation ownership
  - `memory_service.py`: Split messages cho summary, tạo summary với LLM
  - `presentation_service.py`: Detect presentation intent (CREATE_NEW, EDIT_SPECIFIC, EDIT_ACTIVE)

### 4. **Tools Layer** (`app/tools/`)
- **Trách nhiệm**: LLM function calling tools
- **Sử dụng**: Repositories để lưu/đọc data, services cho business logic
- **Ví dụ**: `add_user_fact`, `get_weather`, `get_stock_price`

### 5. **Workflow Layer** (`app/workflows/`)
- **Trách nhiệm**: Orchestration layer - điều phối toàn bộ flow
- **RouterWorkflow**: Main workflow xử lý routing và answering
- **SlideWorkflow**: Workflow xử lý slide generation và editing
- **MemoryManager**: Xử lý memory truncation và summarization

## 🔄 Luồng Xử Lý Tổng Quát

### 1. **Request Flow**

```
Frontend Request
    ↓
WorkflowServer (server.py)
    ↓
AuthMiddleware (JWT verification)
    ↓
RouterWorkflow.route_and_answer()
```

### 2. **RouterWorkflow Flow**

```
1. Authentication & Validation
   ├─ Extract user_id từ JWT (ContextVar)
   ├─ Validate conversation_id
   └─ Validate conversation ownership (chat_service)

2. Load Context
   ├─ Load chat history (chat_repository)
   ├─ Load user facts (user_facts_repository)
   └─ Load conversation summary (summary_repository)

3. Build System Prompt
   ├─ Add user facts
   ├─ Add chat history
   └─ Add conversation summary

4. Save User Message
   └─ Save to database (chat_repository)

5. LLM Processing
   ├─ Tool calling loop (nếu cần)
   │   ├─ get_weather
   │   ├─ get_stock_price
   │   ├─ add_user_fact
   │   ├─ update_user_fact
   │   └─ delete_user_fact
   └─ Get final JSON response (RouterOutput)

6. Intent Routing
   ├─ If INTENT_GENERAL:
   │   ├─ Save assistant message
   │   ├─ Process memory truncation
   │   └─ Return response
   └─ If INTENT_PPTX:
       └─ Trigger GenerateSlideEvent → SlideWorkflow
```

### 3. **SlideWorkflow Flow**

```
1. Detect Presentation Intent
   └─ presentation_service.detect_presentation_intent()
      ├─ CREATE_NEW: Tạo presentation mới
      ├─ EDIT_SPECIFIC: Sửa presentation cụ thể (theo topic/ID)
      └─ EDIT_ACTIVE: Sửa presentation đang active

2. Load Previous Data (nếu EDIT)
   └─ presentation_repository.load_presentation()

3. Build System Prompt
   ├─ Add chat history
   ├─ Add conversation summary
   └─ Add previous slide pages (nếu EDIT)

4. LLM Generate Slides
   └─ Call LLM với SlideOutput model

5. Save Presentation
   ├─ CREATE_NEW: create_presentation()
   └─ EDIT: update_presentation() (archives old version)

6. Save Assistant Message
   └─ Save với metadata (pages, total_pages, topic, slide_id)

7. Process Memory
   └─ Process memory truncation
```

### 4. **Memory Management Flow**

```
Memory Truncation Trigger
    ↓
memory_manager.process_memory_truncation()
    ↓
1. Check if memory truncated
    ├─ Compare hash của first message
    └─ Detect if messages were removed
    ↓
2. Split Messages
    └─ memory_service.split_messages_for_summary()
       ├─ 80% → messages_to_summarize
       └─ 20% → messages_to_keep
    ↓
3. Create Summary
    └─ memory_service.create_summary()
       ├─ Load old summary
       ├─ Combine với new messages
       └─ Call LLM để tạo summary
    ↓
4. Mark Messages as Summarized
    └─ summary_repository.mark_messages_as_summarized()
       └─ Set is_in_working_memory = False
    ↓
5. Update Memory
    └─ Create new memory với messages_to_keep
```

## 🔐 Authentication & Security

### JWT Authentication Flow

```
1. Frontend gửi JWT token trong Authorization header
    ↓
2. AuthMiddleware verify token
    ├─ Extract user_id từ JWT
    ├─ Store user_id và JWT trong ContextVar
    └─ Set JWT trong Supabase client cho RLS
    ↓
3. Workflow access user_id
    └─ get_current_user_id() từ ContextVar
```

### Row Level Security (RLS)

- Tất cả database queries sử dụng `ANON_KEY` với JWT token
- RLS policies đảm bảo users chỉ access được data của chính họ
- Application-level validation trong `chat_service.validate_conversation_access()`

## 💾 Database Schema

### Core Tables
- **conversations**: Danh sách conversations của users
- **messages**: Messages trong conversations (với `is_in_working_memory` flag)
- **conversation_summaries**: Summary của conversations (chỉ lưu latest version)
- **user_facts**: User facts (key-value pairs)

### Presentation Tables
- **presentations**: Presentation metadata (current version)
- **presentation_pages**: Pages của current version
- **presentation_versions**: Archived versions metadata
- **presentation_version_pages**: Pages của archived versions

### RPC Functions
- `get_active_presentation(conv_id)`: Lấy active presentation ID
- `set_active_presentation(conv_id, p_id)`: Set active presentation
- `get_presentation_pages(p_id)`: Lấy pages của current version
- `get_version_pages(p_id, v_num)`: Lấy pages của specific version
- `get_presentation_versions(p_id)`: Lấy tất cả versions metadata
- `archive_presentation_version(p_id)`: Archive current version trước khi update

## 📝 Notes

- **Constants & Types**: Tất cả magic strings và shared data structures được tập trung trong `config/constants.py` và `config/types.py` để dễ maintain

- **Layered Architecture**: Tách biệt rõ ràng giữa data access (repositories), business logic (services), và orchestration (workflows)

- **Memory Management**: Hệ thống tự động truncate và summarize messages khi memory đầy, chỉ giữ lại 20% messages gần nhất

- **Presentation Versioning**: Mỗi lần edit presentation, version cũ được archive vào `presentation_versions` và `presentation_version_pages`

