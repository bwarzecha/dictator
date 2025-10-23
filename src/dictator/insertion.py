"""Text insertion into focused application.

Uses macOS Accessibility API to insert text at cursor position.
"""

import logging
from AppKit import NSWorkspace
from ApplicationServices import (
    AXUIElementCreateSystemWide,
    AXUIElementCopyAttributeValue,
    AXUIElementSetAttributeValue,
    kAXErrorSuccess,
    kAXErrorAPIDisabled,
    kAXErrorNotImplemented,
    kAXErrorInvalidUIElement,
)

logger = logging.getLogger(__name__)

ERROR_MESSAGES = {
    kAXErrorAPIDisabled: "Accessibility API is disabled. Grant accessibility permissions in System Settings.",
    kAXErrorNotImplemented: "Focused element doesn't support text insertion",
    kAXErrorInvalidUIElement: "No valid UI element is focused",
}


class TextInserter:
    """Inserts text into the currently focused application.

    Uses macOS NSAccessibility API via PyObjC.
    """

    def insert_text(self, text: str) -> bool:
        """Insert text at current cursor position.

        Args:
            text: Text to insert

        Returns:
            True if insertion successful, False otherwise
        """
        try:
            system_wide = AXUIElementCreateSystemWide()

            error_code, focused_app = AXUIElementCopyAttributeValue(
                system_wide, "AXFocusedApplication", None
            )

            if error_code != kAXErrorSuccess:
                error_msg = ERROR_MESSAGES.get(
                    error_code,
                    f"Could not get focused application (error code: {error_code})"
                )
                logger.warning(error_msg)
                return False

            error_code, focused_element = AXUIElementCopyAttributeValue(
                focused_app, "AXFocusedUIElement", None
            )

            if error_code != kAXErrorSuccess:
                error_msg = ERROR_MESSAGES.get(
                    error_code,
                    f"Could not get focused UI element (error code: {error_code})"
                )
                logger.warning(error_msg)
                return False

            error_code, current_value = AXUIElementCopyAttributeValue(
                focused_element, "AXValue", None
            )

            if error_code == kAXErrorSuccess and current_value is not None:
                new_value = str(current_value) + text
            else:
                new_value = text

            error_code = AXUIElementSetAttributeValue(
                focused_element, "AXValue", new_value
            )

            if error_code != kAXErrorSuccess:
                error_msg = ERROR_MESSAGES.get(
                    error_code,
                    f"Failed to set text value (error code: {error_code})"
                )
                logger.warning(error_msg)
                return False

            logger.info(
                "Text inserted successfully",
                extra={"text_length": len(text)},
            )
            return True

        except Exception as e:
            logger.error(f"Error inserting text: {e}")
            return False
