"""Start the Stella Textual interface."""

from ..core import ChatSession, Settings
from .app import StellaTUI


def main() -> None:
    settings = Settings.load()
    StellaTUI(ChatSession(settings)).run()


if __name__ == "__main__":
    main()