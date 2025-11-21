"""Audio recording functionality.

Records audio from microphone and saves to WAV files.
"""

from pathlib import Path
from typing import Tuple, List, Optional, Callable
from datetime import datetime, timedelta
import logging
import sounddevice as sd
import numpy as np
import wave
import threading

logger = logging.getLogger(__name__)


class AudioRecorder:
    """Records audio from microphone.

    Records mono 16kHz audio suitable for Whisper transcription.
    """

    def __init__(self, sample_rate: int = 16000, recordings_dir: Path = None,
                 remove_silence: bool = False, silence_threshold: float = 0.01,
                 min_silence_duration: float = 0.5):
        """Initialize audio recorder.

        Args:
            sample_rate: Sample rate in Hz (16000 for Whisper)
            recordings_dir: Directory to save recordings
            remove_silence: Whether to remove silence before saving
            silence_threshold: RMS threshold for silence detection
            min_silence_duration: Minimum silence duration to remove
        """
        self.sample_rate = sample_rate
        self.recordings_dir = Path(recordings_dir) if recordings_dir else Path.home() / ".dictator" / "recordings"
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.remove_silence = remove_silence
        self.silence_removal_threshold = silence_threshold
        self.min_silence_to_remove = min_silence_duration

        self._recording = False
        self._audio_data: List[np.ndarray] = []
        self._stream = None
        self._current_volume = 0.0  # Real-time volume level (0-1)
        self._volume_history = []  # Track recent volume for smoothing
        self._peak_volume = 0.0  # Track recent peak for display
        self._peak_decay_rate = 0.95  # How fast the peak decays (0.95 = 5% per update)

        # Voice detection monitoring
        self._voice_threshold = 0.01  # RMS threshold for voice detection (adjustable)
        self._silence_start_time: Optional[datetime] = None
        self._silence_duration_threshold = 10.0  # seconds before notification
        self._silence_callback: Optional[Callable[[float], None]] = None
        self._voice_resumed_callback: Optional[Callable[[], None]] = None
        self._silence_notification_sent = False
        self._monitoring_timer = None

    def start_monitoring(self) -> None:
        """Start monitoring audio levels without recording."""
        if self._stream and self._stream.active:
            return  # Already monitoring

        # Clear volume history for fresh readings
        self._volume_history = []
        self._current_volume = 0.0
        self._peak_volume = 0.0  # Reset peak tracking

        # Reset device cache to pick up current system default
        sd.default.reset()

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.int16,
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.info("Started audio monitoring")

    def stop_monitoring(self) -> None:
        """Stop monitoring audio levels."""
        if self._stream and not self._recording:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            self._current_volume = 0.0
            self._volume_history = []
            self._peak_volume = 0.0  # Reset peak tracking
            logger.info("Stopped audio monitoring")

    def start_recording(self) -> None:
        """Start recording audio from microphone."""
        if self._recording:
            logger.warning("Already recording")
            return

        self._recording = True
        self._audio_data = []

        # Reset silence tracking
        self._silence_start_time = None
        self._silence_notification_sent = False

        # If not already monitoring, start stream
        if not self._stream or not self._stream.active:
            # Reset device cache to pick up current system default
            sd.default.reset()

            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype=np.int16,
                callback=self._audio_callback,
            )
            self._stream.start()

        # Start silence monitoring timer
        self._start_silence_monitoring()

        logger.info("Started recording", extra={"sample_rate": self.sample_rate})

    def stop_recording(self) -> Tuple[Path, float]:
        """Stop recording and save to file.

        Returns:
            Tuple of (audio_file_path, duration_seconds)
        """
        if not self._recording:
            raise RuntimeError("Not currently recording")

        self._recording = False

        # Stop silence monitoring
        self._stop_silence_monitoring()

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

    def get_volume_level(self) -> float:
        """Get current audio input volume level with peak tracking.

        Returns:
            Volume level from 0.0 (silence) to 1.0 (maximum)
            Uses peak tracking with decay for better visibility
        """
        # Amplify current volume for better visibility
        amplified_current = min(self._current_volume * 3.0, 1.0)

        # Update peak if current volume is louder
        if amplified_current > self._peak_volume:
            self._peak_volume = amplified_current
        else:
            # Apply decay to peak volume when sound is quieter
            # This creates a smooth fade-out effect
            self._peak_volume *= self._peak_decay_rate

        # Reset to zero if peak is very small (avoid lingering tiny values)
        if self._peak_volume < 0.01:
            self._peak_volume = 0.0

        return self._peak_volume

    def set_silence_callback(self, callback: Callable[[float], None]) -> None:
        """Set callback for when prolonged silence is detected.

        Args:
            callback: Function to call with silence duration in seconds
        """
        self._silence_callback = callback

    def set_voice_resumed_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for when voice is resumed after silence.

        Args:
            callback: Function to call when voice is detected again
        """
        self._voice_resumed_callback = callback

    def set_voice_threshold(self, threshold: float) -> None:
        """Set the RMS threshold for voice detection.

        Args:
            threshold: RMS value below which audio is considered silence (0.0 to 1.0)
        """
        self._voice_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"Voice detection threshold set to {self._voice_threshold}")

    def _check_for_silence(self) -> None:
        """Check if silence has exceeded the threshold duration."""
        if not self._recording:
            return

        # Check if we're in a silence period
        if self._current_volume < self._voice_threshold:
            # Start tracking silence if not already
            if self._silence_start_time is None:
                self._silence_start_time = datetime.now()
                self._silence_notification_sent = False
                logger.debug("Started tracking silence period")

            # Calculate silence duration
            silence_duration = (datetime.now() - self._silence_start_time).total_seconds()

            # Trigger callback if threshold exceeded and not already notified
            if (silence_duration >= self._silence_duration_threshold
                and not self._silence_notification_sent
                and self._silence_callback):
                self._silence_callback(silence_duration)
                self._silence_notification_sent = True
                logger.warning(f"No voice detected for {silence_duration:.1f} seconds")
        else:
            # Voice detected, reset silence tracking
            if self._silence_start_time is not None:
                logger.debug("Voice detected, resetting silence tracker")

                # Call voice resumed callback if we had sent a notification
                if self._silence_notification_sent and self._voice_resumed_callback:
                    self._voice_resumed_callback()

                self._silence_start_time = None
                self._silence_notification_sent = False

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

        # Calculate RMS (Root Mean Square) volume level
        # Convert to float for calculations
        audio_float = indata.astype(np.float32) / 32768.0  # Normalize int16 to -1.0 to 1.0
        rms = np.sqrt(np.mean(audio_float ** 2))

        # Apply smoothing with a sliding window
        self._volume_history.append(rms)
        if len(self._volume_history) > 10:  # Keep last 10 readings for smoother transitions
            self._volume_history.pop(0)

        # Use weighted average for smoother display (recent values have more weight)
        if self._volume_history:
            # Apply exponential weighting - more recent values matter more
            weights = np.exp(np.linspace(-1, 0, len(self._volume_history)))
            weights = weights / weights.sum()  # Normalize weights
            self._current_volume = np.average(self._volume_history, weights=weights)
        else:
            self._current_volume = 0.0

        if self._recording:
            self._audio_data.append(indata.copy())

    def _save_audio(self) -> Path:
        """Save recorded audio to WAV file.

        Returns:
            Path to saved audio file
        """
        if not self._audio_data:
            raise ValueError("No audio data to save")

        # Apply silence removal if enabled
        audio_chunks = self._audio_data
        if self.remove_silence:
            logger.info("Applying silence removal before saving...")
            audio_chunks = self.remove_silence_from_audio(
                audio_chunks,
                threshold=self.silence_removal_threshold,
                min_silence_duration=self.min_silence_to_remove
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_path = self.recordings_dir / f"recording_{timestamp}.wav"

        audio_array = np.concatenate(audio_chunks, axis=0)

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

    def _start_silence_monitoring(self) -> None:
        """Start periodic timer to check for prolonged silence."""
        def check_silence():
            while self._recording:
                self._check_for_silence()
                threading.Event().wait(1.0)  # Check every second

        self._monitoring_timer = threading.Thread(target=check_silence, daemon=True)
        self._monitoring_timer.start()

    def _stop_silence_monitoring(self) -> None:
        """Stop the silence monitoring timer."""
        # Thread will exit when self._recording becomes False
        self._monitoring_timer = None

    def remove_silence_from_audio(
        self,
        audio_data: List[np.ndarray],
        threshold: float = 0.01,
        min_silence_duration: float = 0.5,
    ) -> List[np.ndarray]:
        """Remove silence from audio data while preserving short pauses.

        Args:
            audio_data: List of audio chunks
            threshold: RMS threshold for silence detection
            min_silence_duration: Minimum silence duration to remove (seconds)

        Returns:
            Audio data with long silences removed
        """
        if not audio_data:
            return audio_data

        # Calculate chunk duration (samples per chunk / sample rate)
        chunk_size = len(audio_data[0]) if audio_data else 0
        chunk_duration = chunk_size / self.sample_rate if chunk_size > 0 else 0

        if chunk_duration == 0:
            return audio_data

        # Calculate minimum consecutive silent chunks to remove
        min_silent_chunks = int(min_silence_duration / chunk_duration)

        # Analyze each chunk for voice activity
        voice_activity = []
        for chunk in audio_data:
            # Calculate RMS for chunk
            audio_float = chunk.astype(np.float32) / 32768.0
            rms = np.sqrt(np.mean(audio_float ** 2))
            voice_activity.append(rms >= threshold)

        # Find segments to keep (voice + short silences)
        segments_to_keep = []
        current_segment = []
        silence_count = 0

        for i, has_voice in enumerate(voice_activity):
            if has_voice:
                # Voice detected - keep current segment and this chunk
                if silence_count > 0 and silence_count < min_silent_chunks:
                    # Keep short silence between speech
                    current_segment.extend(audio_data[i - silence_count:i + 1])
                else:
                    # Start new segment or continue current
                    current_segment.append(audio_data[i])
                silence_count = 0
            else:
                # Silence detected
                silence_count += 1
                if silence_count >= min_silent_chunks and current_segment:
                    # Long silence - save current segment and start new
                    segments_to_keep.append(current_segment)
                    current_segment = []

        # Add final segment if exists
        if current_segment:
            segments_to_keep.append(current_segment)

        # Flatten segments back to single list
        if segments_to_keep:
            result = []
            for segment in segments_to_keep:
                result.extend(segment)

            # Log silence removal stats
            original_duration = len(audio_data) * chunk_duration
            new_duration = len(result) * chunk_duration
            removed_duration = original_duration - new_duration

            if removed_duration > 0:
                logger.info(
                    f"Removed {removed_duration:.1f}s of silence "
                    f"(kept {new_duration:.1f}s from {original_duration:.1f}s)"
                )

            return result

        return audio_data  # Return original if no voice detected
