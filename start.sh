#!/bin/bash
# Dictator startup script

cd "$(dirname "$0")"

echo "🎙️  Starting Dictator..."
echo ""
echo "Look for the ⚪ icon in your menubar"
echo "Press Option+Space to start/stop recording"
echo ""
echo "Press Ctrl+C to quit"
echo ""

./venv/bin/python run_dictator.py
