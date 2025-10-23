#!/bin/bash
# Dictator - Quick Setup

set -e
cd "$(dirname "$0")"

echo ""
echo "🎙️  Installing Dictator..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Install from https://www.python.org"
    exit 1
fi

# Create venv and install
[ -d "venv" ] || python3 -m venv venv
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q
./venv/bin/pip install -e . -q

echo "✅ Installed!"
echo ""
echo "📋 Next: Grant permissions"
echo ""

# Resolve the actual Python executable (not the symlink)
PYTHON_REAL=$(readlink -f ./venv/bin/python 2>/dev/null || realpath ./venv/bin/python 2>/dev/null || ./venv/bin/python -c "import sys; print(sys.executable)")

echo "   System Settings → Privacy & Security → Accessibility"
echo "   Add this file:"
echo ""
echo "   $PYTHON_REAL"
echo ""
echo "   (Path copied to clipboard - paste with Cmd+Shift+G)"
echo ""

# Copy path to clipboard
echo "$PYTHON_REAL" | pbcopy

echo "Then run: ./start.sh"
echo ""
