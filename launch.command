#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR" || exit 1

echo "================================================="
echo "   🚀 Launching CareerOS Dashboard..."
echo "================================================="

# If already running, open browser and exit
if pgrep -f "streamlit run src/app.py" > /dev/null; then
    echo "CareerOS is already active! Opening in browser..."
    open "http://localhost:8501"
    exit 0
fi

# Run Streamlit
exec "./venv/bin/streamlit" run src/app.py
