"""Audio recording functionality.

Records audio from microphone and saves to WAV files.
"""

from pathlib import Path
from typing import Tuple, List
from datetime import datetime
import logging
import sounddevice as sd
import numpy as np
import wave

logger = logging.getLogger(__name__)


class AudioRecorder:
    """Records audio from microphone.

    Records mono 16kHz audio suitable for Whisper transcription.
    """

    def __init__(self, sample_rate: int = 16000, recordings_dir: Path = None):
        """Initialize audio recorder.

        Args:
            sample_rate: Sample rate in Hz (16000 for Whisper)
            recordings_dir: Directory to save recordings
        """
        self.sample_rate = sample_rate
        self.recordings_dir = Path(recordings_dir) if recordings_dir else Path.home() / ".dictator" / "recordings"
        self.recordings_dir.mkdir(parents=True, exist_ok=True)

        self._recording = False
        self._audio_data: List[np.ndarray] = []
        self._stream = None

    def start_recording(self) -> None:
        """Start recording audio from microphone."""
        if self._recording:
            logger.warning("Already recording")
            return

        self._recording = True
        self._audio_data = []

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.int16,
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.info("Started recording", extra={"sample_rate": self.sample_rate})

    def stop_recording(self) -> Tuple[Path, float]:
        """Stop recording and save to file.

        Returns:
            Tuple of (audio_file_path, duration_seconds)
        """
        if not self._recording:
            raise RuntimeError("Not currently recording")

        self._recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        audio_path = self._save_audio()
        duration = self.get_duration()

        logger.info(
            "Stopped recording",
            extra={"path": str(audio_path), "duration": duration},
        )

        return audio_path, duration

    def get_duration(self) -> float:
        """Get current recording duration in seconds.

        Returns:
            Current duration
        """
        if not self._audio_data:
            return 0.0

        total_samples = sum(len(chunk) for chunk in self._audio_data)
        return total_samples / self.sample_rate

    @property
    def is_recording(self) -> bool:
        """Check if currently recording.

        Returns:
            True if recording in progress
        """
        return self._recording

    def _audio_callback(self, indata: np.ndarray, frames: int, time, status) -> None:
        """Callback for audio stream.

        Args:
            indata: Input audio data
            frames: Number of frames
            time: Time info
            status: Stream status
        """
        if status:
            logger.warning(f"Audio stream status: {status}")

        if self._recording:
            self._audio_data.append(indata.copy())

    def _save_audio(self) -> Path:
        """Save recorded audio to WAV file.

        Returns:
            Path to saved audio file
        """
        if not self._audio_data:
            raise ValueError("No audio data to save")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_path = self.recordings_dir / f"recording_{timestamp}.wav"

        audio_array = np.concatenate(self._audio_data, axis=0)

        with wave.open(str(audio_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_array.tobytes())

        logger.info(
            "Saved audio file",
            extra={
                "path": str(audio_path),
                "size_bytes": audio_path.stat().st_size,
            },
        )

        return audio_path
