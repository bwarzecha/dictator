"""Whisper model download manager.

Handles model detection, downloading, and status tracking.
"""

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Information about a Whisper model."""

    name: str
    size_mb: int
    speed_rating: str  # "fast", "balanced", "accurate"
    description: str

    @property
    def display_name(self) -> str:
        """Get display name with size."""
        if self.size_mb < 1024:
            return f"{self.name} ({self.size_mb}MB)"
        else:
            size_gb = self.size_mb / 1024
            return f"{self.name} ({size_gb:.1f}GB)"


# Model catalog with sizes and characteristics
WHISPER_MODELS = {
    "tiny.en": ModelInfo(
        name="tiny.en",
        size_mb=75,
        speed_rating="fast",
        description="Fastest English-only. ~10x realtime",
    ),
    "tiny": ModelInfo(
        name="tiny",
        size_mb=75,
        speed_rating="fast",
        description="Fastest multilingual. ~10x realtime",
    ),
    "base.en": ModelInfo(
        name="base.en",
        size_mb=142,
        speed_rating="fast",
        description="Fast English-only with better accuracy. ~7x realtime",
    ),
    "base": ModelInfo(
        name="base",
        size_mb=142,
        speed_rating="fast",
        description="Fast multilingual. ~7x realtime",
    ),
    "small.en": ModelInfo(
        name="small.en",
        size_mb=466,
        speed_rating="balanced",
        description="Balanced English-only. ~4x realtime",
    ),
    "small": ModelInfo(
        name="small",
        size_mb=466,
        speed_rating="balanced",
        description="Balanced multilingual. ~4x realtime",
    ),
    "medium.en": ModelInfo(
        name="medium.en",
        size_mb=1536,
        speed_rating="balanced",
        description="Accurate English-only. ~2x realtime",
    ),
    "medium": ModelInfo(
        name="medium",
        size_mb=1536,
        speed_rating="balanced",
        description="Accurate multilingual. ~2x realtime",
    ),
    "large-v3-turbo": ModelInfo(
        name="large-v3-turbo",
        size_mb=1546,
        speed_rating="accurate",
        description="Best balance, multilingual only. ~2x realtime",
    ),
    "large-v3": ModelInfo(
        name="large-v3",
        size_mb=2965,
        speed_rating="accurate",
        description="Most accurate, multilingual only. ~1x realtime",
    ),
}


class WhisperModelManager:
    """Manages Whisper model downloads and caching."""

    def __init__(self):
        """Initialize model manager."""
        self.cache_dir = self._get_cache_dir()

    def _get_cache_dir(self) -> Path:
        """Get whisper model cache directory.

        pywhispercpp stores models in ~/.cache/whisper/
        """
        home = Path.home()
        cache_dir = home / ".cache" / "whisper"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def _get_model_path(self, model_name: str) -> Path:
        """Get expected path for a model file.

        pywhispercpp downloads models as ggml-{model}.bin
        """
        return self.cache_dir / f"ggml-{model_name}.bin"

    def is_model_downloaded(self, model_name: str) -> bool:
        """Check if a model is already downloaded.

        Args:
            model_name: Name of the model (e.g., "small", "large-v3")

        Returns:
            True if model file exists in cache
        """
        model_path = self._get_model_path(model_name)
        exists = model_path.exists()

        if exists:
            # Verify file size is reasonable (at least 1MB)
            size_mb = model_path.stat().st_size / (1024 * 1024)
            if size_mb < 1:
                logger.warning(
                    "Model file too small, may be corrupted",
                    extra={"model": model_name, "size_mb": size_mb},
                )
                return False

        logger.debug(
            "Model download check",
            extra={"model": model_name, "downloaded": exists},
        )
        return exists

    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """Get information about a model.

        Args:
            model_name: Name of the model

        Returns:
            ModelInfo if model is known, None otherwise
        """
        return WHISPER_MODELS.get(model_name)

    def get_all_models(self) -> list[ModelInfo]:
        """Get list of all available models.

        Returns:
            List of ModelInfo objects sorted by size
        """
        return sorted(WHISPER_MODELS.values(), key=lambda m: m.size_mb)

    def download_model_async(
        self,
        model_name: str,
        completion_callback: Optional[Callable[[bool, str], None]] = None,
    ) -> Thread:
        """Download a model asynchronously.

        Args:
            model_name: Name of the model to download
            completion_callback: Called with (success, message) when done

        Returns:
            Thread object (already started)
        """

        def download_worker():
            """Worker function for download thread."""
            try:
                logger.info("Starting model download", extra={"model": model_name})

                # Import here to avoid circular dependency
                from pywhispercpp.model import Model

                # Download model (this blocks until complete)
                # pywhispercpp doesn't provide granular progress, so we just wait
                _ = Model(model_name, n_threads=1, print_progress=False)

                logger.info("Model download complete", extra={"model": model_name})

                if completion_callback:
                    completion_callback(True, f"Model {model_name} downloaded successfully")

            except Exception as e:
                error_msg = f"Failed to download {model_name}: {str(e)}"
                logger.error("Model download failed", extra={"error": str(e)})

                if completion_callback:
                    completion_callback(False, error_msg)

        thread = Thread(target=download_worker, daemon=True)
        thread.start()
        return thread

    def get_downloaded_models(self) -> list[str]:
        """Get list of all downloaded model names.

        Returns:
            List of model names that are downloaded
        """
        downloaded = []
        for model_name in WHISPER_MODELS.keys():
            if self.is_model_downloaded(model_name):
                downloaded.append(model_name)
        return downloaded

    def estimate_disk_space_needed(self, model_name: str) -> int:
        """Estimate disk space needed for a model.

        Args:
            model_name: Name of the model

        Returns:
            Size in MB, or 0 if model already downloaded
        """
        if self.is_model_downloaded(model_name):
            return 0

        model_info = self.get_model_info(model_name)
        return model_info.size_mb if model_info else 0

    def get_available_disk_space(self) -> int:
        """Get available disk space in cache directory.

        Returns:
            Available space in MB
        """
        stat = os.statvfs(self.cache_dir)
        available_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
        return int(available_mb)
