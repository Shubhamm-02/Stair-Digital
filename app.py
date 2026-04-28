import os
import tempfile

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

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


def get_client() -> genai.Client | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def upload_pdf(client: genai.Client, file_bytes: bytes, display_name: str):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    return client.files.upload(
        file=tmp_path,
        config={"display_name": display_name, "mime_type": "application/pdf"},
    )


def new_chat(client: genai.Client):
    return client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,
        ),
    )


def main() -> None:
    st.set_page_config(page_title="PDF Chatbot", page_icon="📄")
    st.title("📄 PDF-Grounded Chatbot")
    st.caption("Answers strictly from the uploaded PDF, with page citations.")

    client = get_client()
    if client is None:
        st.error(
            "GEMINI_API_KEY is not set. Copy `.env.example` to `.env` and add your key."
        )
        st.stop()

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "chat" not in st.session_state:
        st.session_state.chat = None
    if "pdf_file" not in st.session_state:
        st.session_state.pdf_file = None
    if "pdf_name" not in st.session_state:
        st.session_state.pdf_name = None

    with st.sidebar:
        st.header("PDF")
        uploaded = st.file_uploader("Upload a PDF", type="pdf")
        if uploaded is not None and uploaded.name != st.session_state.pdf_name:
            with st.spinner("Uploading PDF to Gemini…"):
                pdf_file = upload_pdf(client, uploaded.getvalue(), uploaded.name)
                st.session_state.pdf_file = pdf_file
                st.session_state.pdf_name = uploaded.name
                st.session_state.chat = new_chat(client)
                st.session_state.messages = []
            st.success(f"Loaded: {uploaded.name}")

        if st.session_state.pdf_name:
            st.write(f"**Active PDF:** {st.session_state.pdf_name}")
            if st.button("Reset conversation"):
                st.session_state.chat = new_chat(client)
                st.session_state.messages = []
                st.rerun()

        st.divider()
        st.markdown(
            "**Behavior**\n\n"
            "- Answers only from the PDF\n"
            "- Cites pages inline\n"
            f"- Refuses out-of-scope with: _{REFUSAL}_"
        )

    if st.session_state.pdf_file is None:
        st.info("Upload a PDF in the sidebar to begin.")
        st.stop()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Ask about the PDF…")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    is_first_turn = len(st.session_state.messages) == 1
    if is_first_turn:
        message = [st.session_state.pdf_file, prompt]
    else:
        message = prompt

    with st.chat_message("assistant"):
        placeholder = st.empty()
        try:
            response = st.session_state.chat.send_message(message)
            answer = response.text or ""
        except Exception as e:
            answer = f"Error contacting Gemini: {e}"
        placeholder.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
