"""Recording storage and persistence.

Manages saving and loading recordings and metadata.
"""

from pathlib import Path
from typing import List, Optional
from datetime import datetime
import json
import logging

from dictator.models import Recording

logger = logging.getLogger(__name__)


class RecordingStorage:
    """Handles persistence of recordings and metadata.

    Stores metadata in JSON file and manages audio file organization.
    """

    def __init__(self, recordings_dir: Path):
        """Initialize storage.

        Args:
            recordings_dir: Directory to store recordings and metadata
        """
        self.recordings_dir = Path(recordings_dir)
        self.metadata_path = self.recordings_dir / "metadata.json"
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Create recordings directory if it doesn't exist."""
        self.recordings_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        audio_path: Path,
        transcription: str,
        duration: float,
        cleaned_transcription: Optional[str] = None,
    ) -> Recording:
        """Save a new recording.

        Args:
            audio_path: Path to audio file
            transcription: Raw transcribed text from Whisper
            duration: Recording length in seconds
            cleaned_transcription: Optional LLM-cleaned version

        Returns:
            The created Recording object
        """
        recording = Recording(
            audio_path=audio_path,
            timestamp=datetime.now(),
            duration=duration,
            transcription=transcription,
            cleaned_transcription=cleaned_transcription,
        )

        recordings = self.load_all()
        recordings.append(recording)
        self._save_metadata(recordings)

        logger.info(
            "Saved recording",
            extra={
                "audio_path": str(audio_path),
                "duration": duration,
                "transcription_length": len(transcription),
                "cleaned": cleaned_transcription is not None,
            },
        )

        return recording

    def load_all(self) -> List[Recording]:
        """Load all recordings from storage.

        Returns:
            List of all stored recordings
        """
        if not self.metadata_path.exists():
            return []

        try:
            with open(self.metadata_path, "r") as f:
                data = json.load(f)
            return [Recording.from_dict(item) for item in data]
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Malformed metadata file, starting fresh: {e}")
            return []

    def update(self, recording: Recording) -> None:
        """Update an existing recording.

        Args:
            recording: Recording to update
        """
        recordings = self.load_all()

        for i, rec in enumerate(recordings):
            if rec.audio_path == recording.audio_path:
                recordings[i] = recording
                break
        else:
            raise ValueError(
                f"Recording not found: {recording.audio_path}"
            )

        self._save_metadata(recordings)
        logger.info("Updated recording", extra={"audio_path": str(recording.audio_path)})

    def _save_metadata(self, recordings: List[Recording]) -> None:
        """Save metadata to JSON file.

        Args:
            recordings: List of recordings to save
        """
        data = [rec.to_dict() for rec in recordings]
        with open(self.metadata_path, "w") as f:
            json.dump(data, f, indent=2)
