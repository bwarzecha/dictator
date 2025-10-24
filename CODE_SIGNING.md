# Code Signing and Notarization Guide

This guide explains how to sign Dictator.app for public distribution without security warnings.

## Prerequisites

### 1. Apple Developer Account
- Cost: $99/year
- Sign up: https://developer.apple.com/programs/
- Verify your identity (can take 1-2 days)

### 2. Install Xcode Command Line Tools
```bash
xcode-select --install
```

## Step 1: Create Developer ID Certificate

### Option A: Using Xcode (Recommended)
1. Open **Xcode** → **Settings** → **Accounts**
2. Add your Apple ID
3. Select your team → **Manage Certificates**
4. Click **+** → **Developer ID Application**
5. Certificate will be installed in Keychain

### Option B: Using Apple Developer Portal
1. Go to https://developer.apple.com/account/resources/certificates
2. Click **+** to create new certificate
3. Select **Developer ID Application**
4. Follow instructions to create CSR (Certificate Signing Request)
5. Download and install certificate

### Verify Certificate
```bash
# List available signing identities
security find-identity -v -p codesigning

# You should see something like:
# 1) ABC123... "Developer ID Application: Your Name (TEAM_ID)"
```

## Step 2: Update setup.py for Code Signing

Create a new file `setup_signed.py` or modify `setup.py`:

```python
"""
py2app setup script with code signing for Dictator.
"""

from setuptools import setup
import os

# Get signing identity from environment variable or use default
SIGNING_IDENTITY = os.environ.get(
    'CODESIGN_IDENTITY',
    'Developer ID Application: Your Name (TEAM_ID)'
)

APP = ['run_dictator.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icon.icns',
    'plist': {
        'CFBundleName': 'Dictator',
        'CFBundleDisplayName': 'Dictator',
        'CFBundleIdentifier': 'com.dictator.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSUIElement': True,
        'NSMicrophoneUsageDescription': 'Dictator needs microphone access to record your voice for transcription.',
        'NSAccessibilityUsageDescription': 'Dictator needs accessibility access to insert transcribed text into any application.',
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
        'boto3',
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
        'matplotlib',
        'PIL',
        'tkinter',
    ],
    'site_packages': True,
    'strip': False,
    'semi_standalone': False,
    # Code signing options
    'codesign_identity': SIGNING_IDENTITY,
    'codesign_options': 'runtime',  # Hardened runtime for notarization
    'codesign_deep': True,  # Deep sign all frameworks and dylibs
}

setup(
    name='Dictator',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
```

## Step 3: Build with Code Signing

### Local Build
```bash
# Set your signing identity
export CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAM_ID)"

# Build
python setup.py py2app

# The app will be automatically signed during build
```

### Verify Signing
```bash
# Check if app is signed
codesign -dv --verbose=4 dist/Dictator.app

# Verify signature
codesign --verify --deep --strict --verbose=2 dist/Dictator.app

# Should output: "dist/Dictator.app: valid on disk"
```

## Step 4: Notarize the App

Notarization submits your app to Apple for automated security scanning. Required for distribution.

### 4.1: Create App-Specific Password
1. Go to https://appleid.apple.com/account/manage
2. Sign in with your Apple ID
3. Under **Security** → **App-Specific Passwords** → **Generate Password**
4. Label it "Notarization" and save the password

### 4.2: Store Credentials in Keychain
```bash
# Store credentials for notarization
xcrun notarytool store-credentials "notary-profile" \
  --apple-id "your-email@example.com" \
  --team-id "YOUR_TEAM_ID" \
  --password "app-specific-password"
```

### 4.3: Create DMG
```bash
# Create DMG for distribution
hdiutil create -volname "Dictator" \
  -srcfolder dist/Dictator.app \
  -ov -format UDZO \
  dist/Dictator.dmg
```

### 4.4: Submit for Notarization
```bash
# Submit DMG to Apple
xcrun notarytool submit dist/Dictator.dmg \
  --keychain-profile "notary-profile" \
  --wait

# This will take 5-15 minutes
# You'll get a submission ID
```

### 4.5: Check Notarization Status
```bash
# Check status (if --wait didn't work)
xcrun notarytool info SUBMISSION_ID \
  --keychain-profile "notary-profile"

# Get detailed log if it fails
xcrun notarytool log SUBMISSION_ID \
  --keychain-profile "notary-profile"
```

### 4.6: Staple Notarization to DMG
```bash
# Attach notarization ticket to DMG
xcrun stapler staple dist/Dictator.dmg

# Verify stapling
xcrun stapler validate dist/Dictator.dmg
```

## Step 5: Automate with GitHub Actions

Update `.github/workflows/build.yml` to sign and notarize automatically:

```yaml
- name: Import Code Signing Certificate
  if: startsWith(github.ref, 'refs/tags/v')
  env:
    CERTIFICATE_BASE64: ${{ secrets.MACOS_CERTIFICATE }}
    CERTIFICATE_PASSWORD: ${{ secrets.MACOS_CERTIFICATE_PASSWORD }}
  run: |
    # Create keychain
    security create-keychain -p actions temp.keychain
    security default-keychain -s temp.keychain
    security unlock-keychain -p actions temp.keychain

    # Import certificate
    echo $CERTIFICATE_BASE64 | base64 --decode > certificate.p12
    security import certificate.p12 -k temp.keychain -P $CERTIFICATE_PASSWORD -T /usr/bin/codesign

    # Allow codesign to access keychain
    security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k actions temp.keychain

- name: Build and Sign .app bundle
  if: startsWith(github.ref, 'refs/tags/v')
  env:
    CODESIGN_IDENTITY: ${{ secrets.CODESIGN_IDENTITY }}
  run: |
    python setup.py py2app

- name: Notarize App
  if: startsWith(github.ref, 'refs/tags/v')
  env:
    APPLE_ID: ${{ secrets.APPLE_ID }}
    APPLE_TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
    APPLE_APP_PASSWORD: ${{ secrets.APPLE_APP_PASSWORD }}
  run: |
    # Create DMG
    hdiutil create -volname "Dictator" \
      -srcfolder dist/Dictator.app \
      -ov -format UDZO \
      dist/Dictator.dmg

    # Store credentials
    xcrun notarytool store-credentials "notary-profile" \
      --apple-id "$APPLE_ID" \
      --team-id "$APPLE_TEAM_ID" \
      --password "$APPLE_APP_PASSWORD"

    # Submit for notarization
    xcrun notarytool submit dist/Dictator.dmg \
      --keychain-profile "notary-profile" \
      --wait

    # Staple ticket
    xcrun stapler staple dist/Dictator.dmg
```

### Required GitHub Secrets
Add these to your repository secrets (Settings → Secrets and variables → Actions):

1. `MACOS_CERTIFICATE` - Base64 encoded .p12 certificate
   ```bash
   base64 -i YourCertificate.p12 | pbcopy
   ```

2. `MACOS_CERTIFICATE_PASSWORD` - Password for .p12 file

3. `CODESIGN_IDENTITY` - Your signing identity name
   ```
   Developer ID Application: Your Name (TEAM_ID)
   ```

4. `APPLE_ID` - Your Apple ID email

5. `APPLE_TEAM_ID` - Your 10-character Team ID

6. `APPLE_APP_PASSWORD` - App-specific password from Step 4.1

## Testing Distribution

### Test on Your Mac
```bash
# Should open without warnings
open dist/Dictator.dmg
```

### Test on Fresh Mac
1. Transfer DMG to another Mac (or test user account)
2. Double-click DMG
3. Drag to Applications
4. Launch - should open without "unidentified developer" warning

## Troubleshooting

### "App is damaged" Error
```bash
# Remove quarantine attribute
xattr -cr /Applications/Dictator.app
```

### Signature Verification Failed
```bash
# Check what's wrong
codesign --verify --deep --strict --verbose=4 dist/Dictator.app
```

### Notarization Failed
```bash
# Get detailed log
xcrun notarytool log SUBMISSION_ID --keychain-profile "notary-profile"

# Common issues:
# - Hardened runtime not enabled (add 'codesign_options': 'runtime')
# - Unsigned frameworks (enable 'codesign_deep': True)
# - Missing entitlements (usually not needed for py2app)
```

## Cost Summary

- **Apple Developer Account**: $99/year (required)
- **Code Signing**: Free (included with account)
- **Notarization**: Free (included with account)
- **GitHub Actions**: Free for public repos

## Alternative: Self-Distribution Without Signing

If you don't want to pay $99/year, users can still run the app by:

1. Right-click → Open (instead of double-click)
2. Click "Open" in security dialog
3. Or disable Gatekeeper: `sudo spctl --master-disable` (not recommended)

However, this creates friction and security warnings.

## Resources

- [Apple Code Signing Guide](https://developer.apple.com/support/code-signing/)
- [Notarization Documentation](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [py2app Code Signing](https://py2app.readthedocs.io/en/latest/codesigning.html)
