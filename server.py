import uuid
from typing import Iterator

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pdf_rag import (
    DEFAULT_MODEL,
    MODEL_CANDIDATES,
    answer_question,
    decode_document,
    encode_document,
    extract_pdf_document,
    get_openai_client,
)

load_dotenv()

client = None

# In-memory session store: session_id -> {document, pdf_name, messages}
sessions: dict[str, dict] = {}

app = FastAPI(title="PDF Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str | None = None
    document_token: str | None = None
    message: str
    history: list[dict] = []


class ResetRequest(BaseModel):
    session_id: str


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "model": DEFAULT_MODEL,
        "fallback_models": MODEL_CANDIDATES[1:],
    }


def openai_client():
    global client
    if client is None:
        client = get_openai_client()
    return client


@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    try:
        document = extract_pdf_document(await file.read(), file.filename or "uploaded.pdf")
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "document": document,
        "pdf_name": file.filename,
        "messages": [],
    }
    return {
        "session_id": session_id,
        "document_token": encode_document(document),
        "pdf_name": file.filename,
        "page_count": len(document.pages),
    }


@app.post("/api/chat")
def chat(req: ChatRequest):
    sess = sessions.get(req.session_id or "")
    if sess is not None:
        document = sess["document"]
        history = sess["messages"]
    elif req.document_token:
        try:
            document = decode_document(req.document_token)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        history = req.history
    else:
        raise HTTPException(status_code=404, detail="Session not found. Upload a PDF first.")

    def stream() -> Iterator[bytes]:
        try:
            answer = answer_question(
                client=openai_client(),
                document=document,
                question=req.message,
                history=history,
            )
            if sess is not None:
                sess["messages"].append({"role": "user", "content": req.message})
                sess["messages"].append({"role": "assistant", "content": answer})
            yield answer.encode("utf-8")
        except Exception as error:
            yield f"\n\n[stream error: {error}]".encode("utf-8")

    return StreamingResponse(stream(), media_type="text/plain; charset=utf-8")


@app.post("/api/reset")
def reset(req: ResetRequest):
    sess = sessions.get(req.session_id)
    if sess is None:
        return {"ok": True}
    sess["messages"] = []
    return {"ok": True}
