"""Data models for Dictator app.

This module defines the core data structures used throughout the application.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import json

from dictator.services.llm_corrector import DEFAULT_CORRECTION_PROMPT


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
        custom_vocabulary: List of custom words, names, technical terms
        llm_correction_enabled: Whether to use LLM for transcript correction
        llm_provider: LLM provider to use (currently only "bedrock")
        aws_profile: AWS profile name (empty = default credential chain)
        bedrock_model: Bedrock model identifier
        bedrock_region: AWS region for Bedrock
        correction_prompt: System prompt for LLM correction
        remove_silence_enabled: Whether to remove silence before processing
        silence_threshold: RMS threshold for detecting silence (0-1)
        min_silence_duration: Minimum silence duration to remove (seconds)
    """
    recordings_dir: Path
    whisper_model: str = "large-v3-turbo"
    whisper_threads: int = 8
    custom_vocabulary: list[str] = field(default_factory=list)
    llm_correction_enabled: bool = False
    llm_provider: str = "bedrock"
    aws_profile: str = ""
    bedrock_model: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    bedrock_region: str = "us-east-1"
    correction_prompt: str = field(default_factory=lambda: DEFAULT_CORRECTION_PROMPT)
    remove_silence_enabled: bool = False  # Disabled by default for safety
    silence_threshold: float = 0.01  # Same as voice detection threshold
    min_silence_duration: float = 0.5  # Remove silence longer than 500ms

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
            "custom_vocabulary": self.custom_vocabulary,
            "llm_correction_enabled": self.llm_correction_enabled,
            "llm_provider": self.llm_provider,
            "aws_profile": self.aws_profile,
            "bedrock_model": self.bedrock_model,
            "bedrock_region": self.bedrock_region,
            "correction_prompt": self.correction_prompt,
            "remove_silence_enabled": self.remove_silence_enabled,
            "silence_threshold": self.silence_threshold,
            "min_silence_duration": self.min_silence_duration,
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
            custom_vocabulary=data.get("custom_vocabulary", []),
            llm_correction_enabled=data.get("llm_correction_enabled", False),
            llm_provider=data.get("llm_provider", "bedrock"),
            aws_profile=data.get("aws_profile", ""),
            bedrock_model=data.get("bedrock_model", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
            bedrock_region=data.get("bedrock_region", "us-east-1"),
            correction_prompt=data.get("correction_prompt", DEFAULT_CORRECTION_PROMPT),
            remove_silence_enabled=data.get("remove_silence_enabled", False),
            silence_threshold=data.get("silence_threshold", 0.01),
            min_silence_duration=data.get("min_silence_duration", 0.5),
        )
