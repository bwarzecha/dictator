# Architectural Decision Log

This document records key architectural decisions made during development, including context, options considered, and rationale for choices.

## Format

Each decision follows this structure:
- **Date**: When the decision was made
- **Status**: Accepted, Superseded, or Deprecated
- **Context**: What problem we're solving
- **Options Considered**: Alternatives we evaluated
- **Decision**: What we chose and why
- **Consequences**: Trade-offs and implications
- **Migration Path**: How to change this later if needed

---

## Decision 1: Direct Calls vs Event Bus Architecture

**Date**: 2025-10-23
**Status**: Accepted

### Context

Deciding on the core communication pattern between components (audio recorder, transcriber, text inserter, storage). Need to balance:
- Simplicity and maintainability
- Extensibility for future features (History window, Settings)
- Error handling clarity
- Debuggability

### Options Considered

#### Option 1: Direct Calls (Chosen)
```python
class DictatorApp:
    def toggle_recording(self):
        if self.audio.is_recording:
            audio_path, duration = self.audio.stop_recording()
            threading.Thread(target=self._transcribe_and_insert,
                           args=(audio_path, duration)).start()
        else:
            self.audio.start_recording()

    def _transcribe_and_insert(self, audio_path, duration):
        try:
            text = self.transcriber.transcribe(audio_path)
            recording = self.storage.save(audio_path, text, duration)
            success = self.inserter.insert_text(text)
            # Handle result...
        except Exception as e:
            # Handle errors in one place
```

**Pros:**
- ✅ Simple: Clear call chain, easy to understand
- ✅ Error handling: Natural try/except, stack traces work
- ✅ Debuggable: Follow the code top-to-bottom
- ✅ Less code: ~85 lines vs ~180 for event bus
- ✅ Returns values: Can check success/failure immediately

**Cons:**
- ❌ Coupled: app.py knows about all components
- ❌ Extension requires modification: Adding History window means editing app.py
- ❌ Testing: Components depend on each other

#### Option 2: Event Bus
```python
class DictatorApp:
    def __init__(self):
        event_bus.subscribe(RECORDING_STOPPED, self._on_recording_stopped)
        event_bus.subscribe(TRANSCRIPTION_COMPLETED, self._on_transcription_completed)
        event_bus.subscribe(TRANSCRIPTION_FAILED, self._on_transcription_failed)
        event_bus.subscribe(TEXT_INSERTED, self._on_text_inserted)
        event_bus.subscribe(TEXT_INSERTION_FAILED, self._on_text_insertion_failed)

    def toggle_recording(self):
        if self.audio.is_recording:
            self.audio.stop_recording()  # Publishes RECORDING_STOPPED
        else:
            self.audio.start_recording()  # Publishes RECORDING_STARTED
```

**Pros:**
- ✅ Decoupled: Components independent
- ✅ Extensible: History window subscribes without modifying app.py
- ✅ Testable: Components tested in isolation

**Cons:**
- ❌ Complex: 2x more code (~180 lines vs ~85)
- ❌ Error handling nightmare:
  - Need separate events for success/failure (8 event types)
  - Errors spread across multiple callbacks
  - Hard to trace: "Which event failed?"
  - No return values (must use response events)
- ❌ Debugging hard: Stack traces don't show event flow
- ❌ Async complications: Background threads need error events

#### Option 3: Hybrid (Direct Core + UI Events)
Core logic uses direct calls, but UI notifications go through simple listener pattern.

**Pros:**
- ✅ Simple core logic
- ✅ UI can listen without modifying app.py

**Cons:**
- ⚠️ Two patterns (potentially confusing)
- ❌ Still coupled for core logic

### Decision

**Choose Option 1: Direct Calls**

Rationale:
1. **YAGNI (You Aren't Gonna Need It)**: We don't have multiple listeners yet. When we add History window (the first case where we'd need it), we can either:
   - Pass it as a dependency: `history_window.add_recording(recording)`
   - Add simple callback: `self.on_recording_completed(recording)`
   - Refactor to events at that point if we have 3+ listeners

2. **Error Handling Priority**: Clear error handling is more important than extensibility right now. Dictation app must be reliable - users need to know when something fails.

3. **Simplicity**: 85 lines of clear code is better than 180 lines of distributed logic.

4. **Debuggability**: Stack traces are invaluable during development and bug reports.

### Consequences

**Positive:**
- Easier to develop and debug initially
- New developers can understand flow quickly
- Natural error handling with try/except
- Less code to maintain

**Negative:**
- Adding History window will require modifying app.py
- Components are coupled through app.py orchestration
- Testing requires more mocking

**Acceptable Trade-offs:**
- We accept tight coupling in exchange for simplicity
- We'll refactor if we find ourselves with 3+ components listening to the same events
- Initial development speed > future extensibility (for now)

### Migration Path

**When to Reconsider:**

Refactor to event bus when ANY of these conditions are met:

1. **Multiple Listeners**: When 3+ components need to react to the same event
   - Example: History window, Statistics tracker, Cloud sync all listen to TRANSCRIPTION_COMPLETED

2. **app.py Size**: When app.py exceeds 400 lines due to orchestration logic

3. **Testing Pain**: When testing becomes too painful due to coupling

4. **Async Complexity**: When we have complex async workflows that would benefit from event-driven approach

**How to Migrate:**

If we need to switch to event bus later:

1. Create `events.py` with EventBus class (~50 lines)
2. Define event types enum
3. Replace direct calls with `event_bus.publish()` one method at a time
4. Add event subscribers in components
5. Keep both patterns during migration (gradual transition)
6. Estimated migration time: 4-6 hours

**Code Sketch for Future Migration:**

```python
# events.py
from enum import Enum, auto
from typing import Callable, Dict, List, Any
from dataclasses import dataclass

class EventType(Enum):
    RECORDING_STOPPED = auto()
    TRANSCRIPTION_COMPLETED = auto()
    TRANSCRIPTION_FAILED = auto()

@dataclass
class Event:
    type: EventType
    data: Dict[str, Any]

class EventBus:
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}

    def subscribe(self, event_type: EventType, callback: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def publish(self, event: Event) -> List[Exception]:
        """Publish event, return any errors from handlers."""
        errors = []
        for callback in self._subscribers.get(event.type, []):
            try:
                callback(event)
            except Exception as e:
                errors.append(e)
        return errors

event_bus = EventBus()
```

**Important Notes for Future Migration:**

- ⚠️ **Must handle errors properly**: Return errors from publish(), don't swallow them
- ⚠️ **Need both success and failure events** for async operations
- ⚠️ **Add extensive logging** to trace event flow during debugging
- ✅ Can migrate gradually - keep direct calls for some flows, events for others during transition

### Related Decisions

- See Decision 2 for module structure (when to extract components)
- See Decision 3 for plugin architecture (when to add factories/ABCs)

---

## Decision 2: No Premature Plugin Architecture

**Date**: 2025-10-23
**Status**: Accepted

### Context

Deciding whether to create abstract base classes and factory patterns for:
- Transcription engines (whisper.cpp, mlx-whisper, cloud APIs)
- LLM processors (Claude, local LLM, GPT)
- Window management system

### Options Considered

#### Option A: Plugin System with Factories (Rejected)
```python
# Abstract base class
class TranscriptionEngine(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        pass

# Factory pattern
def create_transcription_engine(engine_type: str, **kwargs) -> TranscriptionEngine:
    engines = {
        'whispercpp': WhisperCppEngine,
        'mlx-whisper': MlxWhisperEngine,
    }
    return engines[engine_type](**kwargs)
```

**Pros:**
- ✅ Easy to add new engines later
- ✅ Clean abstraction

**Cons:**
- ❌ Over-engineering: We only have ONE engine right now (whisper.cpp)
- ❌ Extra complexity: ABC, factory, registration system
- ❌ YAGNI violation: Building for future we don't have

#### Option B: Simple Class, Extend Later (Chosen)
```python
class WhisperTranscriber:
    """Transcribe using whisper.cpp."""
    def __init__(self, model_name: str = "large-v3-turbo", n_threads: int = 8):
        self.model_name = model_name
        self.n_threads = n_threads
        self._model = None

    def transcribe(self, audio_path: Path) -> str:
        if self._model is None:
            self._model = Model(self.model_name, n_threads=self.n_threads)
        segments = self._model.transcribe(str(audio_path))
        return "".join([seg.text for seg in segments]).strip()
```

**Pros:**
- ✅ Simple: Just a class, no abstractions
- ✅ Easy to understand
- ✅ Can add abstraction later when needed

**Cons:**
- ❌ Have to refactor when adding second engine

### Decision

**Choose Option B: Simple Classes**

**Rationale:**
1. We only have ONE implementation of each component
2. Rule of Three: Extract abstraction after 2 repetitions (we have 0)
3. Simple classes are easier to change than complex hierarchies
4. When we add mlx-whisper (second engine), we'll know exactly what interface we need

### Migration Path

**When to Add Plugin Architecture:**

Add abstractions when we have **2 working implementations** of any component.

**Example: Adding mlx-whisper as second transcription engine:**

1. Create both implementations first
2. Notice the common interface
3. Extract ABC based on actual usage:
```python
class TranscriptionEngine(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path) -> str:
        pass

    @abstractmethod
    def load_model(self) -> None:
        pass

class WhisperCppEngine(TranscriptionEngine):
    # Existing code

class MlxWhisperEngine(TranscriptionEngine):
    # New code
```

4. Add simple factory if needed (>3 engines)

**Don't create the abstraction until you have two concrete examples to guide the design.**

---

## Decision 3: Module Structure - Start Colocated

**Date**: 2025-10-23
**Status**: Accepted

### Context

Deciding when to extract components into separate files vs keeping them in `app.py`.

### Decision

**Start with components in separate files from the beginning:**
- `audio.py` - Audio recording
- `transcription.py` - Whisper integration
- `insertion.py` - Text insertion
- `storage.py` - Recording persistence
- `hotkey.py` - Global hotkey
- `models.py` - Data classes

**Rationale:**
1. Each component is self-contained (~100-150 lines)
2. Clear boundaries even without abstractions
3. Easy to test in isolation
4. Reusable if we need (e.g., storage in History window)

### File Size Rules

Extract to separate file when:
- Class/module >150 lines
- Reused in multiple places
- Needs isolated testing

Keep in `app.py` when:
- UI callback methods (<20 lines each)
- Orchestration logic
- rumps-specific code

**Limits:**
- Max file size: 400 lines (warn at 350)
- Max function: 20 lines, 4 parameters
- Max class: 300 lines

---

## Decision 4: Strong Typing Over Dicts

**Date**: 2025-10-23
**Status**: Accepted

### Context

Python allows using dictionaries for structured data, but this leads to:
- Runtime errors from typos (e.g., `data['usre_id']` instead of `data['user_id']`)
- No IDE autocomplete
- Unclear data structures
- Hard to refactor

### Decision

**Use dataclasses and strong types everywhere:**
- ✅ `@dataclass` for all structured data
- ✅ Type hints on all public functions
- ✅ Path objects instead of strings for file paths
- ✅ datetime objects instead of strings for timestamps
- ❌ No dictionaries for structured data (except JSON serialization)

### Examples

```python
# YES: Strong types
@dataclass
class Recording:
    audio_path: Path
    timestamp: datetime
    duration: float
    transcription: str

# NO: Dictionary with magic strings
recording = {
    'audio_path': '/path/to/file.wav',  # String instead of Path
    'timestamp': '2025-10-23T14:30:22',  # String instead of datetime
    'duration': 5.3,
    'transcription': 'Hello world'
}
```

### Consequences

**Positive:**
- Catch errors at development time (IDE warnings)
- Better autocomplete and refactoring
- Self-documenting code
- Type checkers (mypy) can verify correctness

**Negative:**
- Slightly more code for serialization (to_dict/from_dict methods)
- Need to convert when working with JSON

**Acceptable Trade-offs:**
- Small serialization overhead worth the safety
- JSON only at boundaries (storage, network)

### Migration Path

This is a foundational decision - no migration needed as we're starting fresh.

---

## Decision Template (for future decisions)

```markdown
## Decision X: [Title]

**Date**: YYYY-MM-DD
**Status**: Proposed | Accepted | Superseded | Deprecated

### Context
What problem are we solving? What constraints exist?

### Options Considered
List 2-3 alternatives with pros/cons

### Decision
What we chose and why

### Consequences
Trade-offs and implications

### Migration Path
When to reconsider and how to change
```

---

## Questions for Future Decisions

Track questions that need decisions later:

### Open Questions

1. **LLM Integration**: When to add LLM cleanup?
   - After MVP with whisper.cpp working?
   - Make it optional feature?
   - Which provider first? (Claude API vs local mlx-lm)

2. **Settings Persistence**: JSON vs SQLite?
   - JSON fine for simple config
   - SQLite if we add history search, stats, etc.

3. **History Window**: When to build?
   - After transcription works?
   - Make it the second feature?

4. **Distribution**: How to package?
   - py2app for macOS .app bundle?
   - PyInstaller?
   - Need to bundle Whisper models or download on first run?

5. **Error Handling**: How to report errors to user?
   - Notifications only?
   - Error log file?
   - Sentry/crash reporting?

### Deferred Decisions

These decisions are explicitly deferred until we have more information:

1. **Multi-language support**: Wait until English works perfectly
2. **Cloud sync**: Wait until local works well
3. **Custom vocabulary**: Wait until we understand accuracy issues
4. **Keyboard shortcut customization**: Wait until Option+Space proves limiting

---

## Decision Principles

Guidelines for making future decisions:

1. **YAGNI**: Don't build it until you need it
2. **Rule of Three**: Abstract after 2 repetitions, not before
3. **Simple First**: Start simple, refactor when complexity is justified
4. **Measure**: Make decisions based on real usage data, not speculation
5. **Reversible**: Prefer decisions that are easy to change later
6. **Document**: Write down the reasoning so future-you understands

---

## References

- [Architectural Decision Records (ADRs)](https://adr.github.io/)
- [YAGNI Principle](https://martinfowler.com/bliki/Yagni.html)
- [Rule of Three](https://en.wikipedia.org/wiki/Rule_of_three_(computer_programming))
