"""Common audio processing pipeline.

Handles transcription, LLM correction, and text insertion
for both live recordings and uploaded files.
"""

import logging
from pathlib import Path
from typing import Optional, Callable

from dictator.transcription import WhisperTranscriber
from dictator.services.llm_corrector import LLMCorrector
from dictator.insertion import TextInserter
from dictator.storage import RecordingStorage

logger = logging.getLogger(__name__)


class ProcessingResult:
    """Result from audio processing pipeline."""

    def __init__(
        self,
        raw_text: str,
        cleaned_text: str,
        inserted: bool,
        correction_failed: bool = False,
    ):
        """Initialize processing result.

        Args:
            raw_text: Raw transcription from Whisper
            cleaned_text: LLM-corrected text (or raw if correction disabled)
            inserted: Whether text was successfully inserted
            correction_failed: Whether LLM correction failed
        """
        self.raw_text = raw_text
        self.cleaned_text = cleaned_text
        self.inserted = inserted
        self.correction_failed = correction_failed


class AudioProcessor:
    """Processes audio files through transcription pipeline.

    Orchestrates: Whisper transcription → LLM correction → text insertion
    """

    def __init__(
        self,
        transcriber: WhisperTranscriber,
        storage: RecordingStorage,
        llm_corrector: Optional[LLMCorrector] = None,
        inserter: Optional[TextInserter] = None,
    ):
        """Initialize audio processor.

        Args:
            transcriber: Whisper transcriber instance
            storage: Recording storage instance
            llm_corrector: Optional LLM corrector for text cleanup
            inserter: Optional text inserter for auto-insertion
        """
        self.transcriber = transcriber
        self.storage = storage
        self.llm_corrector = llm_corrector
        self.inserter = inserter

    def process(
        self,
        audio_path: Path,
        duration: float,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> ProcessingResult:
        """Process audio file through complete pipeline.

        Args:
            audio_path: Path to audio file (WAV format)
            duration: Audio duration in seconds
            progress_callback: Optional callback for status updates

        Returns:
            ProcessingResult with transcription and insertion status

        Raises:
            FileNotFoundError: If audio file doesn't exist
            Exception: If transcription or correction fails
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Step 1: Transcribe
        if progress_callback:
            progress_callback("Transcribing...")

        logger.info(
            "Starting transcription",
            extra={"audio_path": str(audio_path), "duration": duration},
        )

        raw_text = self.transcriber.transcribe(audio_path)
        cleaned_text = raw_text
        correction_failed = False

        # Step 2: LLM correction (if enabled)
        if self.llm_corrector:
            try:
                if progress_callback:
                    progress_callback("Correcting...")

                logger.info("Applying LLM correction to transcript")
                cleaned_text = self.llm_corrector.correct(raw_text)
                logger.info("LLM correction successful")

            except Exception as e:
                logger.error(f"LLM correction failed: {e}")
                correction_failed = True
                # Continue with raw text

        # Step 3: Save to storage
        if progress_callback:
            progress_callback("Saving...")

        self.storage.save(
            audio_path,
            transcription=raw_text,
            cleaned_transcription=cleaned_text,
            duration=duration,
        )

        # Step 4: Insert text (if inserter provided)
        inserted = False
        if self.inserter:
            if progress_callback:
                progress_callback("Inserting...")

            inserted = self.inserter.insert_text(cleaned_text)

            if not inserted:
                logger.info("Text insertion failed, will copy to clipboard")

        logger.info(
            "Processing complete",
            extra={
                "raw_length": len(raw_text),
                "cleaned_length": len(cleaned_text),
                "inserted": inserted,
            },
        )

        return ProcessingResult(
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            inserted=inserted,
            correction_failed=correction_failed,
        )
