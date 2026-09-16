"""SQLite FTS5 Full-Text Search integration and query builder."""

import re
import sqlite3
from typing import Any, List, Optional, Tuple
from sqlalchemy import text

from .connection import get_session, session_scope
from ..core.logger import get_logger

logger = get_logger("database.search")


def init_fts5(db_path) -> None:
    """Initialize SQLite FTS5 virtual table and synchronization triggers."""
    with session_scope(db_path) as session:
        # Create FTS5 virtual table indexing filename, caption, chat_title, and extension
        session.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                    filename,
                    caption,
                    chat_title,
                    extension,
                    content='indexed_files',
                    content_rowid='id',
                    tokenize='unicode61 remove_diacritics 2'
                );
                """
            )
        )

        # Triggers to keep FTS5 synchronized with indexed_files table
        session.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON indexed_files BEGIN
                    INSERT INTO files_fts(rowid, filename, caption, chat_title, extension)
                    VALUES (new.id, new.filename, new.caption, new.chat_title, new.extension);
                END;
                """
            )
        )

        session.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON indexed_files BEGIN
                    INSERT INTO files_fts(files_fts, rowid, filename, caption, chat_title, extension)
                    VALUES('delete', old.id, old.filename, old.caption, old.chat_title, old.extension);
                END;
                """
            )
        )

        session.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS files_au AFTER UPDATE ON indexed_files BEGIN
                    INSERT INTO files_fts(files_fts, rowid, filename, caption, chat_title, extension)
                    VALUES('delete', old.id, old.filename, old.caption, old.chat_title, old.extension);
                    INSERT INTO files_fts(rowid, filename, caption, chat_title, extension)
                    VALUES (new.id, new.filename, new.caption, new.chat_title, new.extension);
                END;
                """
            )
        )

        # Populate FTS5 table if it's currently empty but files exist
        session.execute(
            text(
                """
                INSERT INTO files_fts(files_fts) VALUES('rebuild');
                """
            )
        )
        logger.info("FTS5 full-text search table and triggers successfully initialized.")


def sanitize_fts5_query(raw_query: str) -> str:
    """Sanitize user input into a safe FTS5 prefix-matching query string."""
    if not raw_query:
        return ""

    # Remove FTS5 operator keywords and special punctuation that cause syntax errors
    cleaned = re.sub(r'["\*\+\-\^\:\(\)\{\}\~]', ' ', raw_query)
    tokens = [t.strip() for t in cleaned.split() if t.strip() and t.upper() not in ("AND", "OR", "NOT", "NEAR")]

    if not tokens:
        return ""

    # Append prefix wildcard * to each token for partial matching (e.g. 'doc*' matches 'document')
    formatted = " ".join(f'"{t}"*' for t in tokens)
    return formatted
