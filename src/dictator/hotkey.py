"""Global hotkey listener.

Listens for Option+Space keyboard combination system-wide.
"""

from typing import Callable, Set
import logging
from pynput import keyboard

logger = logging.getLogger(__name__)


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
        """Start listening for hotkey in background thread."""
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()
        logger.info("Hotkey listener started")

    def stop(self) -> None:
        """Stop listening and cleanup."""
        if self._listener:
            self._listener.stop()
            logger.info("Hotkey listener stopped")

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
