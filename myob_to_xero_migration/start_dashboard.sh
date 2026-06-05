#!/usr/bin/env bash
# Linux launcher for the MYOB → Xero migration dashboard.
# Run from a file manager (Files / Nautilus) by marking executable, or from a
# terminal with: ./start_dashboard.sh

set -e
cd "$(dirname "$0")"

echo "============================================================"
echo "  MYOB → Xero migration — Dashboard launcher (Linux)"
echo "============================================================"
echo

PY=""
for cand in python3.12 python3.11 python3.10 python3; do
    if command -v "$cand" >/dev/null 2>&1; then
        PY="$cand"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "ERROR: Python 3.10+ not found."
    echo "Install it (e.g. sudo apt install python3 python3-venv) and try again."
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
fi
echo "Using $PY ($($PY --version))"

if [ ! -d ".venv" ]; then
    echo "First-run setup: creating virtual environment..."
    "$PY" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing / verifying dependencies (quietly)..."
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

PORT=8501
URL="http://localhost:${PORT}"

echo
echo "Starting dashboard at ${URL}"
echo "(Press Ctrl+C to stop.)"
echo

# Open the browser shortly after Streamlit binds.
( sleep 2 && xdg-open "${URL}" >/dev/null 2>&1 || true ) &

exec streamlit run dashboard.py \
    --server.port "${PORT}" \
    --server.headless true \
    --browser.gatherUsageStats false
