"""Text insertion into focused application.

Uses multiple strategies for reliable text insertion:
1. kAXSelectedTextAttribute (fast, works with native apps)
2. kAXValue (fallback for simple text fields)
3. Clipboard + Cmd+V paste (universal, works everywhere)
"""

import logging
import time
from AppKit import NSPasteboard, NSStringPboardType
from ApplicationServices import (
    AXUIElementCreateSystemWide,
    AXUIElementCopyAttributeValue,
    AXUIElementSetAttributeValue,
    kAXErrorSuccess,
    kAXErrorAPIDisabled,
    kAXErrorNotImplemented,
    kAXErrorInvalidUIElement,
)
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    kCGHIDEventTap,
    kCGEventFlagMaskCommand,
)

logger = logging.getLogger(__name__)

ERROR_MESSAGES = {
    kAXErrorAPIDisabled: "Accessibility API is disabled. Grant accessibility permissions in System Settings.",
    kAXErrorNotImplemented: "Focused element doesn't support text insertion",
    kAXErrorInvalidUIElement: "No valid UI element is focused",
}

# Virtual key code for 'V' key
V_KEY_CODE = 9


class TextInserter:
    """Inserts text into the currently focused application.

    Uses a hybrid approach with multiple fallback strategies:
    1. Try kAXSelectedTextAttribute (fast, native apps)
    2. Try kAXValue (simple text fields)
    3. Fallback to clipboard+paste (universal compatibility)
    """

    def insert_text(self, text: str) -> bool:
        """Insert text at current cursor position using best available method.

        Args:
            text: Text to insert

        Returns:
            True if insertion successful, False otherwise
        """
        if not text:
            logger.warning("Empty text provided for insertion")
            return False

        # Strategy 1: Try kAXSelectedTextAttribute (best for native apps)
        if self._insert_via_selected_text(text):
            logger.info(
                "Text inserted via kAXSelectedTextAttribute",
                extra={"text_length": len(text), "method": "selected_text"}
            )
            return True

        # Strategy 2: Try kAXValue (fallback for simple fields)
        if self._insert_via_value(text):
            logger.info(
                "Text inserted via kAXValue",
                extra={"text_length": len(text), "method": "value"}
            )
            return True

        # Strategy 3: Universal clipboard+paste (works everywhere)
        if self._insert_via_clipboard_paste(text):
            logger.info(
                "Text inserted via clipboard paste",
                extra={"text_length": len(text), "method": "clipboard"}
            )
            return True

        logger.error("All text insertion methods failed")
        return False

    def _get_focused_element(self):
        """Get the currently focused UI element.

        Returns:
            Tuple of (focused_element, error_code) or (None, error_code)
        """
        system_wide = AXUIElementCreateSystemWide()

        error_code, focused_app = AXUIElementCopyAttributeValue(
            system_wide, "AXFocusedApplication", None
        )

        if error_code != kAXErrorSuccess:
            return None, error_code

        error_code, focused_element = AXUIElementCopyAttributeValue(
            focused_app, "AXFocusedUIElement", None
        )

        if error_code != kAXErrorSuccess:
            return None, error_code

        return focused_element, kAXErrorSuccess

    def _insert_via_selected_text(self, text: str) -> bool:
        """Insert text using kAXSelectedTextAttribute.

        This method inserts at the cursor position without replacing
        the entire field. Works well with native macOS apps.

        Note: Some apps (Chrome, Electron) falsely report success but
        don't actually insert text. We verify by reading back the value.

        Args:
            text: Text to insert

        Returns:
            True if successful, False otherwise
        """
        try:
            focused_element, error_code = self._get_focused_element()

            if error_code != kAXErrorSuccess:
                logger.debug(
                    f"Cannot get focused element for selected text: {error_code}"
                )
                return False

            # Get value before insertion to verify later
            _, value_before = AXUIElementCopyAttributeValue(
                focused_element, "AXValue", None
            )

            # Try to set selected text directly
            error_code = AXUIElementSetAttributeValue(
                focused_element, "AXSelectedText", text
            )

            if error_code == kAXErrorSuccess:
                # Verify text was actually inserted
                if self._verify_insertion(focused_element, text, value_before):
                    return True
                else:
                    logger.debug(
                        "kAXSelectedText reported success but verification failed"
                    )
                    return False

            # If that didn't work, try getting current selection range
            # and setting it to insert text at cursor
            error_code, current_range = AXUIElementCopyAttributeValue(
                focused_element, "AXSelectedTextRange", None
            )

            if error_code == kAXErrorSuccess and current_range is not None:
                # Set text at current selection (replaces selection or inserts)
                error_code = AXUIElementSetAttributeValue(
                    focused_element, "AXSelectedText", text
                )

                if error_code == kAXErrorSuccess:
                    if self._verify_insertion(focused_element, text, value_before):
                        return True
                    else:
                        logger.debug(
                            "kAXSelectedText reported success but verification failed"
                        )
                        return False

            logger.debug(
                f"kAXSelectedText insertion failed with error: {error_code}"
            )
            return False

        except Exception as e:
            logger.debug(f"Exception in _insert_via_selected_text: {e}")
            return False

    def _verify_insertion(self, element, inserted_text: str, value_before) -> bool:
        """Verify that text was actually inserted.

        Some apps falsely report success. We check if the value changed.

        Args:
            element: The UI element
            inserted_text: Text that should have been inserted
            value_before: Value before insertion (or None)

        Returns:
            True if insertion verified, False otherwise
        """
        try:
            # Small delay to let the insertion complete
            time.sleep(0.01)

            error_code, value_after = AXUIElementCopyAttributeValue(
                element, "AXValue", None
            )

            if error_code != kAXErrorSuccess:
                # Can't verify, but don't fail - some fields don't support AXValue
                logger.debug("Cannot verify insertion - AXValue not supported")
                return True

            # Check if value changed
            if value_before != value_after:
                # Value changed, likely successful
                return True

            # Value didn't change - likely false success
            logger.debug(
                f"Value unchanged after insertion (before: {value_before}, after: {value_after})"
            )
            return False

        except Exception as e:
            logger.debug(f"Exception during verification: {e}")
            # Can't verify, assume success to avoid false negatives
            return True

    def _insert_via_value(self, text: str) -> bool:
        """Insert text using kAXValue attribute.

        This method appends text to the existing value. Works with
        simple text fields but not rich text editors.

        Args:
            text: Text to insert

        Returns:
            True if successful, False otherwise
        """
        try:
            focused_element, error_code = self._get_focused_element()

            if error_code != kAXErrorSuccess:
                logger.debug(f"Cannot get focused element for value: {error_code}")
                return False

            # Get current value
            error_code, current_value = AXUIElementCopyAttributeValue(
                focused_element, "AXValue", None
            )

            if error_code == kAXErrorSuccess and current_value is not None:
                new_value = str(current_value) + text
            else:
                new_value = text

            # Set new value
            error_code = AXUIElementSetAttributeValue(
                focused_element, "AXValue", new_value
            )

            if error_code == kAXErrorSuccess:
                return True

            logger.debug(f"kAXValue insertion failed with error: {error_code}")
            return False

        except Exception as e:
            logger.debug(f"Exception in _insert_via_value: {e}")
            return False

    def _insert_via_clipboard_paste(self, text: str) -> bool:
        """Insert text by copying to clipboard and simulating Cmd+V.

        This is the most reliable method and works with all applications
        including web-based inputs (Chrome, Slack, etc.). Temporarily
        uses the clipboard but restores original contents.

        Args:
            text: Text to insert

        Returns:
            True if successful, False otherwise
        """
        try:
            pasteboard = NSPasteboard.generalPasteboard()

            # Save current clipboard contents
            old_contents = pasteboard.stringForType_(NSStringPboardType)

            # Set text to clipboard
            pasteboard.clearContents()
            success = pasteboard.setString_forType_(text, NSStringPboardType)

            if not success:
                logger.error("Failed to set clipboard contents")
                return False

            # Small delay to ensure clipboard is ready
            time.sleep(0.02)

            # Send Cmd+V keystroke
            self._send_paste_keystroke()

            # Wait for paste to complete
            time.sleep(0.05)

            # Restore original clipboard contents
            if old_contents:
                pasteboard.clearContents()
                pasteboard.setString_forType_(old_contents, NSStringPboardType)

            return True

        except Exception as e:
            logger.error(f"Clipboard paste failed: {e}")
            return False

    def _send_paste_keystroke(self):
        """Send Cmd+V keystroke to active application.

        Simulates pressing Command+V to trigger paste action.
        """
        # Create key down event with Command modifier
        key_down = CGEventCreateKeyboardEvent(None, V_KEY_CODE, True)
        CGEventSetFlags(key_down, kCGEventFlagMaskCommand)

        # Create key up event
        key_up = CGEventCreateKeyboardEvent(None, V_KEY_CODE, False)

        # Post events to system
        CGEventPost(kCGHIDEventTap, key_down)
        CGEventPost(kCGHIDEventTap, key_up)
