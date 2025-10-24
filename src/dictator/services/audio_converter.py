"""Audio format conversion utilities.

Converts various audio formats (M4A, MP3, OGG, etc.) to WAV for Whisper.
"""

import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

# Supported input formats
SUPPORTED_FORMATS = {".m4a", ".mp3", ".wav", ".ogg", ".mp4", ".flac", ".aac"}


def is_supported_format(file_path: Path) -> bool:
    """Check if audio file format is supported.

    Args:
        file_path: Path to audio file

    Returns:
        True if format is supported
    """
    return file_path.suffix.lower() in SUPPORTED_FORMATS


def get_supported_formats_string() -> str:
    """Get human-readable string of supported formats.

    Returns:
        Comma-separated list of extensions (e.g., "M4A, MP3, WAV, OGG")
    """
    formats = sorted([fmt.upper().lstrip(".") for fmt in SUPPORTED_FORMATS])
    return ", ".join(formats)


def convert_to_wav(
    input_path: Path, output_dir: Path = None
) -> Tuple[Path, float]:
    """Convert audio file to WAV format for Whisper.

    Args:
        input_path: Path to input audio file
        output_dir: Optional output directory (defaults to temp dir)

    Returns:
        Tuple of (output_wav_path, duration_seconds)

    Raises:
        ValueError: If format not supported
        ImportError: If pydub not installed
        Exception: If conversion fails
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if not is_supported_format(input_path):
        raise ValueError(
            f"Unsupported format: {input_path.suffix}. "
            f"Supported: {get_supported_formats_string()}"
        )

    # If already WAV, just return it
    if input_path.suffix.lower() == ".wav":
        logger.info(f"File already WAV format: {input_path}")
        # Get duration using wave module
        import wave

        with wave.open(str(input_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration = frames / float(rate)
        return input_path, duration

    # Import pydub for conversion
    try:
        from pydub import AudioSegment
    except ImportError:
        raise ImportError(
            "pydub is required for audio format conversion. "
            "Install with: pip install pydub"
        )

    logger.info(
        f"Converting {input_path.suffix} to WAV",
        extra={"input": str(input_path)},
    )

    # Load audio file
    try:
        audio = AudioSegment.from_file(str(input_path))
    except Exception as e:
        raise Exception(f"Failed to load audio file: {e}")

    # Prepare output path
    if output_dir is None:
        output_dir = input_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{input_path.stem}_converted.wav"

    # Convert to WAV (16kHz mono for Whisper)
    try:
        # Whisper expects 16kHz mono
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(str(output_path), format="wav")

        duration = len(audio) / 1000.0  # Convert ms to seconds

        logger.info(
            "Conversion complete",
            extra={
                "output": str(output_path),
                "duration": duration,
                "size_mb": output_path.stat().st_size / 1024 / 1024,
            },
        )

        return output_path, duration

    except Exception as e:
        raise Exception(f"Failed to convert audio: {e}")
