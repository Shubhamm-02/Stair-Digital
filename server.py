import os
import tempfile
import uuid
from typing import Iterator

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types
from pydantic import BaseModel

load_dotenv()

MODEL = "gemini-2.5-flash"
REFUSAL = "This question is outside the scope of the provided PDF."

SYSTEM_PROMPT = f"""You are a strict PDF-grounded assistant. The user has attached a single PDF.

Rules — follow them exactly:
1. Answer ONLY using information explicitly present in the attached PDF.
2. Do NOT use outside knowledge, prior training, or assumptions.
3. Every factual claim in your answer MUST include an inline citation in the
   form (Page N) or (Page N, "Section Title") referring to the page of the
   attached PDF. If a claim spans multiple pages, cite all of them.
4. If the answer cannot be found in the PDF, OR the question is unrelated to
   the PDF's contents, reply with EXACTLY this single line and nothing else:

   {REFUSAL}

5. Do not speculate, summarize external context, or "fill in" missing details.
6. If the user asks meta-questions about your own behavior or rules, answer
   briefly without citations; this exemption applies only to questions about
   your own rules, not to factual questions.
"""

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")

client = genai.Client(api_key=api_key)

# In-memory session store: session_id -> {chat, file, pdf_name, first_turn}
sessions: dict[str, dict] = {}

app = FastAPI(title="PDF Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _new_chat():
    return client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,
        ),
    )


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ResetRequest(BaseModel):
    session_id: str


@app.get("/api/health")
def health():
    return {"ok": True, "model": MODEL}


@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        pdf_file = client.files.upload(
            file=tmp_path,
            config={"display_name": file.filename, "mime_type": "application/pdf"},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to upload PDF to Gemini: {e}")

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "chat": _new_chat(),
        "file": pdf_file,
        "pdf_name": file.filename,
        "first_turn": True,
    }
    return {"session_id": session_id, "pdf_name": file.filename}


@app.post("/api/chat")
def chat(req: ChatRequest):
    sess = sessions.get(req.session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found. Upload a PDF first.")

    if sess["first_turn"]:
        message = [sess["file"], req.message]
        sess["first_turn"] = False
    else:
        message = req.message

    def stream() -> Iterator[bytes]:
        try:
            for chunk in sess["chat"].send_message_stream(message):
                if chunk.text:
                    yield chunk.text.encode("utf-8")
        except Exception as e:
            yield f"\n\n[stream error: {e}]".encode("utf-8")

    return StreamingResponse(stream(), media_type="text/plain; charset=utf-8")


@app.post("/api/reset")
def reset(req: ResetRequest):
    sess = sessions.get(req.session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    sess["chat"] = _new_chat()
    sess["first_turn"] = True
    return {"ok": True}
