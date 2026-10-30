"""
app.py - the web page (built with Streamlit).

Run with:  streamlit run app.py   (or just double-click run.bat on Windows)

Author: V. Srinivasa Reddy
"""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

import rag_engine as rag

load_dotenv()  # reads OPENAI_API_KEY from a .env file if you made one (optional)

SAMPLE_PATH = Path(__file__).parent / "sample.txt"

st.set_page_config(page_title="RAG Document Chatbot", page_icon="📄", layout="wide")
st.title("📄 RAG Document Q&A Chatbot")
st.caption("Upload a document, ask questions, and get answers taken from it.")

if "messages" not in st.session_state:
    st.session_state.messages = []

# ----------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    typed_key = st.text_input(
        "OpenAI API key (optional)",
        type="password",
        value=os.getenv("OPENAI_API_KEY", ""),
        placeholder="sk-...",
        help="Leave empty to use free offline mode: the app will show the most "
             "relevant passages from your document instead of a written answer.",
    )
    api_key = typed_key.strip()
    if api_key and not api_key.startswith("sk-"):
        st.warning("That doesn't look like an OpenAI key (they start with 'sk-'). "
                   "Using offline mode.")
        api_key = ""

    chat_model = st.text_input("Chat model", value=rag.DEFAULT_CHAT_MODEL)
    top_k = st.slider("Passages to retrieve", min_value=1, max_value=8, value=4)

    if st.button("🗑️ Clear chat"):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.caption("Built by V. Srinivasa Reddy")


# --------------------------------------------------------------- documents
def get_documents() -> list[tuple[str, bytes]]:
    uploaded = st.file_uploader(
        "Upload one or more documents",
        type=["pdf", "txt"],
        accept_multiple_files=True,
    )
    if uploaded:
        st.session_state.use_sample = False
        return [(f.name, f.getvalue()) for f in uploaded]
    if st.session_state.get("use_sample") and SAMPLE_PATH.exists():
        return [(SAMPLE_PATH.name, SAMPLE_PATH.read_bytes())]
    return []


docs = get_documents()

if not docs:
    st.info("👆 Upload a PDF or TXT file to begin, or try the built-in sample.")
    if SAMPLE_PATH.exists() and st.button("Try the sample document"):
        st.session_state.use_sample = True
        st.rerun()
    st.stop()

# Build the search index only when the files or key change (not on every click).
sig = rag.signature(docs, api_key)
if st.session_state.get("sig") != sig:
    with st.spinner("Reading and indexing your document(s)..."):
        try:
            chunks = rag.build_chunks(docs)
        except Exception as exc:
            st.error(f"Sorry, I could not read that file: {exc}")
            st.stop()

        if not chunks:
            st.error("No readable text was found. If this is a scanned PDF "
                     "(pictures of pages), it needs OCR first.")
            st.stop()

        client = rag.make_client(api_key)
        try:
            index = rag.Index(chunks, client)
        except Exception as exc:
            st.error(str(exc))
            st.stop()

    st.session_state.update(sig=sig, index=index, client=client, messages=[])

index: rag.Index = st.session_state.index
client = st.session_state.client

if index.mode == "openai":
    st.success(f"Ready ✅  {len(index.chunks)} passages indexed. AI answers are ON.")
else:
    st.info(f"Ready ✅  {len(index.chunks)} passages indexed. "
            "Offline mode: I'll show the most relevant passages "
            "(add an OpenAI key in the sidebar for written answers).")
    if index.error:
        st.warning(f"AI mode was skipped. {index.error}")


# -------------------------------------------------------------------- chat
def show_sources(sources: list[dict]) -> None:
    with st.expander("📚 Sources used"):
        for s in sources:
            st.markdown(f"**{s['source']} - page {s['page']}**")
            st.write(s["text"])


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            show_sources(message["sources"])

question = st.chat_input("Ask a question about your document(s)...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply, sources = "", []
            try:
                hits = index.search(question, k=top_k)
            except Exception as exc:
                hits = []
                reply = f"⚠️ Search failed: {exc}"

            if not reply:
                if not hits:
                    reply = ("I couldn't find anything related to that in your "
                             "document(s). Try rephrasing the question.")
                else:
                    sources = [
                        {"source": h.chunk.source, "page": h.chunk.page, "text": h.chunk.text}
                        for h in hits
                    ]
                    if index.mode == "openai" and client is not None:
                        try:
                            reply = rag.answer(client, chat_model, question, hits)
                        except Exception as exc:
                            reply = (f"⚠️ {rag.explain_error(exc)}\n\n"
                                     "Here are the most relevant passages instead:")
                    if not reply or reply.startswith("⚠️"):
                        passages = "\n\n".join(
                            f"> **{s['source']} - page {s['page']}**\n>\n> {s['text']}"
                            for s in sources
                        )
                        prefix = reply or "**Most relevant passages from your document:**"
                        reply = f"{prefix}\n\n{passages}"
                        sources = []  # already shown inline

        st.markdown(reply)
        if sources:
            show_sources(sources)

    st.session_state.messages.append(
        {"role": "assistant", "content": reply, "sources": sources}
    )
