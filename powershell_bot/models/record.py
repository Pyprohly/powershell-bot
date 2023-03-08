
from typing import Optional

from dataclasses import dataclass

@dataclass
class Record:
    id: int
    feature_flags: int
    recheck: bool
    target_submission_id: int
    target_submission_created_ut: int
    target_submission_author_name: str
    bot_comment_id: Optional[int]
