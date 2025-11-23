"""Global hotkey listener.

Listens for Option+Space keyboard combination system-wide.
"""

from typing import Callable, Set
import logging
from pynput import keyboard

logger = logging.getLogger(__name__)


def _prewarm_hiservices() -> None:
    """Pre-warm the HIServices module to avoid lazy import race conditions.

    The objc lazy import mechanism has a race condition that can cause
    KeyError when multiple threads try to access the same function.
    This function ensures the module is fully loaded before starting threads.
    """
    try:
        import platform
        if platform.system() == "Darwin":
            import time
            # Import the module and force the lazy loading to complete
            from Quartz import HIServices

            # Try multiple times to ensure the lazy import completes
            # This works around a race condition in objc._lazyimport
            for attempt in range(5):
                try:
                    # Access the function to trigger lazy loading
                    _ = HIServices.AXIsProcessTrusted
                    # If we got here without KeyError, the import is complete
                    logger.debug(f"HIServices pre-warmed successfully on attempt {attempt + 1}")
                    return
                except (KeyError, AttributeError) as e:
                    if attempt < 4:
                        logger.debug(f"HIServices pre-warm attempt {attempt + 1} failed: {e}, retrying...")
                        time.sleep(0.1)
                    else:
                        logger.warning(f"HIServices pre-warm failed after 5 attempts: {e}")
    except ImportError:
        # Not on macOS or Quartz not available
        pass
    except Exception as e:
        logger.warning(f"HIServices pre-warm failed: {e}")


def check_input_monitoring_permission() -> bool:
    """Check if app has Input Monitoring permission.

    Returns:
        True if permission granted, False otherwise
    """
    try:
        # Pre-warm the HIServices module to avoid race conditions
        _prewarm_hiservices()

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
        import time

        # Pre-warm HIServices to avoid race condition
        _prewarm_hiservices()

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

                # Wait a bit to ensure the thread actually starts successfully
                # The KeyError can happen in the thread's _run() method after start() returns
                time.sleep(0.2)

                # Check if the listener is actually running
                if not self._listener.running:
                    raise RuntimeError("Listener thread failed to start or died immediately")

                logger.info("Hotkey listener started successfully")
                return

            except Exception as e:
                # Clean up failed listener
                if self._listener:
                    try:
                        self._listener.stop()
                    except:
                        pass
                    self._listener = None

                if attempt < max_retries - 1:
                    logger.warning(f"Failed to start hotkey listener (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {retry_delay}s...")
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
