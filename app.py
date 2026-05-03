import streamlit as st
from dotenv import load_dotenv

from pdf_rag import (
    DEFAULT_MODEL,
    MODEL_CANDIDATES,
    REFUSAL,
    answer_question,
    extract_pdf_document,
    get_openai_client,
)

load_dotenv()


def main() -> None:
    st.set_page_config(page_title="PDF Chatbot", page_icon=":page_facing_up:")
    st.title("PDF-Grounded Chatbot")
    st.caption("Answers strictly from the uploaded PDF, with page citations.")

    try:
        client = get_openai_client()
    except Exception as error:
        st.error(str(error))
        st.stop()

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "document" not in st.session_state:
        st.session_state.document = None
    if "pdf_name" not in st.session_state:
        st.session_state.pdf_name = None

    with st.sidebar:
        st.header("PDF")
        uploaded = st.file_uploader("Upload a PDF", type="pdf")
        if uploaded is not None and uploaded.name != st.session_state.pdf_name:
            with st.spinner("Extracting PDF pages..."):
                document = extract_pdf_document(uploaded.getvalue(), uploaded.name)
                st.session_state.document = document
                st.session_state.pdf_name = uploaded.name
                st.session_state.messages = []
            st.success(f"Loaded {uploaded.name} ({len(document.pages)} text pages)")

        if st.session_state.pdf_name:
            st.write(f"**Active PDF:** {st.session_state.pdf_name}")
            st.write(f"**Text pages:** {len(st.session_state.document.pages)}")
            st.write(f"**Model:** {DEFAULT_MODEL}")
            if st.button("Reset conversation"):
                st.session_state.messages = []
                st.rerun()

        st.divider()
        st.caption("Model order: " + ", ".join(MODEL_CANDIDATES))
        st.markdown(
            "**Behavior**\n\n"
            "- Extracts text page-by-page locally\n"
            "- Retrieves only relevant pages\n"
            "- Answers only from retrieved PDF text\n"
            "- Cites pages inline\n"
            f"- Refuses out-of-scope with: _{REFUSAL}_"
        )

    if st.session_state.document is None:
        st.info("Upload a PDF in the sidebar to begin.")
        st.stop()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Ask about the PDF...")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        try:
            answer = answer_question(
                client=client,
                document=st.session_state.document,
                question=prompt,
                history=st.session_state.messages[:-1],
            )
        except Exception as error:
            answer = f"Error contacting OpenAI: {error}"
        placeholder.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
