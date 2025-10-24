"""
py2app setup script for Dictator.

This creates a standalone macOS .app bundle that can be:
- Launched like any normal Mac application
- Added to Login Items
- Distributed to other users

Usage:
    python setup.py py2app
"""

from setuptools import setup

APP = ['run_dictator.py']
DATA_FILES = []
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

setup(
    name='Dictator',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
