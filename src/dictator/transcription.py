"""Speech-to-text transcription using Whisper.

Uses whisper.cpp for fast, local transcription.
"""

from pathlib import Path
from typing import Optional, Callable
import logging
from pywhispercpp.model import Model

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    """Transcribes audio using Whisper model.

    Uses whisper.cpp Python bindings for fast local transcription.
    """

    def __init__(
        self,
        model_name: str = "large-v3-turbo",
        n_threads: int = 8,
        custom_vocabulary: Optional[list[str]] = None,
        download_progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize transcriber.

        Args:
            model_name: Whisper model to use
            n_threads: Number of CPU threads for transcription
            custom_vocabulary: Optional list of custom words for better recognition
            download_progress_callback: Optional callback for download progress messages
        """
        self.model_name = model_name
        self.n_threads = n_threads
        self.custom_vocabulary = custom_vocabulary or []
        self.download_progress_callback = download_progress_callback
        self._model = None

    def load_model(self) -> None:
        """Load the Whisper model into memory.

        First call will download model if not present.
        """
        if self._model is not None:
            logger.info("Model already loaded")
            return

        logger.info(
            "Loading Whisper model",
            extra={"model": self.model_name, "threads": self.n_threads},
        )

        # Check if model needs downloading
        from dictator.services.model_manager import WhisperModelManager

        model_manager = WhisperModelManager()
        if not model_manager.is_model_downloaded(self.model_name):
            msg = f"Downloading model {self.model_name}..."
            logger.info(msg)
            if self.download_progress_callback:
                self.download_progress_callback(msg)

        self._model = Model(self.model_name, n_threads=self.n_threads)

        logger.info("Model loaded successfully")

    def transcribe(self, audio_path: Path) -> str:
        """Transcribe audio file to text.

        Args:
            audio_path: Path to audio file

        Returns:
            Transcribed text

        Raises:
            FileNotFoundError: If audio file doesn't exist
            RuntimeError: If model not loaded
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if self._model is None:
            logger.info("Model not loaded, loading now")
            self.load_model()

        # Build initial_prompt with vocabulary (SuperWhisper style)
        initial_prompt = self._build_initial_prompt()

        logger.info(
            "Starting transcription",
            extra={
                "model": self.model_name,
                "threads": self.n_threads,
                "audio_path": str(audio_path),
                "vocab_count": len(self.custom_vocabulary),
            },
        )
        logger.info(f"🎙️  Using Whisper model: {self.model_name} ({self.n_threads} threads)")

        # Transcribe with initial_prompt
        segments = self._model.transcribe(
            str(audio_path), initial_prompt=initial_prompt
        )
        text = "".join([seg.text for seg in segments]).strip()

        logger.info(
            "Transcription complete",
            extra={"text_length": len(text), "char_count": len(text)},
        )

        return text

    def _build_initial_prompt(self) -> str:
        """Build initial prompt for Whisper.

        Returns:
            Initial prompt string (SuperWhisper-style)
        """
        if not self.custom_vocabulary:
            # Default prompt for better punctuation
            return "Hello."

        # SuperWhisper format: "Hello, here are some of the names and words that might be used: ..."
        vocab_str = ", ".join(self.custom_vocabulary)
        return f"Hello, here are some of the names and words that might be used: {vocab_str}"

    @property
    def is_ready(self) -> bool:
        """Check if model is loaded and ready.

        Returns:
            True if model loaded
        """
        return self._model is not None
