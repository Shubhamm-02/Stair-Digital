# PDF-Grounded Chatbot

A chatbot that answers questions strictly from a user-supplied PDF, using the Gemini API. Out-of-scope questions are refused with a fixed message; in-scope answers include page-number citations.

Two ways to run it:

1. **React + FastAPI** — full web app with streaming responses ([frontend/](frontend/) + [server.py](server.py))
2. **Streamlit** — single-file demo ([app.py](app.py))

Both share the same grounding contract.

## How grounding works

- The PDF is uploaded directly to Gemini via the **File API** — no manual text extraction, chunking, or vector store.
- Gemini reads the PDF natively (page numbers included) inside a chat session.
- A strict **system instruction** enforces three contracts:
  1. answer only from the PDF,
  2. cite the page on every factual claim,
  3. refuse out-of-scope queries with the exact line:
     `This question is outside the scope of the provided PDF.`
- Temperature is pinned to `0.1` to reduce hallucination.

## One-time setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then paste your GEMINI_API_KEY into .env
```

Get a Gemini API key from <https://aistudio.google.com/apikey>.

## Option 1 — React + FastAPI (recommended)

Two terminals.

**Terminal 1 — backend**

```bash
source venv/bin/activate
uvicorn server:app --reload --port 8000
```

**Terminal 2 — frontend**

```bash
cd frontend
npm install        # only the first time
npm run dev
```

Open <http://localhost:5173>. Upload a PDF in the sidebar, then chat. Replies stream token-by-token. Use **Reset conversation** to clear history; uploading a new PDF starts a fresh session automatically.

API surface (in [server.py](server.py)):

- `POST /api/upload-pdf` — multipart `file=<pdf>` → `{ session_id, pdf_name }`
- `POST /api/chat` — `{ session_id, message }` → streamed `text/plain` body
- `POST /api/reset` — `{ session_id }` → clears chat history, keeps the PDF
- `GET /api/health` — sanity check

Sessions are kept in memory keyed by `session_id`. Restarting the backend drops them.

## Option 2 — Streamlit

```bash
source venv/bin/activate
streamlit run app.py
```

Streamlit opens a browser tab. Same behavior, simpler UI.

## Files

- [server.py](server.py) — FastAPI backend
- [app.py](app.py) — Streamlit single-file app
- [frontend/](frontend/) — Vite + React + TS + Tailwind v4 UI
- [requirements.txt](requirements.txt) — Python deps
- [.env.example](.env.example) — API key template
- [test_queries.md](test_queries.md) — 5 valid + 3 invalid test queries with expected behavior
- `sample.pdf` — the PDF used for testing (drop your own here)

## Testing

See [test_queries.md](test_queries.md). After uploading `sample.pdf`, run each query and confirm:

- valid queries → answer is correct relative to the PDF and includes a `(Page N)` citation,
- invalid queries → response is exactly: `This question is outside the scope of the provided PDF.`
