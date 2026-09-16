"""Full-text file search engine using SQLite FTS5."""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from sqlalchemy import text

from ..core.logger import get_logger
from ..database.connection import get_session, session_scope
from ..database.models import IndexedFileModel
from ..database.search import init_fts5, sanitize_fts5_query

if TYPE_CHECKING:
    from ..database.repository import DatabaseRepository

logger = get_logger("services.search")


class SearchEngineService:
    """Provides high-performance full-text search with faceted filtering."""

    def __init__(self, repo: Any, db_path: Optional[Path] = None):
        self.repo = repo
        self.db_path = db_path or getattr(repo, "db_path", None)
        init_fts5(self.db_path)


    def search_files(
        self,
        query_text: str = "",
        chat_id: Optional[int] = None,
        media_type: Optional[str] = None,
        extension: Optional[str] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sort_by: str = "date",
        sort_desc: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[IndexedFileModel], int]:
        """Execute full-text query using FTS5 or faceted relational filters.

        Returns:
            Tuple[List[IndexedFileModel], int]: (matched_files, total_matched_count)
        """
        fts_query = sanitize_fts5_query(query_text) if query_text else ""

        # If no full-text search term is provided, use standard relational query
        if not fts_query:
            files = self.repo.get_files(
                chat_id=chat_id,
                media_type=media_type,
                extension=extension,
                min_size=min_size,
                max_size=max_size,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_desc=sort_desc,
            )
            total = self.repo.get_files_count(
                chat_id=chat_id,
                media_type=media_type,
                extension=extension,
                min_size=min_size,
                max_size=max_size,
                start_date=start_date,
                end_date=end_date,
            )
            return files, total

        # Construct FTS5 JOIN query
        where_clauses = ["files_fts MATCH :fts_match"]
        params: Dict[str, Any] = {"fts_match": fts_query}

        if chat_id is not None:
            where_clauses.append("f.chat_id = :chat_id")
            params["chat_id"] = chat_id

        if media_type is not None:
            where_clauses.append("f.media_type = :media_type")
            params["media_type"] = media_type.upper()

        if extension:
            clean_ext = extension if extension.startswith(".") else f".{extension}"
            where_clauses.append("f.extension = :extension")
            params["extension"] = clean_ext.lower()

        if min_size is not None:
            where_clauses.append("f.file_size >= :min_size")
            params["min_size"] = min_size

        if max_size is not None:
            where_clauses.append("f.file_size <= :max_size")
            params["max_size"] = max_size

        if start_date is not None:
            where_clauses.append("f.message_date >= :start_date")
            params["start_date"] = start_date

        if end_date is not None:
            where_clauses.append("f.message_date <= :end_date")
            params["end_date"] = end_date

        where_sql = " AND ".join(where_clauses)

        # Sorting mapping
        sort_col = "f.message_date"
        if sort_by == "name":
            sort_col = "f.filename"
        elif sort_by == "size":
            sort_col = "f.file_size"

        order_dir = "DESC" if sort_desc else "ASC"

        # Count query
        count_sql = f"""
            SELECT COUNT(*)
            FROM indexed_files f
            JOIN files_fts ON f.id = files_fts.rowid
            WHERE {where_sql}
        """

        # Data query
        data_sql = f"""
            SELECT f.id
            FROM indexed_files f
            JOIN files_fts ON f.id = files_fts.rowid
            WHERE {where_sql}
            ORDER BY {sort_col} {order_dir}
            LIMIT :limit OFFSET :offset
        """
        params["limit"] = limit
        params["offset"] = offset

        session = get_session(self.db_path)
        try:
            total_count = session.execute(text(count_sql), params).scalar() or 0
            id_rows = session.execute(text(data_sql), params).fetchall()
            matched_ids = [r[0] for r in id_rows]

            if not matched_ids:
                return [], total_count

            # Retrieve complete ORM models preserving order
            models = (
                session.query(IndexedFileModel)
                .filter(IndexedFileModel.id.in_(matched_ids))
                .all()
            )
            # Reorder to match query ranking/sort order
            id_to_model = {m.id: m for m in models}
            ordered_models = [id_to_model[i] for i in matched_ids if i in id_to_model]

            return ordered_models, total_count
        finally:
            session.close()
