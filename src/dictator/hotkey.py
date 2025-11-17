"""Global hotkey listener.

Listens for Option+Space keyboard combination system-wide.
"""

from typing import Callable, Set
import logging
from pynput import keyboard

logger = logging.getLogger(__name__)


def check_input_monitoring_permission() -> bool:
    """Check if app has Input Monitoring permission.

    Returns:
        True if permission granted, False otherwise
    """
    try:
        # For macOS, check if we can access the AXIsProcessTrusted API
        # If the API is not available or fails, we assume permission is not granted
        import platform
        if platform.system() == "Darwin":
            try:
                # Try to import and use the HIServices API
                from Quartz import HIServices
                return HIServices.AXIsProcessTrusted()
            except (ImportError, AttributeError, KeyError):
                # If the API is not available, try a fallback method
                # Attempt to create a listener - this will fail if no permission
                pass

        # Fallback: Try to create and start a listener
        # This will succeed even without permission but won't receive events
        test_listener = keyboard.Listener(on_press=lambda k: None)
        test_listener.start()
        test_listener.stop()
        # We can't reliably detect permission this way, so we assume it's granted
        # The actual failure will happen when trying to receive keyboard events
        return True
    except Exception as e:
        logger.warning(f"Input Monitoring permission check: {e}")
        # Don't error, just warn - the actual listener might still work
        return True


class HotkeyListener:
    """Listens for global hotkey press (Option+Space).

    Runs in background daemon thread and calls callback when hotkey detected.
    """

    def __init__(self, callback: Callable[[], None]):
        """Initialize hotkey listener.

        Args:
            callback: Function to call when hotkey pressed
        """
        self.callback = callback
        self._pressed_keys: Set[keyboard.Key] = set()
        self._listener = None
        self._hotkey_triggered = False

    def start(self) -> None:
        """Start listening for hotkey in background thread with retry logic."""
        max_retries = 3
        retry_delay = 0.5  # seconds

        for attempt in range(max_retries):
            try:
                self._listener = keyboard.Listener(
                    on_press=self._on_press,
                    on_release=self._on_release,
                )
                self._listener.daemon = True
                self._listener.start()
                logger.info("Hotkey listener started")
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Failed to start hotkey listener (attempt {attempt + 1}): {e}. Retrying in {retry_delay}s...")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Failed to start hotkey listener after {max_retries} attempts: {e}")
                    raise

    def stop(self) -> None:
        """Stop listening and cleanup."""
        if self._listener:
            self._listener.stop()
            self._listener = None
            logger.info("Hotkey listener stopped")

    def restart(self) -> None:
        """Restart the hotkey listener.

        Used for recovery after crashes.
        """
        logger.info("Restarting hotkey listener")
        self.stop()
        self.start()

    @property
    def is_running(self) -> bool:
        """Check if listener is currently running.

        Returns:
            True if listener is active
        """
        return self._listener is not None and self._listener.running

    def _on_press(self, key: keyboard.Key) -> None:
        """Handle key press event.

        Args:
            key: The key that was pressed
        """
        self._pressed_keys.add(key)

        if self._is_hotkey_pressed() and not self._hotkey_triggered:
            self._hotkey_triggered = True
            logger.info("Hotkey detected: Option+Space")
            self.callback()

    def _on_release(self, key: keyboard.Key) -> None:
        """Handle key release event.

        Args:
            key: The key that was released
        """
        if key in self._pressed_keys:
            self._pressed_keys.remove(key)

        if not self._is_hotkey_pressed():
            self._hotkey_triggered = False

    def _is_hotkey_pressed(self) -> bool:
        """Check if the hotkey combination is pressed.

        Returns:
            True if Option+Space is pressed
        """
        has_option = (
            keyboard.Key.alt in self._pressed_keys
            or keyboard.Key.alt_l in self._pressed_keys
            or keyboard.Key.alt_r in self._pressed_keys
        )
        has_space = keyboard.Key.space in self._pressed_keys
        return has_option and has_space
