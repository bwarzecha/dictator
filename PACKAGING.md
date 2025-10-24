# Packaging Dictator as a macOS Application

This document explains how Dictator is packaged as a standalone macOS `.app` bundle.

## Overview

We use **py2app** to create a native macOS application bundle. This solves several problems:

- ✅ No need to run from terminal
- ✅ Can be added to Login Items
- ✅ Proper Info.plist with permissions
- ✅ Notifications work without hacks
- ✅ Can be distributed as DMG
- ✅ Works like any other Mac app

## Building the App

### Local Build

```bash
# Build standalone .app (for distribution)
./build_app.sh

# Build in alias mode (for development - faster, links to source)
./build_app.sh --alias
```

The app will be created in `dist/Dictator.app`.

### Manual Build

```bash
# Standalone build
python setup.py py2app

# Development build (alias mode)
python setup.py py2app -A
```

## Automated Builds (GitHub Actions)

Every push to `main` triggers a build workflow that:

1. Sets up Python 3.12 on macOS
2. Installs all dependencies
3. Builds the .app bundle
4. Uploads as artifact (available for 30 days)

For tagged releases (`v*`):
1. All of the above, plus:
2. Creates a DMG file
3. Uploads DMG as artifact (90 days)
4. Creates GitHub Release with DMG attached

### Triggering a Release

```bash
# Tag and push
git tag v1.0.0
git push origin v1.0.0

# GitHub Actions will automatically:
# - Build the app
# - Create DMG
# - Create GitHub Release
```

## How py2app Works

### Setup Configuration

The `setup.py` file configures py2app with:

**App Settings:**
- Entry point: `run_dictator.py`
- Bundle identifier: `com.dictator.app`
- App icon: `icon.icns` (custom Dictator icon)
- LSUIElement: `True` (menubar-only app, no dock icon)

**Permissions in Info.plist:**
- `NSMicrophoneUsageDescription` - For audio recording
- `NSAccessibilityUsageDescription` - For text insertion
- `NSAppleEventsUsageDescription` - For global hotkey monitoring

**Included Packages:**
- rumps (menubar app framework)
- pynput (hotkey listener)
- sounddevice (audio recording)
- numpy (audio processing)
- pywhispercpp (transcription)
- PyQt6 (history/settings windows)
- boto3 (AWS Bedrock LLM)
- All PyObjC frameworks

### Build Modes

**Standalone Mode (default):**
```bash
python setup.py py2app
```
- Bundles Python runtime and all dependencies
- ~200-300MB app size
- Can run on any Mac (same architecture)
- Independent of source code location

**Alias Mode (development):**
```bash
python setup.py py2app -A
```
- Creates symlinks to source code and venv
- ~10MB app size
- Fast rebuilds during development
- Requires source code to stay in place
- Used for testing changes quickly

## Bundle Structure

```
Dictator.app/
├── Contents/
│   ├── Info.plist           # App metadata and permissions
│   ├── MacOS/
│   │   └── Dictator         # Executable launcher
│   ├── Resources/           # Python code and dependencies
│   │   ├── lib/
│   │   │   └── python3.12/  # All Python packages
│   │   ├── __boot__.py      # py2app bootstrap
│   │   └── site.pyc         # Site configuration
│   └── Frameworks/          # Python framework (standalone mode)
│       └── Python.framework/
```

## Distribution

### Installing Locally

```bash
# Copy to Applications
cp -R dist/Dictator.app /Applications/

# Launch
open /Applications/Dictator.app
```

### Creating DMG (Manual)

```bash
# Create temporary directory
mkdir -p dmg_tmp
cp -R dist/Dictator.app dmg_tmp/
ln -s /Applications dmg_tmp/Applications

# Create DMG
hdiutil create -volname "Dictator" \
  -srcfolder dmg_tmp \
  -ov -format UDZO \
  dist/Dictator.dmg

# Clean up
rm -rf dmg_tmp
```

## Adding to Login Items

Once installed, users can:

1. Open **System Settings** → **General** → **Login Items**
2. Click **+** button
3. Select **Dictator.app** from Applications
4. App will now launch automatically on login

## Troubleshooting

### Build Fails

```bash
# Clean and rebuild
rm -rf build dist
./build_app.sh
```

### App Won't Launch

Check Console.app for errors:
```bash
log stream --predicate 'process == "Dictator"' --level debug
```

### Missing Dependencies

Make sure all dependencies are in `requirements.txt` and `setup.py`:
```bash
# Reinstall all dependencies
./venv/bin/pip install -r requirements.txt
```

### Notifications Don't Work

The Info.plist must include `CFBundleIdentifier`. This is automatically set by py2app to `com.dictator.app`.

### Permissions Not Requested

The app must include proper usage descriptions in Info.plist:
- Check `dist/Dictator.app/Contents/Info.plist`
- Verify `NSMicrophoneUsageDescription`, `NSAccessibilityUsageDescription`, etc. are present

## Customizing the App Icon

The app uses `icon.icns` as the application icon. To replace it:

### From iconset (Recommended)

If you have an iconset directory with all sizes:

```bash
# iconset should contain:
# icon_16x16.png, icon_16x16@2x.png
# icon_32x32.png, icon_32x32@2x.png
# icon_128x128.png, icon_128x128@2x.png
# icon_256x256.png, icon_256x256@2x.png
# icon_512x512.png, icon_512x512@2x.png

iconutil -c icns path/to/MyIcon.iconset -o icon.icns
```

### From single image

Use an online converter or Image2Icon app to create .icns from a single high-res image (1024x1024 PNG).

After replacing `icon.icns`, rebuild the app:

```bash
./build_app.sh
```

## Code Signing & Notarization (Future)

For public distribution outside GitHub, we'll need:

1. **Apple Developer Account** ($99/year)
2. **Code Signing Certificate**
3. **Notarization** (for Gatekeeper)

This will allow users to download and run without security warnings.

## Size Optimization

Current bundle size: ~200-300MB (standalone mode)

This includes:
- Python runtime (~50MB)
- PyQt6 (~100MB)
- All other dependencies (~50-100MB)

To reduce size:
- Exclude unused PyQt6 modules
- Use `strip: True` in setup.py (removes debug symbols)
- Compress with UPX (not recommended for macOS)

For now, we prioritize simplicity and compatibility over size.
