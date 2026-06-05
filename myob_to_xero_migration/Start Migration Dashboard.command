#!/usr/bin/env bash
# macOS double-click launcher for the MYOB → Xero migration dashboard.
# Double-click in Finder; the first run sets up a virtualenv and installs
# dependencies (~30s), subsequent runs start in a few seconds.

set -e
cd "$(dirname "$0")"

echo "============================================================"
echo "  MYOB → Xero migration — Dashboard launcher (macOS)"
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
    echo "Install from https://www.python.org/downloads/ and try again."
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
echo "(Close this window to stop the dashboard.)"
echo

# Open the browser shortly after Streamlit binds.
( sleep 2 && open "${URL}" >/dev/null 2>&1 ) &

exec streamlit run dashboard.py \
    --server.port "${PORT}" \
    --server.headless true \
    --browser.gatherUsageStats false
