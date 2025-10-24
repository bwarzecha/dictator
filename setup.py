"""
py2app setup script for Dictator.

This creates a standalone macOS .app bundle that can be:
- Launched like any normal Mac application
- Added to Login Items
- Distributed to other users

Usage:
    python setup.py py2app                    # Ad-hoc signing
    CODESIGN_IDENTITY="..." python setup.py py2app  # With code signing
"""

from setuptools import setup
import os

APP = ['run_dictator.py']
DATA_FILES = []

# Get code signing identity from environment (optional)
CODESIGN_IDENTITY = os.environ.get('CODESIGN_IDENTITY')

OPTIONS = {
    'argv_emulation': False,  # Don't emulate argv for drag-and-drop
    'iconfile': 'icon.icns',  # Custom app icon
    'plist': {
        'CFBundleName': 'Dictator',
        'CFBundleDisplayName': 'Dictator',
        'CFBundleIdentifier': 'com.dictator.app',
        'CFBundleVersion': '0.1.0',
        'CFBundleShortVersionString': '0.1.0',
        'LSUIElement': True,  # Run as menubar app (no dock icon)
        'NSMicrophoneUsageDescription': 'Dictator needs microphone access to record your voice for transcription.',
        'NSAccessibilityUsageDescription': 'Dictator needs accessibility access to insert transcribed text into any application.',
        # Input Monitoring permission
        'NSAppleEventsUsageDescription': 'Dictator needs to monitor keyboard events to detect the global hotkey (Option+Space).',
    },
    'packages': [
        'rumps',
        'pynput',
        'sounddevice',
        'numpy',
        'pywhispercpp',
        'PyQt6',
        'dictator',
        'AppKit',
        'Foundation',
        'ApplicationServices',
        'boto3',  # For AWS Bedrock LLM
    ],
    'includes': [
        'dictator.main',
        'dictator.app',
        'dictator.models',
        'dictator.audio',
        'dictator.transcription',
        'dictator.insertion',
        'dictator.storage',
        'dictator.hotkey',
        'dictator.ui.history',
        'dictator.ui.settings',
        'dictator.services.llm_corrector',
    ],
    'excludes': [
        'matplotlib',  # Don't need plotting
        'PIL',  # Don't need image processing
        'tkinter',  # Don't use Tkinter
    ],
    'site_packages': True,  # Include all site-packages
    'strip': False,  # Keep symbols for debugging
    'semi_standalone': False,  # Include Python framework
}

# Add code signing options if identity is provided
if CODESIGN_IDENTITY:
    print(f"🔐 Code signing enabled: {CODESIGN_IDENTITY}")
    OPTIONS.update({
        'codesign_identity': CODESIGN_IDENTITY,
        'codesign_options': 'runtime',  # Hardened runtime for notarization
        'codesign_deep': True,  # Deep sign all embedded frameworks
    })
else:
    print("⚠️  Code signing disabled (ad-hoc signing will be used)")

setup(
    name='Dictator',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
