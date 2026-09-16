"""SQLAlchemy connection management and session factory."""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger("database.connection")

Base = declarative_base()

_ENGINE = None
_SESSION_FACTORY = None


def get_engine(db_path: Optional[Path] = None):
    """Create or retrieve singleton SQLAlchemy SQLite engine with optimizations."""
    global _ENGINE, _SESSION_FACTORY
    target_path = db_path or settings.database_path

    if _ENGINE is None or (db_path is not None and str(_ENGINE.url) != f"sqlite:///{target_path}"):
        target_path.parent.mkdir(parents=True, exist_ok=True)
        db_uri = f"sqlite:///{target_path}"
        logger.info("Initializing SQLAlchemy engine at: %s", db_uri)

        engine = create_engine(
            db_uri,
            connect_args={"timeout": 30.0, "check_same_thread": False},
            echo=False,
            future=True,
        )

        # Set SQLite pragmas for foreign keys and WAL mode
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.close()

        _ENGINE = engine
        _SESSION_FACTORY = sessionmaker(bind=_ENGINE, expire_on_commit=False, future=True)

    return _ENGINE


def get_session(db_path: Optional[Path] = None) -> Session:
    """Return a new SQLAlchemy Session."""
    get_engine(db_path)
    return _SESSION_FACTORY()


@contextmanager
def session_scope(db_path: Optional[Path] = None) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = get_session(db_path)
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error("Session rollback due to error: %s", e)
        raise
    finally:
        session.close()


def init_db(db_path: Optional[Path] = None) -> None:
    """Create all defined tables and indexes if they do not exist."""
    engine = get_engine(db_path)
    Base.metadata.create_all(bind=engine)
    logger.info("SQLAlchemy database metadata initialized successfully.")
