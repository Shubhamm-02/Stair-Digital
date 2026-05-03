import base64
import gzip
import json
import math
import os
import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


REFUSAL = "This question is outside the scope of the provided PDF."
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
FALLBACK_MODELS = os.getenv("OPENAI_FALLBACK_MODELS", "")
ALLOW_EXTRACTIVE_FALLBACK = os.getenv("ALLOW_EXTRACTIVE_FALLBACK", "true").lower() not in {
    "0",
    "false",
    "no",
}
MODEL_CANDIDATES = tuple(
    dict.fromkeys(
        [DEFAULT_MODEL]
        + [model.strip() for model in FALLBACK_MODELS.split(",") if model.strip()]
    )
)
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PAGES = 1000
MAX_CONTEXT_CHARS = 18000
PAGE_CITATION_RE = re.compile(r"\(Page(?:s)?\s+\d+")
PAGE_NUMBER_RE = re.compile(r"Page(?:s)?\s+([0-9,\sand-]+)", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")
TRANSIENT_ERROR_MARKERS = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "rate limit",
    "temporarily",
    "timeout",
    "overloaded",
    "unavailable",
)
QUOTA_ERROR_MARKERS = (
    "insufficient_quota",
    "exceeded your current quota",
    "billing details",
    "run out of credits",
)
OUT_OF_SCOPE_TERMS = {
    "billing",
    "cost",
    "dinner",
    "fee",
    "fifa",
    "minister",
    "president",
    "price",
    "pricing",
    "restaurant",
    "salary",
    "tonight",
    "world",
}
STOPWORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}
GENERIC_QUERY_TERMS = STOPWORDS | {
    "answer",
    "brief",
    "covered",
    "describe",
    "document",
    "explain",
    "information",
    "main",
    "mention",
    "mentions",
    "pdf",
    "question",
    "section",
    "says",
    "summary",
    "summarize",
    "tell",
    "topic",
    "topics",
}

SYSTEM_PROMPT = f"""You are a strict PDF-grounded assistant.

Rules:
1. Answer only from the supplied PDF page excerpts.
2. Do not use outside knowledge, prior training, or assumptions.
3. Every factual claim must include an inline citation in exactly this format:
   (Page N)
4. If the excerpts do not contain the answer, reply with exactly:
   {REFUSAL}
5. If the user asks for another language, answer in that language but keep
   citations in the exact (Page N) format.
6. Do not cite pages that were not supplied in the context.
7. Conversation history may resolve references, but it is not evidence.
"""


@dataclass(frozen=True)
class PageSource:
    page_number: int
    text: str


@dataclass(frozen=True)
class PdfDocument:
    name: str
    pages: tuple[PageSource, ...]


def encode_document(document: PdfDocument) -> str:
    payload = {
        "name": document.name,
        "pages": [[page.page_number, page.text] for page in document.pages],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(raw)
    return base64.urlsafe_b64encode(compressed).decode("ascii")


def decode_document(token: str) -> PdfDocument:
    try:
        compressed = base64.urlsafe_b64decode(token.encode("ascii"))
        payload = json.loads(gzip.decompress(compressed).decode("utf-8"))
        pages = tuple(
            PageSource(page_number=int(page_number), text=str(text))
            for page_number, text in payload["pages"]
            if str(text).strip()
        )
        if not pages:
            raise ValueError("Document token has no pages.")
        return PdfDocument(name=str(payload.get("name") or "uploaded.pdf"), pages=pages)
    except Exception as exc:
        raise ValueError("Invalid or expired document token.") from exc


def validate_pdf(file_bytes: bytes) -> None:
    if not file_bytes:
        raise ValueError("Uploaded PDF is empty.")
    if len(file_bytes) > MAX_PDF_BYTES:
        raise ValueError("PDF must be 20 MB or smaller.")
    if not file_bytes.startswith(b"%PDF"):
        raise ValueError("Uploaded file is not a valid PDF.")


def extract_pdf_document(file_bytes: bytes, name: str) -> PdfDocument:
    validate_pdf(file_bytes)
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is not installed. Run `pip install -r requirements.txt`."
        ) from exc

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError(f"Could not read PDF: {exc}") from exc

    if doc.page_count == 0:
        raise ValueError("PDF has no pages.")
    if doc.page_count > MAX_PAGES:
        raise ValueError(f"PDF must be {MAX_PAGES} pages or fewer.")

    pages: list[PageSource] = []
    for index, page in enumerate(doc, start=1):
        text = " ".join((page.get_text("text") or "").split())
        if text:
            pages.append(PageSource(page_number=index, text=text))

    if not pages:
        raise ValueError(
            "No extractable text was found in this PDF. Use a text-based PDF for this demo."
        )

    return PdfDocument(name=name, pages=tuple(pages))


def tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_RE.findall(text)
        if len(token) > 1 and token.lower() not in STOPWORDS
    ]


def build_retrieval_query(question: str, history: Iterable[dict] | None = None) -> str:
    parts: list[str] = []
    if history:
        recent = list(history)[-6:]
        parts.extend(str(message.get("content", "")) for message in recent)
    parts.append(question)
    return "\n".join(parts)


def retrieve_pages(
    document: PdfDocument,
    question: str,
    history: Iterable[dict] | None = None,
    top_k: int = 5,
) -> list[PageSource]:
    query_text = build_retrieval_query(question, history)
    query_terms = tokenize(query_text)

    if not query_terms:
        return list(document.pages[: min(top_k, len(document.pages))])

    page_tokens = [tokenize(page.text) for page in document.pages]
    doc_freq = Counter()
    for tokens in page_tokens:
        doc_freq.update(set(tokens))

    total_pages = len(document.pages)
    query_counts = Counter(query_terms)
    scored: list[tuple[float, int, PageSource]] = []

    for index, (page, tokens) in enumerate(zip(document.pages, page_tokens)):
        counts = Counter(tokens)
        score = 0.0
        for term, query_count in query_counts.items():
            if term not in counts:
                continue
            idf = math.log((total_pages + 1) / (doc_freq[term] + 1)) + 1.0
            score += (1 + math.log(counts[term])) * idf * query_count

        lower_page = page.text.lower()
        for phrase in quoted_phrases(question):
            if phrase.lower() in lower_page:
                score += 4.0

        scored.append((score, -index, page))

    scored.sort(reverse=True)
    selected = [page for score, _, page in scored[:top_k] if score > 0]

    if not selected:
        selected = list(document.pages[: min(top_k, len(document.pages))])
    elif len(document.pages) <= top_k:
        selected = list(document.pages)

    return sorted(selected, key=lambda page: page.page_number)


def quoted_phrases(text: str) -> list[str]:
    return re.findall(r'"([^"]+)"', text)


def format_context(pages: Iterable[PageSource]) -> str:
    chunks: list[str] = []
    remaining = MAX_CONTEXT_CHARS
    for page in pages:
        label = f"[Page {page.page_number}]"
        text = page.text[: max(0, remaining - len(label) - 2)]
        if not text:
            break
        chunks.append(f"{label}\n{text}")
        remaining -= len(label) + len(text) + 2
        if remaining <= 0:
            break
    return "\n\n".join(chunks)


def format_history(history: Iterable[dict] | None) -> str:
    if not history:
        return "No prior conversation."
    lines: list[str] = []
    for message in list(history)[-6:]:
        role = str(message.get("role", "user")).title()
        content = " ".join(str(message.get("content", "")).split())
        if content:
            lines.append(f"{role}: {content[:600]}")
    return "\n".join(lines) or "No prior conversation."


def normalize_model_text(text: str, allowed_pages: set[int]) -> str:
    answer = (text or "").strip()
    if not answer:
        return REFUSAL
    if REFUSAL in answer:
        return REFUSAL
    if not PAGE_CITATION_RE.search(answer):
        return REFUSAL

    cited_pages = extract_cited_pages(answer)
    if not cited_pages or not cited_pages.issubset(allowed_pages):
        return REFUSAL
    return answer


def extract_cited_pages(answer: str) -> set[int]:
    pages: set[int] = set()
    for match in PAGE_NUMBER_RE.findall(answer):
        for number in re.findall(r"\d+", match):
            pages.add(int(number))
    return pages


def is_quota_error(error: Exception) -> bool:
    message = str(error).lower()
    return any(marker in message for marker in QUOTA_ERROR_MARKERS)


def is_transient_error(error: Exception) -> bool:
    message = str(error).lower()
    return any(marker in message for marker in TRANSIENT_ERROR_MARKERS)


def model_order() -> list[str]:
    return list(MODEL_CANDIDATES)


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key."
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI SDK is not installed. Run `pip install -r requirements.txt`."
        ) from exc

    return OpenAI(api_key=api_key)


def split_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def document_terms(document: PdfDocument) -> set[str]:
    return set(tokenize(" ".join(page.text for page in document.pages)))


def should_refuse_extractive(document: PdfDocument, question: str) -> bool:
    question_terms = set(tokenize(question))
    doc_terms = document_terms(document)

    if question_terms & OUT_OF_SCOPE_TERMS and not question_terms & OUT_OF_SCOPE_TERMS & doc_terms:
        return True

    evidence_terms = question_terms - GENERIC_QUERY_TERMS
    if not evidence_terms:
        return False

    overlap = evidence_terms & doc_terms
    if not overlap and "main" not in question_terms and "topic" not in question_terms:
        return True

    missing_topic_terms = evidence_terms - doc_terms
    if missing_topic_terms & OUT_OF_SCOPE_TERMS:
        return True

    return False


def score_sentence(sentence: str, question_terms: set[str]) -> float:
    sentence_terms = set(tokenize(sentence))
    score = len(sentence_terms & question_terms) * 2.0
    if re.search(r"\d+%|\bpercent\b|\bpercentage\b", sentence, re.IGNORECASE):
        score += 2.0
    if re.search(r"\bdefined as\b|\bis defined\b", sentence, re.IGNORECASE):
        score += 2.0
    if "topics" in sentence.lower() or "covered" in sentence.lower():
        score += 1.0
    return score


def first_content_sentence(page: PageSource) -> str:
    sentences = split_sentences(page.text)
    return sentences[0] if sentences else page.text[:300]


def extractive_answer(
    document: PdfDocument,
    question: str,
    history: Iterable[dict] | None = None,
) -> str:
    question_terms = set(tokenize(build_retrieval_query(question, history)))
    lower_question = question.lower()

    if should_refuse_extractive(document, question):
        return REFUSAL

    pages = retrieve_pages(document, question, history)

    if "main topic" in lower_question or (
        "topic" in question_terms and document.pages
    ):
        page = document.pages[0]
        sentences = split_sentences(page.text)
        for sentence in sentences:
            if " is " in sentence.lower():
                return f"{sentence} (Page {page.page_number})"
        for sentence in sentences:
            if "overview" in sentence.lower():
                return f"{sentence} (Page {page.page_number})"
        return f"{first_content_sentence(page)} (Page {page.page_number})"

    if "summar" in lower_question:
        snippets = [
            f"{first_content_sentence(page)} (Page {page.page_number})"
            for page in pages[:3]
        ]
        return " ".join(snippets) if snippets else REFUSAL

    scored: list[tuple[float, int, str]] = []
    for page in pages:
        for sentence in split_sentences(page.text):
            score = score_sentence(sentence, question_terms)
            if score > 0:
                scored.append((score, page.page_number, sentence))

    if not scored:
        return REFUSAL

    scored.sort(reverse=True)
    chosen: list[tuple[int, str]] = []
    seen = set()
    for _, page_number, sentence in scored:
        key = (page_number, sentence)
        if key in seen:
            continue
        seen.add(key)
        chosen.append((page_number, sentence))
        if len(chosen) >= 1:
            break

    return " ".join(
        f"{sentence} (Page {page_number})" for page_number, sentence in chosen
    )


def answer_question(
    client,
    document: PdfDocument,
    question: str,
    history: Iterable[dict] | None = None,
) -> str:
    pages = retrieve_pages(document, question, history)
    allowed_pages = {page.page_number for page in pages}
    context = format_context(pages)
    history_text = format_history(history)
    input_text = f"""PDF name: {document.name}

Retrieved page excerpts:
{context}

Recent conversation:
{history_text}

Use conversation history only to understand references. Use the retrieved PDF
page excerpts as the only evidence source.

User question:
{question}
"""

    last_error: Exception | None = None
    for model in model_order():
        for attempt in range(2):
            try:
                response = client.responses.create(
                    model=model,
                    instructions=SYSTEM_PROMPT,
                    input=input_text,
                    temperature=0,
                    max_output_tokens=700,
                )
                return normalize_model_text(response.output_text, allowed_pages)
            except Exception as error:
                last_error = error
                if is_quota_error(error) and ALLOW_EXTRACTIVE_FALLBACK:
                    return extractive_answer(document, question, history)
                if is_transient_error(error):
                    time.sleep(attempt + 1)
                    continue
                raise

    raise RuntimeError(f"OpenAI request failed after retries: {last_error}")
