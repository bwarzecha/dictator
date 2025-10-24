# Quick Setup: Code Signing for Dictator

This is a step-by-step guide to get code signing working after signing up for Apple Developer.

## Step 1: Verify Account Activation

1. Go to: https://developer.apple.com/account
2. Sign in with your Apple ID
3. Check if you see "Membership" status as **Active**

**If not active yet:**
- Wait for activation email (can take 2-48 hours)
- Check spam folder
- Apple may ask for additional verification

**Once active, continue to Step 2.**

---

## Step 2: Create Developer ID Certificate

### Option A: Using Xcode (Easiest)

1. **Open Xcode** (install from App Store if needed)
   ```bash
   xcode-select --install  # If you don't have Xcode
   ```

2. **Open Xcode Settings:**
   - Xcode menu → **Settings** (or press `Cmd + ,`)
   - Click **Accounts** tab

3. **Add your Apple ID:**
   - Click **+** button at bottom left
   - Select **Apple ID**
   - Sign in with your developer account

4. **Create Certificate:**
   - Select your Apple ID
   - Click **Manage Certificates...**
   - Click **+** button at bottom left
   - Select **Developer ID Application**
   - Click **Done**

5. **Verify it was created:**
   ```bash
   security find-identity -v -p codesigning
   ```

   You should see:
   ```
   1) ABC123... "Developer ID Application: Your Name (TEAM_ID)"
   ```

### Option B: Using Apple Developer Portal

1. Go to: https://developer.apple.com/account/resources/certificates
2. Click **+** (Create Certificate)
3. Select **Developer ID Application**
4. Click **Continue**
5. Follow instructions to create Certificate Signing Request (CSR)
6. Download and install the certificate

---

## Step 3: Export Certificate for GitHub Actions

1. **Open Keychain Access** (Applications → Utilities → Keychain Access)

2. **Find your certificate:**
   - Select **login** keychain on left
   - Select **My Certificates** category
   - Find **Developer ID Application: Your Name**

3. **Export as .p12:**
   - Right-click the certificate → **Export "Developer ID Application..."**
   - Save as: `DictatorCertificate.p12`
   - **Set a password** (you'll need this later)
   - Click **Save**
   - Enter your Mac password to allow export

4. **Convert to Base64:**
   ```bash
   cd ~/Downloads  # or wherever you saved it
   base64 -i DictatorCertificate.p12 | pbcopy
   ```

   The base64 string is now in your clipboard!

---

## Step 4: Get Your Team ID and Identity Name

1. **Get Team ID:**
   ```bash
   # List your certificates
   security find-identity -v -p codesigning

   # Copy the TEAM_ID from the output (10 characters in parentheses)
   # Example: "Developer ID Application: John Doe (AB12CD34EF)"
   #                                               ^^^^^^^^^^
   #                                               This is your TEAM_ID
   ```

2. **Get Full Identity Name:**
   ```bash
   # Copy the full quoted string
   # Example: "Developer ID Application: John Doe (AB12CD34EF)"
   ```

---

## Step 5: Add Secrets to GitHub

1. **Go to your repository:**
   https://github.com/bwarzecha/dictator/settings/secrets/actions

2. **Click "New repository secret"** and add these secrets:

   **Secret 1: MACOS_CERTIFICATE**
   - Name: `MACOS_CERTIFICATE`
   - Value: Paste the base64 string from Step 3 (should still be in clipboard)

   **Secret 2: MACOS_CERTIFICATE_PASSWORD**
   - Name: `MACOS_CERTIFICATE_PASSWORD`
   - Value: The password you set when exporting the .p12

   **Secret 3: KEYCHAIN_PASSWORD**
   - Name: `KEYCHAIN_PASSWORD`
   - Value: Any random password (e.g., `temporary-build-keychain-pass`)

   **Secret 4: CODESIGN_IDENTITY**
   - Name: `CODESIGN_IDENTITY`
   - Value: The full identity string from Step 4
   - Example: `Developer ID Application: John Doe (AB12CD34EF)`

---

## Step 6: Enable Code Signing in GitHub

1. **Go to repository variables:**
   https://github.com/bwarzecha/dictator/settings/variables/actions

2. **Click "New repository variable":**
   - Name: `ENABLE_CODE_SIGNING`
   - Value: `true`

---

## Step 7: Test the Setup

1. **Create a test tag:**
   ```bash
   cd /Users/bartosz/dev/dictator
   git tag v1.0.1
   git push origin v1.0.1
   ```

2. **Monitor the build:**
   - Go to: https://github.com/bwarzecha/dictator/actions
   - Watch the workflow run
   - Look for: "🔐 Building with code signing: Developer ID Application..."

3. **Verify the build:**
   - Download the DMG from the release
   - Open it on your Mac
   - Check signature:
   ```bash
   codesign -dv /Volumes/Dictator/Dictator.app
   ```

   Should show your Developer ID!

---

## Troubleshooting

### "Certificate not found in keychain"
```bash
# List all keychains
security list-keychains

# Make sure login keychain is in the list
security list-keychains -s ~/Library/Keychains/login.keychain-db
```

### "The identity could not be found"
- Make sure you copied the EXACT identity string including quotes
- Try without quotes if it doesn't work
- Verify with: `security find-identity -v -p codesigning`

### GitHub Actions fails at "Import Certificate"
- Check that MACOS_CERTIFICATE is valid base64
- Verify MACOS_CERTIFICATE_PASSWORD matches your .p12 password
- Check GitHub Actions logs for specific error

### "Your binary is not signed at all"
- ENABLE_CODE_SIGNING variable must be set to exactly `true`
- Check that workflow saw the variable (look for "🔐 Building with code signing" in logs)

---

## Testing Locally

Before pushing to GitHub, test locally:

```bash
cd /Users/bartosz/dev/dictator

# Build with signing
export CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAM_ID)"
./build_app.sh

# Verify signature
codesign -dv --verbose=4 dist/Dictator.app

# Check if notarization-ready (hardened runtime)
codesign -dv dist/Dictator.app 2>&1 | grep runtime
# Should show: "flags=0x10000(runtime)"
```

---

## Next Step: Notarization (Optional)

Once code signing works, you can add notarization to remove all security warnings.
See [CODE_SIGNING.md](CODE_SIGNING.md) Section "Step 4: Notarize the App" for details.

---

## Quick Reference

**Check what you have:**
```bash
# List certificates
security find-identity -v -p codesigning

# Check app signature
codesign -dv dist/Dictator.app

# Verify signature
codesign --verify --deep --strict dist/Dictator.app
```

**Required GitHub Secrets:**
- ✅ MACOS_CERTIFICATE (base64 of .p12)
- ✅ MACOS_CERTIFICATE_PASSWORD
- ✅ KEYCHAIN_PASSWORD
- ✅ CODESIGN_IDENTITY

**Required GitHub Variable:**
- ✅ ENABLE_CODE_SIGNING = `true`
