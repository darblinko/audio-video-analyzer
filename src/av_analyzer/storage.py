"""SQLite storage for analysis runs."""

import json
from pathlib import Path
from typing import Any

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    media_type TEXT NOT NULL,
    upload_timestamp TEXT NOT NULL,
    audio_features TEXT,
    video_analysis TEXT,
    status TEXT NOT NULL,
    error_message TEXT
)
"""
_JSON_COLUMNS = ("audio_features", "video_analysis")


def _decode(row: aiosqlite.Row) -> dict[str, Any]:
    record = dict(row)
    for column in _JSON_COLUMNS:
        if record[column]:
            record[column] = json.loads(record[column])
    return record


def _encode(value: dict[str, Any] | None) -> str | None:
    return json.dumps(value) if value is not None else None


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(_SCHEMA)
            await db.commit()

    async def create(
        self, analysis_id: str, filename: str, media_type: str, timestamp: str
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO analyses (id, filename, media_type, upload_timestamp, status) "
                "VALUES (?, ?, ?, ?, 'processing')",
                (analysis_id, filename, media_type, timestamp),
            )
            await db.commit()

    async def complete(
        self,
        analysis_id: str,
        audio_features: dict[str, Any],
        video_analysis: dict[str, Any] | None,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE analyses SET audio_features = ?, video_analysis = ?, status = 'completed' "
                "WHERE id = ?",
                (_encode(audio_features), _encode(video_analysis), analysis_id),
            )
            await db.commit()

    async def fail(self, analysis_id: str, error_message: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE analyses SET status = 'failed', error_message = ? WHERE id = ?",
                (error_message, analysis_id),
            )
            await db.commit()

    async def list(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM analyses ORDER BY upload_timestamp DESC"
            ) as cursor:
                return [_decode(row) for row in await cursor.fetchall()]

    async def get(self, analysis_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)) as cursor:
                row = await cursor.fetchone()
                return _decode(row) if row else None
