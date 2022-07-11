
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.ext.asyncio.engine import AsyncEngine

from sqlalchemy.schema import MetaData, Table, Column
from sqlalchemy.types import SmallInteger, BigInteger, String, Boolean

metadata = MetaData()

record_table = Table(
    'record',
    metadata,
    Column('id', BigInteger, primary_key=True, nullable=False),
    Column('feature_flags', SmallInteger, nullable=False),
    Column('recheck', Boolean, nullable=False),
    Column('target_submission_id', BigInteger, nullable=False),
    Column('target_submission_created_ut', BigInteger, nullable=False),
    Column('target_submission_author_name', String(24), nullable=False),
    Column('bot_comment_id', BigInteger, nullable=True),
)

def create_database(engine: Engine) -> None:
    metadata.create_all(engine)

async def create_database_async(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.run_sync(metadata.create_all)
        await conn.commit()
