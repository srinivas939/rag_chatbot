# 📄 RAG Document Q&A Chatbot

Upload a PDF or text file, ask questions in plain English, and get answers taken from **your** document.

**Author:** V. Srinivasa Reddy
[LinkedIn](https://www.linkedin.com/in/v-srinivasareddy-238905293/) · [GitHub](https://github.com/srinivas939)

> Acknowledgement: this project grew out of the open-source `rag-chatbot` by Y. Sree Ranga Rohith.
> This version is a rewrite with a new engine, offline mode, chat interface, multi-file support and one-click setup.

---

## ✨ Features

- Upload **multiple PDF / TXT files** at once
- **Works with or without an OpenAI key**
  - With a key: written, conversational answers
  - Without a key: free **offline mode** that shows the most relevant passages
- Shows the **source file and page** for every answer
- Chat-style interface with history
- Friendly error messages and automatic fallback, so the app never crashes on a bad key or lost internet
- Built-in sample document to try instantly

---

## 🚀 Quick start

**Windows:** double-click **`run.bat`**
**Mac / Linux:** run `./run.sh` in a terminal

The first run creates a private environment and installs everything (a few minutes, needs internet). After that it starts instantly. Your browser opens automatically at `http://localhost:8501`.

You only need **Python 3.10 or newer** ([download](https://www.python.org/downloads/), tick *"Add Python to PATH"* on Windows).

### Adding an OpenAI key (optional)

Either paste it into the **sidebar** of the app, or copy `.env.example` to `.env` and put the key after `OPENAI_API_KEY=`.

---

## 🧠 How it works

```
Document → extract text → split into chunks → make searchable
                                                    ↑ search
Your question ──────────────────────────────────────┘
                                                    ↓
                    best chunks + question → AI model → Answer + sources
```

1. **Read** the PDF with PyMuPDF.
2. **Chunk** the text into ~800-character pieces that overlap a little.
3. **Index** the chunks: OpenAI embeddings (meaning-based) if you have a key, otherwise TF-IDF (keyword-based).
4. **Retrieve** the chunks closest to your question.
5. **Generate** an answer from only those chunks (or display them directly in offline mode).

---

## 📁 Project structure

| File | Purpose |
|---|---|
| `app.py` | The web page (Streamlit) |
| `rag_engine.py` | Reading, chunking, searching, asking the AI |
| `requirements.txt` | Python packages needed |
| `run.bat` / `run.sh` | One-click setup and launch |
| `sample.txt` | Demo document |
| `.env.example` | Template for your optional API key |

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| "Python was not found" | Install Python 3.10+ and tick *Add Python to PATH* |
| Setup fails | Check internet, delete the `.venv` folder, run again |
| "No readable text found" | The PDF is scanned images; it needs OCR first |
| Answers say AI mode was skipped | Key is wrong/expired or has no credit; offline mode still works |
| Port already in use | Close the other Streamlit window, or run `streamlit run app.py --server.port 8502` |

---

## 💡 Ideas to extend it

- Add OCR for scanned PDFs
- Save the index to disk so large documents load instantly
- Support Word files and web pages
- Use a local model (Ollama) for fully offline written answers
