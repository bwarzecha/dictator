# Dictator - Open Source Voice Dictation for macOS

## What This Is

Dictator is a privacy-focused, system-wide voice dictation app for macOS. Press a hotkey from anywhere, speak, and your words appear at your cursor—no cloud services, no subscription, completely local processing.

**Key Features:**
- **100% Local Processing** - All transcription runs on your Mac using Whisper AI. No data leaves your computer.
- **System-Wide** - Works in any application with any text field
- **Fast & Accurate** - Blazing fast transcription (~0.3-0.5 seconds) with GPU acceleration on Apple Silicon
- **Privacy First** - No telemetry, no cloud APIs, no data collection
- **Open Source** - Fully transparent and auditable codebase

## How It Works

### User Experience

1. Press **Option+Space** from anywhere (any app, any text field)
2. Menubar icon changes: ⚪ → 🔴 (recording starts)
3. Speak your text
4. Press **Option+Space** again (recording stops)
5. Menubar icon changes: 🔴 → ⚪
6. Transcribed text automatically appears at your cursor
7. Notification confirms completion

### Technical Architecture

```
┌─────────────────────────────────────┐
│  rumps Menubar App                  │
│  ├─ NSStatusBar (icon in menubar)  │
│  ├─ Menu items (status, history)   │
│  └─ Notifications                   │
└─────────────┬───────────────────────┘
              │
              ├─→ pynput (global hotkey listener)
              ├─→ sounddevice (audio recording)
              ├─→ Whisper (local transcription)
              └─→ NSAccessibility (text insertion)
```

## Current Status: ✅ MVP COMPLETE & WORKING!

The app is fully functional! Press Option+Space from anywhere to dictate text.

## Core Features

### Implemented ✅
- [x] Global hotkey (Option+Space) works from any app
- [x] Audio recording from microphone (16kHz mono WAV)
- [x] Local Whisper transcription (large-v3-turbo with Metal GPU acceleration)
- [x] Menubar presence with status indicators (⚪ ready, 🔴 recording, 🟡 transcribing)
- [x] System-wide text insertion via NSAccessibility API
- [x] Recording history with metadata storage
- [x] No focus stealing (never interrupts your workflow)
- [x] Blazing fast: ~0.3-0.5 second transcription on Apple Silicon!


### Completed Features ✅
- [x] History window to view/copy past recordings
- [x] Settings window for configuration
- [x] LLM cleanup for improved transcription quality (AWS Bedrock)
- [x] Packaging as standalone .app bundle
- [x] Custom vocabulary support

### Planned 🔮
- [ ] Custom keyboard shortcuts
- [ ] Multiple language support
- [ ] App Store distribution


## Key Technical Challenges Solved

### 1. Global Hotkey Without Focus
**Challenge**: Hotkey must work even when app isn't focused
**Solution**: `pynput` keyboard listener runs in background thread

### 2. System-Wide Text Insertion
**Challenge**: Paste transcribed text into any application's focused text field
**Solution**: NSAccessibility API (`AXUIElementSetAttributeValue`) inserts directly without using clipboard

### 3. UI Without Focus Stealing
**Challenge**: Show recording status without taking focus from user's current text field
**Solution**: rumps menubar app (no window = no focus stealing)

This was the hardest problem. We tried:
- ❌ PyQt windows (all steal focus regardless of flags)
- ❌ NSPanel mixed with PyQt (event loop conflicts)
- ✅ **rumps menubar app** (perfect solution)

### 4. History Fallback
**Challenge**: NSAccessibility doesn't work in all apps
**Solution**: Optional history window with manual copy buttons

## Project Structure

```
dictator/
├── src/dictator/               # Main application code
│   ├── models.py              # Data models (Recording, AppConfig)
│   ├── storage.py             # Recording persistence
│   ├── hotkey.py              # Global hotkey listener
│   ├── audio.py               # Audio recording
│   ├── transcription.py       # Whisper transcription
│   ├── insertion.py           # Text insertion via Accessibility API
│   ├── app.py                 # Main application controller
│   └── main.py                # Entry point
├── docs/                       # Architecture & decisions
├── tests/                      # Unit tests
├── run_dictator.py            # Launcher script (hides from Dock)
├── start.sh                   # Convenient startup script
├── SETUP.md                   # Detailed setup instructions
└── requirements.txt           # Python dependencies
```

## Quick Start

### Option 1: Download Pre-built App (Recommended)

1. Download `Dictator.dmg` from [Releases](https://github.com/yourusername/dictator/releases)
2. Open the DMG and drag Dictator.app to Applications
3. Launch Dictator from Applications
4. Grant permissions when prompted (Accessibility, Microphone, Input Monitoring)
5. Look for the ⚪ icon in your menubar
6. Press **Option+Space** to start dictating!

### Option 2: Build from Source

```bash
# 1. Install dependencies
./setup.sh

# 2. Build the .app bundle
./build_app.sh

# 3. Install to Applications
cp -R dist/Dictator.app /Applications/

# 4. Launch
open /Applications/Dictator.app
```

### Option 3: Run from Terminal (Development)

```bash
# 1. Install
./setup.sh

# 2. Run
./start.sh
```

See [SETUP.md](SETUP.md) for detailed instructions.

## Usage

1. Look for the ⚪ icon in your menubar
2. Open any text editor and click in a text field
3. Press **Option+Space** to start recording (icon → 🔴)
4. Speak your text
5. Press **Option+Space** again to stop (icon → 🟡 while transcribing)
6. Text appears at your cursor!

## Dependencies

- **rumps** - Menubar app framework
- **pynput** - Global hotkey listener
- **sounddevice** - Audio recording
- **numpy** - Audio data handling
- **PyQt6** - Optional history window
- **pyobjc-framework-ApplicationServices** - NSAccessibility API
- **whisper** (planned) - Speech-to-text transcription

## macOS Permissions Required

The app needs these permissions (macOS will prompt):
- **Accessibility** - For system-wide text insertion
- **Microphone** - For audio recording
- **Input Monitoring** - For global hotkey detection

## Feature Status

| Feature | Status |
|---------|--------|
| Global hotkey | ✅ Implemented |
| System-wide text insertion | ✅ Implemented |
| Menubar presence | ✅ Implemented |
| No focus stealing | ✅ Implemented |
| Local Whisper transcription | ✅ Implemented |
| GPU acceleration (Apple Silicon) | ✅ Implemented |
| History window | 🚧 In progress |
| LLM cleanup/enhancement | 📋 Planned |

## Development Philosophy

This project follows simple, test-driven principles:

1. **Validate risky components first** (POC approach)
2. **One feature at a time** with tests
3. **No over-engineering** - simple solutions only
4. **Clear over clever** - readability wins
5. **Build POCs when uncertain** about approach

## Current Status

**POC Phase: ✅ COMPLETE**

All three risky technical components have been validated:
1. ✅ Global hotkey works
2. ✅ Audio recording works
3. ✅ Text insertion without focus stealing works

**Next Phase: Integration**

Now ready to:
1. Integrate actual Whisper transcription
2. Build history window UI
3. Add persistence for transcriptions
4. Polish and package for distribution

## Why Python?

- Excellent AI/ML ecosystem (Whisper, transformers)
- PyObjC for native macOS APIs
- Rapid prototyping for POC validation
- Easy to audit and understand
- Good enough performance for this use case

## License

MIT License - see [LICENSE](LICENSE) file for details.

**Note:** This project uses [pynput](https://github.com/moses-palmer/pynput) which is licensed under LGPL-3.0. See [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES) for full dependency licenses.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Acknowledgments

- Built with [Whisper](https://github.com/openai/whisper) by OpenAI for speech recognition
- Uses [rumps](https://github.com/jaredks/rumps) for menubar integration
- Uses [pywhispercpp](https://github.com/abdeladim-s/pywhispercpp) for efficient Whisper inference
