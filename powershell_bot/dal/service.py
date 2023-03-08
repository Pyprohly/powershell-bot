
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, AsyncIterable
if TYPE_CHECKING:
    import sqlalchemy.ext.asyncio
    from ..models.record import Record

import asyncio

from sqlalchemy import select, insert, update

from ..database_schema import record_table
from ..model_loaders.record import load_record


class Service:
    def __init__(self,
        *,
        engine: sqlalchemy.ext.asyncio.engine.AsyncEngine,
        haven: set[asyncio.Task[None]],
    ) -> None:
        self._engine: sqlalchemy.ext.asyncio.engine.AsyncEngine = engine
        self._haven: set[asyncio.Task[None]] = haven

    async def add_record(self,
        *,
        feature_flags: int,
        recheck: bool = True,
        target_submission_id: int,
        target_submission_created_ut: int,
        target_submission_author_name: str,
        bot_comment_id: Optional[int],
    ) -> None:
        record_data = {
            'feature_flags': feature_flags,
            'recheck': recheck,
            'target_submission_id': target_submission_id,
            'target_submission_created_ut': target_submission_created_ut,
            'target_submission_author_name': target_submission_author_name,
            'bot_comment_id': bot_comment_id,
        }

        async def coro_fn() -> None:
            async with self._engine.connect() as conn:
                await conn.execute(
                    insert(record_table),
                    record_data,
                )
                await conn.commit()

        task = asyncio.create_task(coro_fn())
        self._haven.add(task)
        task.add_done_callback(self._haven.remove)
        await asyncio.shield(task)

    async def produce_rechecking_records(self) -> AsyncIterable[Record]:
        async with self._engine.connect() as conn:
            result = await conn.execute(select(record_table).where(record_table.c.recheck))
            for row in result:
                yield load_record(row)

    async def deactivate_rechecking(self, record_id: int) -> None:
        async def coro_fn() -> None:
            async with self._engine.connect() as conn:
                await conn.execute(update(record_table).where(record_table.c.id == record_id), {'recheck': False})
                await conn.commit()

        task = asyncio.create_task(coro_fn())
        self._haven.add(task)
        task.add_done_callback(self._haven.remove)
        await asyncio.shield(task)

    async def set_bot_comment_id(self, record_id: int, bot_comment_id: int) -> None:
        async def coro_fn() -> None:
            async with self._engine.connect() as conn:
                await conn.execute(update(record_table).where(record_table.c.id == record_id), {'bot_comment_id': bot_comment_id})
                await conn.commit()

        task = asyncio.create_task(coro_fn())
        self._haven.add(task)
        task.add_done_callback(self._haven.remove)
        await asyncio.shield(task)

    async def set_feature_flags(self, record_id: int, feature_flags: int) -> None:
        async def coro_fn() -> None:
            async with self._engine.connect() as conn:
                await conn.execute(update(record_table).where(record_table.c.id == record_id), {'feature_flags': feature_flags})
                await conn.commit()

        task = asyncio.create_task(coro_fn())
        self._haven.add(task)
        task.add_done_callback(self._haven.remove)
        await asyncio.shield(task)

    async def get_record_by_submission_id(self, submission_id: int) -> Optional[Record]:
        async with self._engine.connect() as conn:
            result = await conn.execute(select(record_table).where(record_table.c.target_submission_id == submission_id))
            row = result.first()
            if row is None:
                return None
            return load_record(row)
