
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import sqlalchemy.engine.row

from ..models.record import Record

def load_record(row: sqlalchemy.engine.row.Row) -> Record:
    return Record(
        id=row.id,
        feature_flags=row.feature_flags,
        recheck=row.recheck,
        target_submission_id=row.target_submission_id,
        target_submission_created_ut=row.target_submission_created_ut,
        target_submission_author_name=row.target_submission_author_name,
        bot_comment_id=row.bot_comment_id,
    )
