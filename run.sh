#!/usr/bin/env bash
# One-command launcher for macOS / Linux:  ./run.sh
set -e
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else
  echo "Python was not found. Install Python 3.10+ from https://www.python.org/downloads/"
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Creating a private Python environment..."
  $PY -m venv .venv
fi

if [ ! -f ".venv/.installed" ]; then
  echo "Installing packages (first run only, takes a few minutes)..."
  .venv/bin/python -m pip install --upgrade pip >/dev/null 2>&1 || true
  .venv/bin/python -m pip install -r requirements.txt
  echo done > .venv/.installed
fi

# skip Streamlit's first-run email question
if [ ! -f "$HOME/.streamlit/credentials.toml" ]; then
  mkdir -p "$HOME/.streamlit"
  printf '[general]\nemail = ""\n' > "$HOME/.streamlit/credentials.toml"
fi

echo "Starting the chatbot. Your browser will open in a moment."
.venv/bin/python -m streamlit run app.py
