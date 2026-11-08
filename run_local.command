#!/bin/zsh
set -e
cd "$(dirname "$0")"
if python3 -c 'import flask, openpyxl' >/dev/null 2>&1; then
  exec python3 main.py
fi
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi
exec .venv/bin/python main.py
