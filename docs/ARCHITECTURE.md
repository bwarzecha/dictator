# Dictator Architecture

**Version**: 1.0 (MVP)
**Last Updated**: 2025-10-23
**Status**: In Development

## Overview

Dictator is a macOS voice dictation app built with Python. It uses a simple, direct-call architecture with clear separation of concerns. Components communicate through method calls orchestrated by the main app controller.

## Design Principles

1. **Simple First**: Direct calls, no event bus (until we need it)
2. **Clear Boundaries**: Each module has one responsibility
3. **No Over-Engineering**: No abstractions until we have 2+ implementations
4. **Testable**: Components can be tested in isolation
5. **Maintainable**: Max 400 lines per file, 20 lines per function

See [DECISIONS.md](./DECISIONS.md) for detailed rationale.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Interaction                      │
│                   (Global Hotkey)                        │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   DictatorApp (app.py)                   │
│                   Main Controller                        │
│                                                           │
│  - rumps menubar UI                                      │
│  - Orchestrates all components                           │
│  - Error handling                                        │
│  - Threading coordination                                │
└──┬────────┬────────┬────────┬────────┬─────────────────┘
   │        │        │        │        │
   ▼        ▼        ▼        ▼        ▼
┌──────┐ ┌─────┐ ┌─────┐ ┌───────┐ ┌─────────┐
│Hotkey│ │Audio│ │Trans│ │Insert │ │Storage  │
│      │ │     │ │cript│ │       │ │         │
└──────┘ └─────┘ └─────┘ └───────┘ └─────────┘
```

### Data Flow

**Recording and Transcription:**
```
User presses Option+Space
  ↓
HotkeyListener calls app.toggle_recording()
  ↓
AudioRecorder.start_recording()
  ↓
User presses Option+Space again
  ↓
AudioRecorder.stop_recording() → returns (audio_path, duration)
  ↓
Background thread starts
  ↓
WhisperTranscriber.transcribe(audio_path) → returns text
  ↓
RecordingStorage.save(audio_path, text, duration) → returns Recording
  ↓
TextInserter.insert_text(text) → returns success boolean
  ↓
If success: Show success notification
If failure: Copy text to clipboard + show notification
```

**Error Handling:**
```
All operations wrapped in try/except in app.py
  ↓
Specific exceptions caught (FileNotFoundError, etc)
  ↓
User notified via rumps.notification()
  ↓
UI restored to ready state
```

---

## Component Details

### 1. Main Application (`app.py`)

**Responsibility**: Orchestrate all components, manage menubar UI, handle errors

**Key Methods:**
- `toggle_recording()` - Handle hotkey press
- `_transcribe_and_insert(audio_path, duration)` - Background thread for transcription
- `_update_duration(timer)` - Update menubar during recording
- `_update_status(status)` - Update status menu item
- `show_history()` - Open Qt history window
- `_copy_and_notify(text)` - Copy to clipboard on insertion failure

**Dependencies**:
- All other components (owns them)
- rumps for menubar
- PyQt6 for history window
- threading for background work

**Actual Size**: ~220 lines

---

### 1.5. History Window (`ui/history.py`)

**Responsibility**: Display past recordings in a Qt table with copy functionality

**Key Classes:**
```python
class HistoryWindow(QMainWindow):
    def load_recordings() -> None  # Populate table
    def _copy_to_clipboard(text) -> None
    def _format_timestamp(dt) -> str
```

**Implementation Details:**
- Qt6 QTableWidget with 3 columns (Time, Recording, Copy Button)
- Word-wrapped multi-line text support
- Adapts to system dark/light mode
- Shows last 50 recordings (newest first)
- Lazy initialization from app.py

**Dependencies**:
- PyQt6
- dictator.storage

**Actual Size**: ~145 lines

---

### 2. Audio Recording (`audio.py`)

**Responsibility**: Record audio from microphone, save to WAV file

**Key Classes:**
```python
class AudioRecorder:
    def start_recording() -> None
    def stop_recording() -> tuple[Path, float]  # (audio_path, duration)
    def get_duration() -> float
```

**Implementation Details:**
- Uses `sounddevice` for recording
- Records mono 16kHz audio (Whisper standard)
- Buffers audio chunks during recording
- Saves as WAV file with timestamp
- No events - just returns data when stopped

**Dependencies**:
- sounddevice
- numpy
- wave (stdlib)

**Size Estimate**: ~150 lines

---

### 3. Transcription (`transcription.py`)

**Responsibility**: Convert audio files to text using Whisper

**Key Classes:**
```python
class WhisperTranscriber:
    def __init__(model_name: str, n_threads: int)
    def load_model() -> None
    def transcribe(audio_path: Path) -> str
    def is_ready() -> bool
```

**Implementation Details:**
- Uses `pywhispercpp` (whisper.cpp Python bindings)
- Model: `large-v3-turbo` (default)
- Lazy loading: Model loaded on first use or at startup in background thread
- Returns plain text (no segments)
- No initial_prompt for MVP (add later if accuracy issues)

**Performance:**
- Target: 41x faster than real-time (~0.5s for 20s audio)
- Runs in background thread (non-blocking)

**Dependencies**:
- pywhispercpp

**Size Estimate**: ~100 lines

**Future Extensions:**
- Add `initial_prompt` parameter for better punctuation
- Support mlx-whisper as alternative backend
- Extract ABC when we have 2nd implementation

---

### 4. Text Insertion (`insertion.py`)

**Responsibility**: Insert text into focused application using macOS APIs

**Key Classes:**
```python
class TextInserter:
    def insert_text(text: str) -> bool
```

**Implementation Details:**
- Uses NSAccessibility API via PyObjC
- Gets focused UI element
- Sets text value directly (no clipboard)
- Returns True on success, False on failure

**Failure Cases:**
- No focused element
- Element doesn't support text input
- Accessibility permission not granted

**Dependencies**:
- pyobjc-framework-ApplicationServices

**Size Estimate**: ~80 lines

---

### 5. Storage (`storage.py`)

**Responsibility**: Persist recordings and metadata

**Key Classes:**
```python
class RecordingStorage:
    def save(audio_path: Path, transcription: str, duration: float) -> Recording
    def load_all() -> list[Recording]
    def update(recording: Recording) -> None
```

**Implementation Details:**
- Stores metadata in `recordings/metadata.json`
- Audio files stored as `recording_YYYYMMDD_HHMMSS.wav`
- Simple JSON serialization (no SQLite for MVP)
- Loads all recordings into memory (fine for MVP)

**Data Structure:**
```json
[
  {
    "audio_path": "/path/to/recording_20251023_143022.wav",
    "timestamp": "2025-10-23T14:30:22",
    "duration": 5.3,
    "transcription": "Hello world",
    "cleaned_transcription": null
  }
]
```

**Dependencies**:
- None (stdlib only: json, pathlib)

**Size Estimate**: ~120 lines

**Future Extensions:**
- SQLite when we add search/filtering
- Add `cleaned_transcription` field for LLM post-processing

---

### 6. Global Hotkey (`hotkey.py`)

**Responsibility**: Listen for Option+Space globally

**Key Classes:**
```python
class HotkeyListener:
    def __init__(callback: Callable)
    def start() -> None
    def stop() -> None
```

**Implementation Details:**
- Uses `pynput` keyboard listener
- Tracks pressed keys in set
- Detects Option+Space combination
- Calls callback when hotkey pressed
- Runs in daemon thread

**Dependencies**:
- pynput

**Size Estimate**: ~60 lines

**Future Extensions:**
- Configurable hotkey (Settings)
- Support multiple modifiers

---

### 7. Data Models (`models.py`)

**Responsibility**: Define data structures

**Key Classes:**
```python
@dataclass
class Recording:
    audio_path: Path
    timestamp: datetime
    duration: float
    transcription: str
    cleaned_transcription: Optional[str] = None

    def to_dict() -> dict
    @classmethod
    def from_dict(data: dict) -> Recording

@dataclass
class AppConfig:
    recordings_dir: Path
    whisper_model: str = "large-v3-turbo"
    whisper_threads: int = 8
    llm_enabled: bool = False
    anthropic_api_key: Optional[str] = None

    @classmethod
    def default() -> AppConfig
    def save(path: Path) -> None
    @classmethod
    def load(path: Path) -> AppConfig
```

**Dependencies**:
- None (stdlib only: dataclasses, pathlib, datetime, json)

**Size Estimate**: ~100 lines

---

### 8. UI Windows (`ui/`)

**Deferred for MVP+**

Windows to add after core functionality works:
- `ui/history.py` - View past recordings, copy manually
- `ui/settings.py` - Configure model, hotkey, LLM

**Integration Pattern:**
```python
# In app.py
@rumps.clicked("Show History")
def show_history(self, _):
    if not hasattr(self, '_history_window'):
        self._history_window = HistoryWindow(self.storage)
    self._history_window.show()
```

Simple lazy initialization, no window manager needed yet.

---

## File Structure

```
dictator/
├── src/
│   └── dictator/
│       ├── __init__.py
│       ├── main.py              # Entry point (~20 lines)
│       ├── app.py               # Main app controller (~250 lines)
│       ├── audio.py             # Recording (~150 lines)
│       ├── transcription.py     # Whisper (~100 lines)
│       ├── insertion.py         # Text insertion (~80 lines)
│       ├── storage.py           # Persistence (~120 lines)
│       ├── hotkey.py            # Global hotkey (~60 lines)
│       ├── models.py            # Data classes (~100 lines)
│       └── ui/                  # Windows (MVP+)
│           ├── __init__.py
│           ├── history.py       # Deferred
│           └── settings.py      # Deferred
│
├── tests/
│   ├── test_audio.py
│   ├── test_transcription.py
│   ├── test_insertion.py
│   ├── test_storage.py
│   ├── test_hotkey.py
│   └── fixtures/
│       └── test_audio.wav
│
├── docs/
│   ├── ARCHITECTURE.md          # This file
│   ├── DECISIONS.md             # Decision log
│   └── DEVELOPER_GUIDE.md       # How to extend (TBD)
│
├── requirements.txt
├── pyproject.toml
└── README.md
```

**Total Core Files**: 8 Python files (~860 lines total)

---

## Threading Model

### Main Thread (rumps)
- Runs rumps event loop
- Handles UI updates (menubar icon, menu items)
- Handles hotkey callbacks
- Updates duration timer

### Background Threads
1. **Hotkey Listener Thread** (daemon)
   - Started at app init
   - Listens for keyboard events
   - Calls app.toggle_recording() on main thread

2. **Model Loading Thread** (daemon)
   - Started at app init
   - Loads Whisper model in background
   - Prevents UI freeze on first transcription

3. **Transcription Thread** (daemon)
   - Started when recording stops
   - Runs transcribe → save → insert sequence
   - Shows notification when complete
   - Catches and reports errors

**Thread Safety:**
- No shared mutable state
- All communication through method calls
- rumps handles UI updates safely

---

## Error Handling Strategy

### Principle
**Fail visibly, recover gracefully**

### Error Categories

#### 1. User-Facing Errors (Show Notification)
- **Microphone permission denied**
  - Notification: "Microphone access required"
  - Action: Show system preferences hint

- **Accessibility permission denied**
  - Notification: "Text insertion failed - Check History"
  - Fallback: User copies from History window

- **No focused text field**
  - Notification: "No text field selected"
  - Fallback: History window

- **Audio file not found**
  - Notification: "Recording file missing"
  - Action: Try recording again

#### 2. Developer Errors (Log + Notification)
- **Model loading failed**
  - Log full exception
  - Notification: "Failed to load Whisper model"

- **Transcription failed**
  - Log full exception
  - Notification: "Transcription failed"

#### 3. Silent Errors (Log Only)
- Settings file missing → Use defaults
- Malformed metadata.json → Start fresh

### Error Handling Pattern

```python
def _transcribe_and_insert(self, audio_path: Path, duration: float):
    """Background thread with comprehensive error handling."""
    try:
        # Transcribe
        text = self.transcriber.transcribe(audio_path)

        # Save
        recording = self.storage.save(audio_path, text, duration)

        # Insert
        success = self.inserter.insert_text(text)

        # Notify result
        if success:
            rumps.notification("Text Inserted", "", text[:100])
        else:
            rumps.notification("Failed to insert", "", "Check History window")

    except FileNotFoundError:
        rumps.notification("Recording file not found", "", "Please try again")

    except Exception as e:
        # Catch-all for unexpected errors
        print(f"Transcription error: {e}")
        rumps.notification("Transcription failed", "", str(e))

    finally:
        # Always restore UI state
        self._update_status("Ready")
```

**Key Points:**
- One try/except per major operation
- Specific exceptions first (FileNotFoundError)
- Generic catch-all last (Exception)
- Always restore UI in finally block
- User always gets feedback

---

## Configuration

### Config File Location
`~/.dictator/config.json`

### Default Config
```json
{
  "recordings_dir": "~/.dictator/recordings",
  "whisper_model": "large-v3-turbo",
  "whisper_threads": 8,
  "llm_enabled": false,
  "anthropic_api_key": null
}
```

### Loading Strategy
1. Check if config file exists
2. If not, create with defaults
3. Load into `AppConfig` dataclass
4. Validate values (model exists, threads >0)
5. Use throughout app

---

## Testing Strategy

### Unit Tests
Test each component in isolation:

```python
# test_audio.py
def test_start_recording():
    recorder = AudioRecorder(16000, Path("/tmp"))
    recorder.start_recording()
    assert recorder.is_recording == True

# test_transcription.py
def test_transcribe(test_audio_fixture):
    transcriber = WhisperTranscriber()
    transcriber.load_model()
    text = transcriber.transcribe(test_audio_fixture)
    assert len(text) > 0

# test_storage.py
def test_save_recording():
    storage = RecordingStorage(Path("/tmp"))
    recording = storage.save(Path("test.wav"), "Hello", 1.5)
    assert recording.transcription == "Hello"
```

### Integration Tests
Test full flow (slower, fewer tests):

```python
def test_end_to_end_flow():
    """Record → Transcribe → Save → Insert"""
    # Use real components but mock TextInserter
    # Verify full chain works
```

### Manual Testing Checklist
- [ ] Press hotkey → menubar changes to 🔴
- [ ] Record 5s audio → duration shows in menubar
- [ ] Press hotkey again → transcription starts
- [ ] Text appears in focused app
- [ ] Notification shows success
- [ ] Recording saved to storage
- [ ] Error handling: No focused field → notification shown

---

## Performance Targets

### Audio Recording
- **Latency**: <100ms from hotkey to recording start
- **Overhead**: <5MB memory for 1 minute recording

### Transcription
- **Speed**: 41x real-time (0.5s for 20s audio)
- **Quality**: 88%+ word accuracy
- **Model Load**: <5s in background

### Text Insertion
- **Latency**: <50ms after transcription complete
- **Success Rate**: 95%+ (falls back to History window)

### Total User Experience
- **Record 20s audio**: 20s
- **Transcribe**: 0.5s
- **Insert**: 0.05s
- **Total**: ~20.5s → Text appears in app

**User perception**: Near-instant after stopping recording

---

## Security & Privacy

### Data Privacy
- ✅ **All processing local** - No cloud APIs
- ✅ **No network calls** - All models run offline
- ✅ **User controls data** - Recordings stored locally
- ✅ **Transparent** - Open source, auditable

### Future LLM Integration
- ⚠️ **Optional feature** - Disabled by default
- ⚠️ **API key required** - User provides own key
- ⚠️ **User consent** - Clear disclosure before enabling
- ⚠️ **No storage of cleaned text** - Unless user wants

### Permissions Required
- **Microphone** - Record audio
- **Accessibility** - Insert text system-wide
- **Input Monitoring** - Detect global hotkey

All standard for dictation apps, no unusual permissions.

---

## Future Extensions

### Near Term (MVP+)
1. **History Window** - View/copy past recordings
2. **Settings Window** - Configure model, hotkey
3. **Better error messages** - Actionable guidance

### Medium Term (v1.0)
1. **LLM cleanup** - Optional grammar/formatting fixes
2. **Custom vocabulary** - Improve accuracy for technical terms
3. **Multiple models** - tiny/base/small/medium options
4. **Keyboard shortcut customization**

### Long Term (v2.0+)
1. **Multi-language support**
2. **Voice commands** - "new paragraph", "correct that"
3. **Cloud sync** - Optional backup
4. **iOS companion app**

See [DECISIONS.md](./DECISIONS.md) for deferred decisions.

---

## Development Workflow

### Adding a New Feature

1. **Update docs first**
   - Add to ARCHITECTURE.md (if structural)
   - Add decision to DECISIONS.md (if architectural)

2. **Write test**
   - Create failing test for new feature
   - Define expected behavior

3. **Implement**
   - Follow file size limits (400 lines max)
   - Keep functions small (20 lines, 4 params)
   - Add type hints

4. **Test**
   - Unit tests pass
   - Integration test if needed
   - Manual testing

5. **Document**
   - Update docstrings
   - Update README if user-facing

### File Size Management

**When file approaches 350 lines:**
1. Look for extractable components
2. Consider splitting by responsibility
3. Create new module if reusable elsewhere
4. Update ARCHITECTURE.md with new structure

**Example:** If `app.py` reaches 350 lines:
- Extract UI methods → `app_ui.py`
- Extract threading helpers → `app_threading.py`
- Keep orchestration logic in `app.py`

---

## References

- [POC Results](../ui-and-mic-test/SUCCESS.md)
- [Whisper Research](../whisper-integration/ACCURACY_RESEARCH.md)
- [SuperWhisper Analysis](../whisper-integration/SUPERWHISPER_LLM_PROMPTS.md)
- [Decision Log](./DECISIONS.md)

---

## Version History

- **v1.0** (2025-10-23): Initial architecture for MVP
  - Direct calls, no event bus
  - Simple component structure
  - Whisper.cpp transcription
  - No LLM integration
  - No History/Settings windows
