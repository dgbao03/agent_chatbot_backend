# Overview

## 1. Introduction

**Agent Chat API** is the backend for an AI-powered chat application built around an **Agent** architecture. Unlike a simple chatbot that only answers questions, the system operates as an intelligent agent it understands user intent, decides whether to answer directly or invoke external tools to gather information, and can handle complex requests such as generating and editing full HTML slide presentations.

## 2. Key Features

### Chat with AI Agent
- Have natural conversations with an AI agent across multiple sessions
- The agent understands the context of the conversation and remembers what was discussed earlier
- The agent can looks up for external information via tools (weather, stock prices, URLs) when needed

### Real-time Information via Tools
- Ask the agent for the current weather in any city
- Ask the agent for the latest stock price of any ticker symbol
- Provide a URL and ask the agent to read and summarize the content of that page

### Slide Presentation
- Ask the agent to create a multi-page slide presentation on any topic — it generates the full content automatically
- Ask the agent to edit an existing presentation: change the content, add or remove pages, or modify a specific page
- Every time a presentation is edited, the previous version is saved — users can go back and view any earlier version

### Conversation Management
- All conversations are automatically saved and can be revisited at any time
- Each conversation is automatically given a title based on the first message
- Users can rename or delete any conversation
- Full message history is preserved, including AI responses and any slides generated within the conversation

### Personal Memory
- Tell the agent to remember personal information (e.g., "Remember that my name is Bao", "Save that I live in Hanoi")
- The agent will recall this information in future conversations without the user needing to repeat it
- Users can ask the agent to update or forget any saved information at any time

### Memory Management
- The agent remembers the context of the current conversation, even in very long sessions
- When a conversation grows too long, the agent automatically summarizes older messages so nothing important is lost
- The summary is carried forward silently — users do not need to do anything, the agent simply stays aware of what was discussed earlier

### Authentication
- Register and log in with email and password
- Register and log in with Google account
- Reset forgotten password via a link sent to email

## 3. Tech Stack

- **Framework** — FastAPI

- **AI / LLM** — LlamaIndex, OpenAI API

- **Database** — PostgreSQL, SQLAlchemy

- **Authentication** — JWT, OAuth 2.0 Google

- **Email** — aiosmtplib (async SMTP for password reset link)

- **Background Tasks** — APScheduler (outdated token cleanup every 24h)

- **Logging** — structlog (structured JSON logging), Promtail (log collector), Loki (log storage), Grafana (log visualizer)
