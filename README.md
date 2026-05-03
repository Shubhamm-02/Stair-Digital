# PDF-Grounded Chatbot

A Streamlit chatbot that answers questions strictly from a user-supplied PDF. It extracts page text locally with PyMuPDF, retrieves relevant pages, and uses the OpenAI Responses API only over those retrieved excerpts. Out-of-scope questions are refused with a fixed message; in-scope answers include page-number citations.

The submitted interface is [app.py](app.py). The shared agent logic lives in [pdf_rag.py](pdf_rag.py).

## How Grounding Works

- The PDF is parsed locally with **PyMuPDF** into page-numbered text.
- A lightweight lexical retriever selects the most relevant pages for each user question.
- OpenAI receives only retrieved page excerpts, recent conversation context, and the current user question.
- The prompt requires exact refusal when the retrieved pages do not support the answer:
  `This question is outside the scope of the provided PDF.`
- A local output guard normalizes refusals, rejects uncited answers, and rejects citations to pages that were not supplied in the retrieved context.
- The default model is `gpt-4.1-mini`, configurable with `OPENAI_MODEL`.
- If the OpenAI account has no quota, `ALLOW_EXTRACTIVE_FALLBACK=true` enables a conservative local fallback that returns retrieved PDF sentences with page citations.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then paste your OPENAI_API_KEY into .env
```

Optional model settings:

```bash
OPENAI_MODEL=gpt-4.1-mini
OPENAI_FALLBACK_MODELS=
ALLOW_EXTRACTIVE_FALLBACK=true
```

## Run Locally

```bash
source venv/bin/activate
streamlit run app.py
```

Streamlit opens a local browser tab. Upload `sample.pdf`, then ask questions from [test_queries.md](test_queries.md).

## Files

- [app.py](app.py) — Streamlit interface
- [pdf_rag.py](pdf_rag.py) — PDF extraction, retrieval, OpenAI call, fallback, and citation guard
- [requirements.txt](requirements.txt) — Python dependencies
- [.env.example](.env.example) — environment variable template
- [sample.pdf](sample.pdf) — sample PDF used for testing
- [test_queries.md](test_queries.md) — 5 valid + 3 invalid test queries with expected behavior
- [TECHNICAL_NOTE.md](TECHNICAL_NOTE.md) — architecture, decisions, trade-offs
- [TEST_INSTRUCTIONS.md](TEST_INSTRUCTIONS.md) — evaluator setup and manual acceptance checks

## Testing

After uploading `sample.pdf`, run each query in [test_queries.md](test_queries.md) and confirm:

- valid queries -> answer is correct relative to the PDF and includes a `(Page N)` citation,
- invalid queries -> response is exactly: `This question is outside the scope of the provided PDF.`

Optional multilingual check: ask a valid question in Hindi, Spanish, or another language. The answer should stay in that language while preserving `(Page N)` citations. Unsupported questions should still return the exact refusal string.
