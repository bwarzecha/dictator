"""Entry point for Dictator application.

Launches the menubar app.
"""

from dictator.app import DictatorApp


def main():
    """Start the Dictator application."""
    app = DictatorApp()
    app.run()


if __name__ == "__main__":
    main()
