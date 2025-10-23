# Dictator Setup Guide

## Quick Start (2 steps!)

**Step 1: Install**
```bash
./setup.sh
```

**Step 2: Grant Permission**
- Open **System Settings** → **Privacy & Security** → **Accessibility**
- Click the **+** button
- Press **Cmd+Shift+G** and paste the path (already copied to clipboard)
- Click **Go**, then **Open**

**Step 3: Run**
```bash
./start.sh
```

That's it! Press **Option+Space** from anywhere to dictate.

## What You'll See

- **⚪** - Ready and waiting
- **🔴** - Recording your voice (shows duration in menubar)
- **🟡** - Transcribing audio (takes ~0.3-0.5 seconds)
- **⚪** - Back to ready

## Menubar Menu

Click the ⚪ icon to see:
- **Status: Ready** - Current app state
- **Quit Dictator** - Stop the app

## How It Works

1. **Global hotkey**: Option+Space works from any application
2. **Audio recording**: Records mono 16kHz audio (perfect for Whisper)
3. **Transcription**: Uses Whisper large-v3-turbo model with Metal GPU acceleration
4. **Text insertion**: Uses macOS Accessibility API to insert at cursor
5. **Storage**: All recordings saved to `~/.dictator/recordings/` with metadata

## First Run

The first time you run Dictator, it will download the Whisper model (~1.6GB). This takes a few minutes. Subsequent starts are instant.

The app will automatically:
- Download the Whisper model to `~/Library/Application Support/pywhispercpp/models/`
- Create config at `~/.dictator/config.json`
- Create recordings directory at `~/.dictator/recordings/`

## Performance

On Apple Silicon (M4 Max):
- Model loading: ~0.5 seconds
- Transcription: 0.3-0.5 seconds for 3-5 second recordings (40-50x real-time!)
- Memory usage: ~500MB during transcription, ~200MB idle

## Troubleshooting

### Hotkey not working
- Check the pynput warning in logs
- Grant accessibility permissions to Python (see step 2 above)
- Restart the app after granting permissions

### Text not inserting
- Make sure you granted accessibility permissions
- Make sure a text field is focused and cursor is blinking
- Some apps (like Terminal) may not support text insertion via Accessibility API

### App shows in Dock
- This is normal when running from command line
- To hide from Dock completely, package as .app bundle (future work)

### Transcription is slow
- First run downloads the model (one-time)
- Check that Metal is being used (you'll see "using Metal backend" in logs)
- On Intel Macs, transcription will be CPU-only and slower

## File Locations

- **Config**: `~/.dictator/config.json`
- **Recordings**: `~/.dictator/recordings/`
- **Metadata**: `~/.dictator/recordings/metadata.json`
- **Whisper model**: `~/Library/Application Support/pywhispercpp/models/`

## Stopping the App

- Click the menubar icon → **Quit Dictator**
- Or press Ctrl+C in the terminal

## What's Next?

See [docs/PROGRESS.md](docs/PROGRESS.md) for the roadmap and future features like:
- History window to view past recordings
- LLM cleanup for better transcription
- Settings window
- Custom keyboard shortcuts
- Packaging as standalone .app

Enjoy! 🎙️
