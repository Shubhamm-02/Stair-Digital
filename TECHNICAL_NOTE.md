# Technical Note: PDF-Grounded Chatbot

## 1. Architecture Overview

The system is a lightweight PDF-constrained conversational agent. It separates grounding from generation: PDF parsing and retrieval happen locally, while OpenAI is used only to compose the final answer from retrieved page excerpts.

*   **Interface:** Streamlit (`app.py`) provides the submitted chat UI and PDF upload flow.
*   **Agent core:** `pdf_rag.py` handles PDF validation, page-text extraction, retrieval, prompt construction, OpenAI calls, fallback behavior, and citation/refusal validation.
*   **AI engine:** OpenAI Responses API with `gpt-4.1-mini` by default.
*   **Session state:** Uploaded PDFs are stored in Streamlit session state as `PdfDocument` objects containing page-numbered text. Conversation history is also held in Streamlit session state.
*   **Demo affordance:** When the uploaded file is exactly `sample.pdf`, the UI displays one-click sample questions. These buttons call the same grounded chat path as manually typed prompts and are not shown for other PDFs.

## 2. Key Technical Decisions

### Local Page Extraction
The app uses PyMuPDF to extract text page-by-page before any model call.
*   **Reasoning:** The assignment requires page citations. Keeping page numbers in our own data structure makes citation validation deterministic and independent of provider-specific file citation behavior.

### Page-Grounded Retrieval
For each question, the system performs lightweight lexical retrieval over page text and sends only the selected page excerpts to the model.
*   **Reasoning:** This reduces prompt size, makes the context auditable, and improves out-of-scope behavior because the model sees a constrained evidence set rather than the whole internet or prior knowledge.

### Strict Prompt + Local Output Guard
The model is instructed to answer only from retrieved excerpts and cite every factual claim as `(Page N)`. After generation, a local guard:
*   converts empty output to the exact refusal string;
*   normalizes any refusal-like response to the exact required line;
*   refuses non-refusal answers without `(Page N)` citations;
*   refuses answers citing pages that were not supplied in retrieved context.

### Extractive Quota Fallback
If OpenAI returns an insufficient-quota billing error and `ALLOW_EXTRACTIVE_FALLBACK=true`, the system falls back to a deterministic local answer assembled from retrieved PDF sentences. This keeps the demo usable without external generation, while remaining strictly grounded.
*   **Reasoning:** The fallback is less fluent than the model path, but it is safer than returning an API error during evaluation.

### Conversational Querying
Recent conversation turns are included in the retrieval query and prompt context.
*   **Reasoning:** This supports follow-up questions while still forcing the final answer to come from retrieved PDF pages.

### Multilingual Support
The prompt allows the model to answer in the user's requested language while keeping citations in the exact `(Page N)` format.
*   **Reasoning:** This gives multilingual behavior without adding a separate translation layer.

## 3. Trade-offs and Limitations

### Text PDFs vs. Scanned PDFs
*   **Trade-off:** PyMuPDF extraction is reliable for text-based PDFs but does not OCR scanned image-only documents.
*   **Mitigation for Production:** Add OCR or use a multimodal PDF pipeline for scanned PDFs, while preserving page-numbered evidence.

### Lexical Retrieval vs. Embeddings
*   **Trade-off:** Lexical retrieval avoids extra services and is deterministic, but semantic retrieval would perform better on paraphrased questions in large documents.
*   **Mitigation for Production:** Add OpenAI embeddings or a vector store, keeping page numbers attached to every chunk.

### In-Memory State
*   **Trade-off:** Streamlit session state keeps the assessment easy to run, but it is not designed for horizontal scaling across many server instances.
*   **Mitigation for Production:** Store extracted page text and session history in Redis/PostgreSQL and add cleanup for inactive sessions.

### Guardrail Strictness
*   **Trade-off:** The output guard may refuse a valid answer if the model forgets citation syntax.
*   **Mitigation for Production:** Add a repair pass that asks the model to add citations only when the cited evidence is present.

### Extractive Fallback Quality
*   **Trade-off:** The quota fallback can answer simple factual questions, definitions, and summaries, but it is not as good as the LLM path for nuanced synthesis.
*   **Mitigation for Production:** Keep a funded API project for evaluation, or use embeddings plus a stronger local summarization model.

## 4. Deployment Thinking

For the assessment, deploy `app.py` on Streamlit Community Cloud and store `OPENAI_API_KEY` as a Streamlit secret. For production, move session state to a shared store, set upload limits, add OCR for scanned PDFs, and log retrieved page IDs plus model outputs for observability.
