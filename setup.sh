#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 not found. Install from https://www.python.org/downloads/ first."
  exit 1
fi

echo "Creating virtual environment..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing Python dependencies..."
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "Ensuring Google Chrome is available to Playwright..."
python -m playwright install chrome

echo ""
echo "Setup complete."
echo "Next: ./run.sh \"<paste-your-sales-nav-search-url>\""
