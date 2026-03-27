"""Operational entrypoints for local setup."""

from __future__ import annotations

from .config import load_settings
from .database import initialize_database, session_scope
from .persistence import bootstrap_defaults


def init_database_main() -> None:
    initialize_database()
    settings = load_settings()
    with session_scope() as session:
        bootstrap_defaults(session, settings)
    print("Database ready.")


if __name__ == "__main__":
    init_database_main()
