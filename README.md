# docRAG

A portable research-paper RAG app. Upload PDFs, TXT, or Markdown files, store extracted chunks in SQLite, and ask questions with source-backed retrieval.

## Easiest Run: Docker

This is the smoothest way to run docRAG on another computer because Docker supplies Python and all app dependencies.

1. Install Docker Desktop.
2. Download or unzip this `docrag_app` folder.
3. In the `docrag_app` folder, run:

```bash
cp .env.example .env
docker compose up --build
```

Open `http://127.0.0.1:8000`.

Uploaded files and the SQLite index stay on that computer in `data/`.

## Run Without Docker

Mac/Linux:

```bash
./scripts/start.sh
```

Windows:

```bat
scripts\start.bat
```

Then open `http://127.0.0.1:8000`.

## Optional LLM Mode

Without an API key, docRAG uses local SQLite full-text search and returns the most relevant passages immediately.

For synthesized answers and semantic embeddings, edit `.env` and set:

```text
OPENAI_API_KEY=your_key_here
```

Restart docRAG after changing `.env`:

```bash
docker compose down
docker compose up --build
```

If you already built the app before this fix, use `docker compose build --no-cache` once to force Docker to reinstall the pinned OpenAI dependencies.

## API

- `GET /api/health`
- `GET /api/documents`
- `POST /api/upload` with multipart field `files`
- `POST /api/query` with JSON `{ "question": "...", "top_k": 6 }`
