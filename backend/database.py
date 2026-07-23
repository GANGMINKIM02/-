"""문서 영속화 계층 (SQLite + JSON 백업).

역할: 업로드된 판결문의 메타·페이지·요약·번역 데이터를 저장·조회·갱신한다.
주요 기능: documents 테이블 CRUD, Vercel 등 DB 유실 시 JSON 백업 복구.
관계: models/schemas(타입), config(DB_PATH), routers/documents(호출).
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from backend.config import DB_PATH, DATA_DIR
from backend.models.schemas import (
    ChecklistReport,
    DocumentResponse,
    DocType,
    TranslationSegment,
)

# --- JSON 백업 헬퍼 ---


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _backup_path(doc_id: str) -> Path:
    return DATA_DIR / "docs" / f"{doc_id}.json"


def _write_backup(doc: DocumentResponse, pages: list[str]) -> None:
    path = _backup_path(doc.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = doc.model_dump()
    payload["pages"] = pages
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _read_backup(doc_id: str) -> tuple[DocumentResponse, list[str]] | None:
    path = _backup_path(doc_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        pages = payload.pop("pages", [])
        return DocumentResponse(**payload), pages
    except (json.JSONDecodeError, TypeError, ValueError):
        return None

# --- DB 초기화 ---


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                stage TEXT NOT NULL,
                page_count INTEGER NOT NULL,
                pages_json TEXT NOT NULL,
                full_text TEXT NOT NULL,
                summary TEXT,
                translation_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await db.commit()

# --- 문서 CRUD ---


async def create_document(
    filename: str,
    doc_type: DocType,
    pages: list[str],
    full_text: str,
) -> str:
    doc_id = str(uuid.uuid4())
    now = _now()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO documents
            (id, filename, doc_type, stage, page_count, pages_json, full_text,
             summary, translation_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
            """,
            (
                doc_id,
                filename,
                doc_type,
                "uploaded",
                len(pages),
                json.dumps(pages, ensure_ascii=False),
                full_text,
                now,
                now,
            ),
        )
        await db.commit()
    doc = DocumentResponse(
        id=doc_id,
        filename=filename,
        doc_type=doc_type,
        stage="uploaded",
        page_count=len(pages),
        full_text=full_text,
        summary=None,
        translation_segments=[],
        translation_text=None,
        checklist=None,
    )
    _write_backup(doc, pages)
    return doc_id


async def get_document(doc_id: str) -> DocumentResponse | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)) as cursor:
            row = await cursor.fetchone()
    if not row:
        backup = _read_backup(doc_id)
        return backup[0] if backup else None

    segments: list[TranslationSegment] = []
    translation_text = None
    checklist = None
    if row["translation_json"]:
        payload = json.loads(row["translation_json"])
        segments = [TranslationSegment(**s) for s in payload.get("segments", [])]
        translation_text = payload.get("text")
        if payload.get("checklist"):
            checklist = ChecklistReport(**payload["checklist"])

    return DocumentResponse(
        id=row["id"],
        filename=row["filename"],
        doc_type=row["doc_type"],
        stage=row["stage"],
        page_count=row["page_count"],
        full_text=row["full_text"],
        summary=row["summary"],
        translation_segments=segments,
        translation_text=translation_text,
        checklist=checklist,
    )


async def ensure_document(
    doc_id: str,
    *,
    filename: str,
    doc_type: DocType,
    pages: list[str],
    full_text: str,
) -> None:
    existing = await get_document(doc_id)
    if existing:
        return
    now = _now()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO documents
            (id, filename, doc_type, stage, page_count, pages_json, full_text,
             summary, translation_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
            """,
            (
                doc_id,
                filename,
                doc_type,
                "uploaded",
                len(pages),
                json.dumps(pages, ensure_ascii=False),
                full_text,
                now,
                now,
            ),
        )
        await db.commit()
    _write_backup(
        DocumentResponse(
            id=doc_id,
            filename=filename,
            doc_type=doc_type,
            stage="uploaded",
            page_count=len(pages),
            full_text=full_text,
        ),
        pages,
    )


async def get_page(doc_id: str, page_num: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT pages_json FROM documents WHERE id = ?", (doc_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if row:
        pages = json.loads(row["pages_json"])
        if 1 <= page_num <= len(pages):
            return pages[page_num - 1]

    backup = _read_backup(doc_id)
    if backup:
        _, pages = backup
        if 1 <= page_num <= len(pages):
            return pages[page_num - 1]
    return None

# --- 요약·번역 갱신 ---


async def update_summary(doc_id: str, summary: str) -> None:
    doc = await get_document(doc_id)
    if not doc:
        return
    now = _now()
    backup = _read_backup(doc_id)
    pages = backup[1] if backup else ([doc.full_text] if doc.full_text else [])
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE documents SET summary = ?, stage = ?, updated_at = ? WHERE id = ?
            """,
            (summary, "summarized", now, doc_id),
        )
        if cursor.rowcount == 0:
            await db.execute(
                """
                INSERT INTO documents
                (id, filename, doc_type, stage, page_count, pages_json, full_text,
                 summary, translation_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    doc_id,
                    doc.filename,
                    doc.doc_type,
                    "summarized",
                    doc.page_count,
                    json.dumps(pages, ensure_ascii=False),
                    doc.full_text,
                    summary,
                    now,
                    now,
                ),
            )
        await db.commit()
    _write_backup(
        DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            doc_type=doc.doc_type,
            stage="summarized",
            page_count=doc.page_count,
            full_text=doc.full_text,
            summary=summary,
            translation_segments=doc.translation_segments,
            translation_text=doc.translation_text,
            checklist=doc.checklist,
        ),
        pages,
    )


async def update_translation(
    doc_id: str,
    segments: list[TranslationSegment],
    text: str,
    checklist: ChecklistReport | None = None,
) -> None:
    now = _now()
    payload: dict = {
        "segments": [s.model_dump() for s in segments],
        "text": text,
    }
    if checklist:
        payload["checklist"] = checklist.model_dump()
    payload_json = json.dumps(payload, ensure_ascii=False)

    doc = await get_document(doc_id)
    backup = _read_backup(doc_id)
    pages = backup[1] if backup else ([doc.full_text] if doc and doc.full_text else [])

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE documents SET translation_json = ?, stage = ?, updated_at = ? WHERE id = ?
            """,
            (payload_json, "translated", now, doc_id),
        )
        if cursor.rowcount == 0 and doc:
            await db.execute(
                """
                INSERT INTO documents
                (id, filename, doc_type, stage, page_count, pages_json, full_text,
                 summary, translation_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    doc.filename,
                    doc.doc_type,
                    "translated",
                    doc.page_count,
                    json.dumps(pages, ensure_ascii=False),
                    doc.full_text,
                    doc.summary,
                    payload_json,
                    now,
                    now,
                ),
            )
        await db.commit()

    if doc:
        _write_backup(
            DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                doc_type=doc.doc_type,
                stage="translated",
                page_count=doc.page_count,
                full_text=doc.full_text,
                summary=doc.summary,
                translation_segments=segments,
                translation_text=text,
                checklist=checklist or doc.checklist,
            ),
            pages,
        )


async def get_doc_type(doc_id: str) -> DocType | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT doc_type FROM documents WHERE id = ?", (doc_id,)) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else None


async def update_doc_type(doc_id: str, doc_type: DocType) -> None:
    doc = await get_document(doc_id)
    if not doc:
        return
    now = _now()
    backup = _read_backup(doc_id)
    pages = backup[1] if backup else ([doc.full_text] if doc.full_text else [])
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE documents SET doc_type = ?, updated_at = ? WHERE id = ?",
            (doc_type, now, doc_id),
        )
        if cursor.rowcount == 0:
            await db.execute(
                """
                INSERT INTO documents
                (id, filename, doc_type, stage, page_count, pages_json, full_text,
                 summary, translation_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    doc_id,
                    doc.filename,
                    doc_type,
                    doc.stage,
                    doc.page_count,
                    json.dumps(pages, ensure_ascii=False),
                    doc.full_text,
                    doc.summary,
                    now,
                    now,
                ),
            )
        await db.commit()
    _write_backup(
        doc.model_copy(update={"doc_type": doc_type}),
        pages,
    )
