"""
rag_engine.py - the "brain" of the chatbot.

What it does, in plain steps:
  1. read_document()  -> pull the text out of a PDF / TXT file
  2. split_text()     -> cut the text into small overlapping chunks
  3. Index            -> make chunks searchable
                         (OpenAI embeddings if you have a key, otherwise a free
                          offline TF-IDF search that needs no internet or key)
  4. Index.search()   -> find the chunks most related to a question
  5. answer()         -> ask an OpenAI chat model to answer from those chunks

Author: V. Srinivasa Reddy
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

EMBED_MODEL = "text-embedding-3-small"
DEFAULT_CHAT_MODEL = "gpt-4o-mini"


# --------------------------------------------------------------------------
# Data containers
# --------------------------------------------------------------------------
@dataclass
class Chunk:
    text: str
    source: str  # file name
    page: int    # page number (1 for text files)


@dataclass
class Hit:
    chunk: Chunk
    score: float


# --------------------------------------------------------------------------
# 1. Reading documents
# --------------------------------------------------------------------------
def read_document(name: str, data: bytes) -> list[tuple[int, str]]:
    """Return a list of (page_number, text). Empty pages are skipped."""
    if name.lower().endswith(".pdf"):
        import fitz  # PyMuPDF (imported here so the rest works without it)

        pages: list[tuple[int, str]] = []
        with fitz.open(stream=data, filetype="pdf") as doc:
            for number, page in enumerate(doc, start=1):
                text = page.get_text().strip()
                if text:
                    pages.append((number, text))
        return pages

    text = data.decode("utf-8", errors="ignore").strip()
    return [(1, text)] if text else []


# --------------------------------------------------------------------------
# 2. Splitting text into chunks
# --------------------------------------------------------------------------
def split_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    """Cut text into ~`size` character pieces. Neighbouring pieces share
    `overlap` characters so a sentence cut in half is not lost."""
    text = " ".join(text.split())  # tidy up whitespace / line breaks
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # try to end the chunk at a sentence end or a space
            window_start = start + int(size * 0.6)
            cut = max(text.rfind(". ", window_start, end),
                      text.rfind(" ", window_start, end))
            if cut != -1:
                end = cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def build_chunks(files: list[tuple[str, bytes]]) -> list[Chunk]:
    """files = [(file_name, file_bytes), ...]  ->  list of Chunk"""
    chunks: list[Chunk] = []
    for name, data in files:
        for page_number, page_text in read_document(name, data):
            for piece in split_text(page_text):
                chunks.append(Chunk(text=piece, source=name, page=page_number))
    return chunks


def signature(files: list[tuple[str, bytes]], api_key: str) -> str:
    """A fingerprint of the uploaded files + key, used to know when to rebuild."""
    h = hashlib.sha256()
    for name, data in files:
        h.update(name.encode())
        h.update(data)
    h.update(api_key.encode())
    return h.hexdigest()


# --------------------------------------------------------------------------
# OpenAI helpers
# --------------------------------------------------------------------------
def make_client(api_key: str):
    """Return an OpenAI client, or None if there is no usable key."""
    api_key = (api_key or "").strip()
    if not api_key:
        return None
    try:
        from openai import OpenAI

        return OpenAI(api_key=api_key, timeout=30, max_retries=2)
    except Exception:
        return None


def explain_error(exc: Exception) -> str:
    """Turn a scary traceback into a one-line, human explanation."""
    name = type(exc).__name__
    if name == "AuthenticationError":
        return "OpenAI rejected the API key (it may be wrong or expired)."
    if name == "RateLimitError":
        return "OpenAI says the quota or rate limit was reached (check billing/credits)."
    if name in ("APIConnectionError", "APITimeoutError"):
        return "Could not reach OpenAI (check your internet connection)."
    if name == "NotFoundError":
        return "OpenAI does not recognise that model name for your account."
    return f"OpenAI error: {exc}"


def _embed(client, texts: list[str], model: str = EMBED_MODEL) -> np.ndarray:
    vectors: list[list[float]] = []
    for i in range(0, len(texts), 96):  # send in small batches
        response = client.embeddings.create(model=model, input=texts[i:i + 96])
        vectors.extend(item.embedding for item in response.data)
    matrix = np.array(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms  # unit length -> dot product == cosine similarity


# --------------------------------------------------------------------------
# 3 + 4. The searchable index
# --------------------------------------------------------------------------
class Index:
    """Makes chunks searchable.

    mode == "openai": meaning-based search using OpenAI embeddings.
    mode == "local" : keyword-based TF-IDF search, works with no key, no internet.
    If OpenAI fails for any reason, we quietly fall back to "local" and keep
    the reason in `self.error` so the app can tell the user.
    """

    def __init__(self, chunks: list[Chunk], client=None):
        self.chunks = chunks
        self.client = client
        self.mode = "local"
        self.error: str | None = None
        texts = [c.text for c in chunks]

        if client is not None:
            try:
                self.matrix = _embed(client, texts)
                self.mode = "openai"
            except Exception as exc:  # any failure -> fall back, never crash
                self.error = explain_error(exc)

        if self.mode == "local":
            self._build_tfidf(texts)

    def _build_tfidf(self, texts: list[str]) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        attempts = [
            dict(stop_words="english", ngram_range=(1, 2), sublinear_tf=True),
            dict(ngram_range=(1, 2), sublinear_tf=True),
            dict(token_pattern=r"(?u)\b\w+\b"),
        ]
        last_error: Exception | None = None
        for options in attempts:
            try:
                self.vectorizer = TfidfVectorizer(**options)
                self.tfidf = self.vectorizer.fit_transform(texts)
                return
            except ValueError as exc:  # e.g. "empty vocabulary"
                last_error = exc
        raise ValueError(f"Could not index this document: {last_error}")

    def search(self, query: str, k: int = 4) -> list[Hit]:
        if self.mode == "openai":
            try:
                q = _embed(self.client, [query])[0]
                scores = self.matrix @ q
            except Exception as exc:
                raise RuntimeError(explain_error(exc)) from exc
        else:
            from sklearn.metrics.pairwise import linear_kernel

            scores = linear_kernel(self.vectorizer.transform([query]), self.tfidf)[0]

        best = np.argsort(scores)[::-1][:k]
        return [
            Hit(self.chunks[i], float(scores[i]))
            for i in best
            if scores[i] > 0  # ignore chunks with nothing in common
        ]


# --------------------------------------------------------------------------
# 5. Asking the chat model
# --------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions using ONLY the context "
    "taken from the user's documents. If the answer is not in the context, say "
    "you could not find it in the documents - do not guess. Keep answers clear "
    "and concise, and mention the source file and page when it helps."
)


def answer(client, model: str, question: str, hits: list[Hit]) -> str:
    context = "\n\n".join(
        f"[{h.chunk.source}, page {h.chunk.page}]\n{h.chunk.text}" for h in hits
    )
    response = client.chat.completions.create(
        model=model or DEFAULT_CHAT_MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    return (response.choices[0].message.content or "").strip()
