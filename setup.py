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
    'compressed': False,  # Don't create python312.zip - needed for notarization
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
        'pydub',
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
        'dictator.ui.file_processor',
        'dictator.services.llm_corrector',
        'dictator.services.audio_processor',
        'dictator.services.audio_converter',
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

# Sign the app after building if identity is provided
if CODESIGN_IDENTITY and __name__ == '__main__':
    import subprocess
    import sys
    import glob

    # Only sign if we're actually building (not just installing)
    if 'py2app' in sys.argv:
        print(f"\n🔐 Code signing with: {CODESIGN_IDENTITY}")

        app_path = 'dist/Dictator.app'

        # Sign options for all binaries
        sign_opts = [
            'codesign',
            '--force',
            '--options', 'runtime',
            '--timestamp',
            '--sign', CODESIGN_IDENTITY
        ]

        # Find all .so and .dylib files
        binaries = []
        binaries.extend(glob.glob(f'{app_path}/**/*.so', recursive=True))
        binaries.extend(glob.glob(f'{app_path}/**/*.dylib', recursive=True))

        print(f"  → Found {len(binaries)} binaries to sign")

        # Sign each binary individually
        for i, binary in enumerate(binaries, 1):
            print(f"  [{i}/{len(binaries)}] Signing: {os.path.basename(binary)}")
            result = subprocess.run(
                sign_opts + [binary],
                capture_output=True,
                text=True
            )
            if result.returncode != 0 and 'is already signed' not in result.stderr:
                print(f"    ⚠️  Warning: {result.stderr.strip()}")

        # Sign frameworks if they exist
        frameworks = glob.glob(f'{app_path}/Contents/Frameworks/*.framework')
        if frameworks:
            print(f"  → Signing {len(frameworks)} frameworks")
            for framework in frameworks:
                print(f"    Signing: {os.path.basename(framework)}")
                subprocess.run(sign_opts + [framework], capture_output=True)

        # Finally sign the main app bundle
        print("  → Signing main app bundle...")
        result = subprocess.run(
            sign_opts + [app_path],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("  ✅ Code signing complete!")

            # Verify signature
            print("\n  Verifying signature...")
            verify_result = subprocess.run([
                'codesign',
                '--verify',
                '--deep',
                '--strict',
                '--verbose=2',
                app_path
            ], capture_output=True, text=True)

            if verify_result.returncode == 0:
                print(f"  ✅ Signature verified: {app_path}")
            else:
                print(f"  ⚠️  Verification failed: {verify_result.stderr}")
        else:
            print(f"  ⚠️  Code signing failed")
            print(f"  Error: {result.stderr}")
            print(f"  → App will be ad-hoc signed instead")
            # Don't fail the build, just continue without proper signing
