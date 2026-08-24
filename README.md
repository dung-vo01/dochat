# Dochat

A full-stack AI chat app that lets you upload a PDF and have a conversation with it. Built as a self-studied project about streaming responses (SSE), retrieval-augmented generation, and tool calling.

![Dochat demo](demo/demo.gif)

## What it does

- **Streaming chat**: responses come back token-by-token over Server-Sent Events, not as one blocking request. A stop button cancels mid-stream.
- **PDF upload + RAG**: upload a PDF and it's extracted, chunked, embedded, and stored in a local vector database. Every question you ask retrieves the most relevant chunks and feeds them to the model as context, so answers are grounded in the document instead of the model just guessing.
- **Persisted conversations**: conversations and messages are stored in Postgres (via SQLAlchemy + Alembic migrations), with a sidebar to switch between, create, and delete them. Refreshing the page doesn't lose history.
- **Tool calling**: the model can call `get_current_datetime`, `web_search`, and `clear_chat_history` mid-conversation.

## Tech stack

|              |                                                              |
| ------------ | ------------------------------------------------------------ |
| Frontend     | React + TypeScript, SCSS Modules, Vite                       |
| Backend      | Python, FastAPI, SQLAlchemy (async) + Alembic                |
| Database     | PostgreSQL                                                    |
| AI           | OpenAI GPT-4o (chat + tool calling) + text-embedding-3-small (embeddings) |
| Vector store | ChromaDB (local, persisted to disk)                           |

## How it works

**Upload:** PDF => extract text (`pypdf`) => split into overlapping chunks => embed each chunk => store in ChromaDB.

**Chat:** user message saved to Postgres => embed the message => query ChromaDB for the closest chunks => inject them into the system prompt along with the conversation's message history => model responds (optionally calling a tool first) => stream the response back over SSE => frontend appends each token to the last message as it arrives => assistant response saved to Postgres.

```
frontend/src/
  api/chat.ts             fetch + SSE stream parsing
  api/conversations.ts    conversation CRUD
  hooks/useChat.ts         message state, sending, streaming
  hooks/useUpload.ts       file upload state
  components/Chat/         chat UI
  components/Sidebar/      conversation list UI

backend/app/
  routers/chat.py          POST /api/chat: streams the response
  routers/conversations.py CRUD for conversations
  routers/upload.py        POST /api/upload: extracts, chunks, embeds, indexes
  services/chat.py         orchestrates a chat turn (RAG + tools + streaming)
  services/rag.py          embedding + retrieval + prompt building
  services/memory.py       conversation/message persistence
  services/tools.py        tool definitions + handlers
  clients/                 OpenAI and ChromaDB client setup
  utils/helpers.py         PDF text extraction, chunking
```

## Getting started

### Backend

Requires a running PostgreSQL instance and [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync
cp .env.example .env        # then add your own OPENAI_API_KEY and DATABASE_URL
uv run alembic upgrade head # create the conversations/messages tables
uv run python run.py
```

Backend runs on `http://localhost:5000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:3000` and proxies `/api/*` requests to the backend (see `vite.config.ts`).

## Current limitations

This is a learning project, not a production app so some corners are deliberately cut for now:

- One global document collection: uploading a new PDF replaces the previous one, and any indexed document is visible to every conversation — there's no per-user or per-conversation isolation.
- No auth: anyone with access to the API can read/write any conversation.
- Chunking is character-based (fixed size + overlap), not token- or sentence-aware, and conversation history sent to the model is unbounded — long conversations will eventually hit the model's context limit.
- Assistant messages render as plain text (no markdown/code-block formatting).

## Roadmap

- [ ] Multi-document support (per-conversation document scoping)
- [ ] Context window trimming/summarization for long conversations
- [ ] Markdown rendering for assistant messages
- [ ] Deploy backend (Railway/Render) + frontend (Vercel)
