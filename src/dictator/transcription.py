"""Speech-to-text transcription using Whisper.

Uses whisper.cpp for fast, local transcription.
"""

from pathlib import Path
from typing import Optional, Callable
import logging
import time
import threading
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
        self._model_lock = threading.RLock()  # Reentrant lock for model loading thread safety

    def load_model(self) -> None:
        """Load the Whisper model into memory (thread-safe).

        First call will download model if not present.
        Uses a lock to prevent concurrent loading from multiple threads,
        which can cause segfaults in the C++ Whisper library.
        """
        thread_name = threading.current_thread().name
        logger.info(f"[{thread_name}] Attempting to acquire model lock for loading")

        with self._model_lock:
            logger.info(f"[{thread_name}] Model lock acquired, checking if model already loaded")

            if self._model is not None:
                logger.info(f"[{thread_name}] Model already loaded, skipping")
                return

            logger.info(
                f"[{thread_name}] Loading Whisper model",
                extra={"model": self.model_name, "threads": self.n_threads},
            )

            # Check if model needs downloading
            from dictator.services.model_manager import WhisperModelManager

            model_manager = WhisperModelManager()
            if not model_manager.is_model_downloaded(self.model_name):
                msg = f"Downloading model {self.model_name}..."
                logger.info(f"[{thread_name}] {msg}")
                if self.download_progress_callback:
                    self.download_progress_callback(msg)

            try:
                logger.info(f"[{thread_name}] Initializing pywhispercpp.Model (C++ library)")
                self._model = Model(self.model_name, n_threads=self.n_threads)
                logger.info(f"[{thread_name}] Model loaded successfully")
            except Exception as e:
                logger.error(f"[{thread_name}] Failed to load model: {e}")
                self._model = None
                raise

        logger.info(f"[{thread_name}] Model lock released")

    def reload_model(self) -> None:
        """Force reload the Whisper model (thread-safe).

        Used for recovery after crashes/segfaults.
        """
        thread_name = threading.current_thread().name
        logger.info(f"[{thread_name}] Force reloading Whisper model")

        with self._model_lock:
            logger.info(f"[{thread_name}] Model lock acquired for reload, clearing model")
            self._model = None  # Clear existing model

        # load_model() will acquire lock again (RLock allows same thread to re-acquire)
        self.load_model()

    def transcribe(self, audio_path: Path) -> str:
        """Transcribe audio file to text with retry logic.

        Args:
            audio_path: Path to audio file

        Returns:
            Transcribed text

        Raises:
            FileNotFoundError: If audio file doesn't exist
            RuntimeError: If transcription fails after retries
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Build initial_prompt with vocabulary (SuperWhisper style)
        initial_prompt = self._build_initial_prompt()

        # Try transcription with retry logic for segfaults
        max_retries = 3
        thread_name = threading.current_thread().name

        for attempt in range(max_retries):
            try:
                # Check if model needs loading (thread-safe via load_model's lock)
                if self._model is None:
                    logger.info(f"[{thread_name}] Model not loaded, loading now (attempt {attempt + 1})")
                    self.load_model()

                logger.info(
                    f"[{thread_name}] Starting transcription",
                    extra={
                        "model": self.model_name,
                        "threads": self.n_threads,
                        "audio_path": str(audio_path),
                        "vocab_count": len(self.custom_vocabulary),
                        "attempt": attempt + 1,
                    },
                )
                logger.info(f"[{thread_name}] 🎙️  Using Whisper model: {self.model_name} ({self.n_threads} threads)")

                # Transcribe with initial_prompt (C++ library call - not thread-safe for loading)
                logger.info(f"[{thread_name}] Calling C++ transcribe() method")
                segments = self._model.transcribe(
                    str(audio_path), initial_prompt=initial_prompt
                )
                text = "".join([seg.text for seg in segments]).strip()

                logger.info(
                    "Transcription complete",
                    extra={"text_length": len(text), "char_count": len(text)},
                )

                return text

            except Exception as e:
                logger.error(f"[{thread_name}] Transcription failed (attempt {attempt + 1}/{max_retries}): {e}")

                # If segfault or model failure, try reloading
                if attempt < max_retries - 1:
                    logger.warning(f"[{thread_name}] Attempting to reload model and retry")

                    # Clear potentially corrupted model (thread-safe)
                    with self._model_lock:
                        logger.info(f"[{thread_name}] Clearing potentially corrupted model")
                        self._model = None

                    time.sleep(1.0)  # Brief pause before retry
                else:
                    raise RuntimeError(f"Transcription failed after {max_retries} attempts: {e}")

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
