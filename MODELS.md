# Whisper Model Selection Guide

## Quick Reference

| Model | Size | Speed | Best For |
|-------|------|-------|----------|
| tiny.en / tiny | 75 MB | ⚡⚡⚡⚡⚡ | Ultra-fast, lowest accuracy |
| base.en / base | 142 MB | ⚡⚡⚡⚡ | Fast, basic accuracy |
| **small.en / small** | **466 MB** | **⚡⚡⚡** | **Balanced - recommended for slower machines** |
| medium.en / medium | 1.5 GB | ⚡⚡ | Accurate, moderate speed |
| **large-v3-turbo** | **1.5 GB** | **⚡⚡** | **Best balance - default** |
| large-v3 | 2.9 GB | ⚡ | Most accurate, slowest |

## How to Change Models

1. Open **Settings** (menu bar → Dictator → Settings)
2. In **Whisper Transcription** section, select model from dropdown
3. If model not downloaded, click **Download** button
4. Click **Save**

Models are cached locally after first download.

## Recommendations

### For Slow Machines
Switch to **small** (466MB) or **small.en** (English-only):
- 2x faster than default
- Still good accuracy
- Much less memory usage

### For Normal Machines
Keep default **large-v3-turbo** (1.5GB):
- Best balance of speed and accuracy
- Good for most use cases

### For Best Quality
Use **large-v3** (2.9GB):
- Highest accuracy
- Slower transcription
- Requires more RAM

## English-Only Models (.en)

Models with `.en` suffix are optimized for English only:
- **Available**: tiny.en, base.en, small.en, medium.en
- **Not available**: large-v3-turbo.en, large-v3.en (multilingual only)
- **Benefits**: Slightly better English accuracy, ~5-10% faster
- **Use if**: You ONLY dictate in English

## Download Behavior

- **First time**: Model downloads automatically (may take a few minutes)
- **Storage**: Models cached in `~/.cache/whisper/`
- **Re-download**: Not needed, models persist
- **Progress**: Dialog shows "Downloading..." status
- **Background**: Click "Run in Background" to continue working

## Speed Reference

Speed ratings show how much faster than realtime:
- **10x realtime** = 1 minute audio → ~6 seconds to transcribe
- **4x realtime** = 1 minute audio → ~15 seconds
- **2x realtime** = 1 minute audio → ~30 seconds
- **1x realtime** = 1 minute audio → ~60 seconds

## Logging

Check which model is being used:
```bash
tail -f ~/Library/Logs/Dictator/dictator.log | grep "🎙️"
```

You'll see:
```
🎙️  Using Whisper model: small (4 threads)
```

## Tips

- **Thread count**: Adjust in Settings (default: 8 threads)
- **Custom vocabulary**: Add technical terms, names in Settings for better accuracy
- **Disk space**: Check you have enough before downloading large models
- **Switch anytime**: Can change models without losing data

## Troubleshooting

**Transcription too slow?**
→ Switch to smaller model (small or base)

**Transcription inaccurate?**
→ Switch to larger model (large-v3-turbo or large-v3)
→ Add custom vocabulary in Settings

**Download stuck?**
→ Click "Run in Background", download continues
→ Check `~/.cache/whisper/` for partial files
→ Restart app if needed
