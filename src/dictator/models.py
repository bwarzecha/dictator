"""Data models for Dictator app.

This module defines the core data structures used throughout the application.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import json


@dataclass
class Recording:
    """Represents a single voice recording and its transcription.

    Attributes:
        audio_path: Path to the audio WAV file
        timestamp: When the recording was created
        duration: Length of recording in seconds
        transcription: Raw text from Whisper
        cleaned_transcription: Optional LLM-cleaned version
    """
    audio_path: Path
    timestamp: datetime
    duration: float
    transcription: str
    cleaned_transcription: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "audio_path": str(self.audio_path),
            "timestamp": self.timestamp.isoformat(),
            "duration": self.duration,
            "transcription": self.transcription,
            "cleaned_transcription": self.cleaned_transcription,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Recording":
        """Deserialize from dictionary."""
        return cls(
            audio_path=Path(data["audio_path"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            duration=data["duration"],
            transcription=data["transcription"],
            cleaned_transcription=data.get("cleaned_transcription"),
        )


@dataclass
class AppConfig:
    """Application configuration.

    Attributes:
        recordings_dir: Where to store audio files and metadata
        whisper_model: Model name for whisper.cpp
        whisper_threads: Number of threads for transcription
        llm_enabled: Whether to use LLM for cleanup
        anthropic_api_key: API key for Claude (if LLM enabled)
    """
    recordings_dir: Path
    whisper_model: str = "large-v3-turbo"
    whisper_threads: int = 8
    llm_enabled: bool = False
    anthropic_api_key: Optional[str] = None

    @classmethod
    def default(cls) -> "AppConfig":
        """Create default configuration."""
        home = Path.home()
        recordings_dir = home / ".dictator" / "recordings"
        return cls(recordings_dir=recordings_dir)

    def save(self, path: Path) -> None:
        """Save configuration to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "recordings_dir": str(self.recordings_dir),
            "whisper_model": self.whisper_model,
            "whisper_threads": self.whisper_threads,
            "llm_enabled": self.llm_enabled,
            "anthropic_api_key": self.anthropic_api_key,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        """Load configuration from JSON file."""
        if not path.exists():
            return cls.default()

        with open(path, "r") as f:
            data = json.load(f)

        return cls(
            recordings_dir=Path(data["recordings_dir"]),
            whisper_model=data.get("whisper_model", "large-v3-turbo"),
            whisper_threads=data.get("whisper_threads", 8),
            llm_enabled=data.get("llm_enabled", False),
            anthropic_api_key=data.get("anthropic_api_key"),
        )
