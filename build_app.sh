#!/bin/bash
# Build script for Dictator.app
#
# Usage:
#   ./build_app.sh           # Build full standalone .app
#   ./build_app.sh --alias   # Build development alias mode

set -e

cd "$(dirname "$0")"

echo "🔨 Building Dictator.app..."
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build dist

# Build the app
if [ "$1" == "--alias" ]; then
    echo "📦 Building in alias mode (development)..."
    ./venv/bin/python setup.py py2app -A
else
    echo "📦 Building standalone .app bundle..."
    ./venv/bin/python setup.py py2app
fi

echo ""
echo "✅ Build complete!"
echo ""
echo "The app is located at: dist/Dictator.app"
echo ""
echo "To run it:"
echo "  open dist/Dictator.app"
echo ""
echo "To install it:"
echo "  cp -R dist/Dictator.app /Applications/"
echo ""
