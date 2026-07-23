from __future__ import annotations

"""회원별 프로젝트 결과 저장소.

역할: 회원 ID 기준으로 업로드 원본·요약·번역·이지리드 산출물을 파일로 저장한다.
주요 기능: 저장(save_*), 조회(list/read/get_source_file).
"""

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from backend.config import DATA_DIR

_USER_STORAGE_DIR = DATA_DIR / "user_storage"


ArtifactKind = Literal["summary", "translation", "easyread"]

_ARTIFACT_META_KEY: dict[ArtifactKind, str] = {
    "summary": "summary_file",
    "translation": "translation_file",
    "easyread": "easyread_file",
}

_ARTIFACT_DEFAULT_FILE: dict[ArtifactKind, str] = {
    "summary": "summary.txt",
    "translation": "translation.txt",
    "easyread": "easyread.txt",
}

TRANSLATION_SEGMENTS_FILE = "translation_segments.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", value.strip())
    return cleaned or "unknown"


def _user_dir(user_id: str) -> Path:
    return _USER_STORAGE_DIR / _safe_segment(user_id)


def _project_dir(user_id: str, doc_id: str) -> Path:
    return _user_dir(user_id) / "projects" / _safe_segment(doc_id)


def resolve_project_dir(user_id: str, doc_id: str) -> Path | None:
    """doc_id(메타)와 폴더명이 어긋난 경우 프로젝트 디렉터리를 찾는다."""
    direct = _project_dir(user_id, doc_id)
    if direct.is_dir() and (direct / "metadata.json").is_file():
        return direct

    root = _user_dir(user_id) / "projects"
    if not root.is_dir():
        return None

    target = doc_id.strip()
    safe_target = _safe_segment(doc_id)
    for project_dir in root.iterdir():
        if not project_dir.is_dir():
            continue
        if project_dir.name == safe_target:
            return project_dir
        meta_path = project_dir / "metadata.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if str(meta.get("doc_id") or "") == target:
            return project_dir
    return None


def _project_has_artifact(project_dir: Path, meta: dict, kind: ArtifactKind) -> bool:
    meta_key = _ARTIFACT_META_KEY[kind]
    named = meta.get(meta_key)
    if isinstance(named, str) and named and (project_dir / named).is_file():
        return True
    return (project_dir / _ARTIFACT_DEFAULT_FILE[kind]).is_file()


def _meta_path(user_id: str, doc_id: str) -> Path:
    return _project_dir(user_id, doc_id) / "metadata.json"


def _load_meta(user_id: str, doc_id: str) -> dict:
    path = _meta_path(user_id, doc_id)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_meta(user_id: str, doc_id: str, payload: dict) -> None:
    path = _meta_path(user_id, doc_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _project_has_source(project_dir: Path, meta: dict) -> bool:
    source_file = meta.get("source_file")
    if isinstance(source_file, str) and source_file:
        if (project_dir / source_file).is_file():
            return True
    for candidate in project_dir.glob("source.*"):
        if candidate.is_file():
            return True
    return False


def _touch_meta(user_id: str, doc_id: str, *, filename: str | None = None) -> dict:
    meta = _load_meta(user_id, doc_id)
    now = _now_iso()
    if not meta.get("created_at"):
        meta["created_at"] = now
    meta["updated_at"] = now
    meta["doc_id"] = doc_id
    if filename:
        meta["filename"] = filename
    _save_meta(user_id, doc_id, meta)
    return meta


def save_source(user_id: str, doc_id: str, filename: str, content: bytes) -> None:
    project_dir = _project_dir(user_id, doc_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(filename).suffix.lower() or ".bin"
    source_name = f"source{ext}"
    source_path = project_dir / source_name
    source_path.write_bytes(content)

    meta = _touch_meta(user_id, doc_id, filename=filename)
    meta["source_file"] = source_name
    _save_meta(user_id, doc_id, meta)


def save_summary(user_id: str, doc_id: str, filename: str, summary: str) -> None:
    project_dir = _project_dir(user_id, doc_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "summary.txt").write_text(summary, encoding="utf-8")

    meta = _touch_meta(user_id, doc_id, filename=filename)
    meta["summary_file"] = "summary.txt"
    _save_meta(user_id, doc_id, meta)


def save_translation(user_id: str, doc_id: str, filename: str, translation: str) -> None:
    project_dir = _project_dir(user_id, doc_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "translation.txt").write_text(translation, encoding="utf-8")

    meta = _touch_meta(user_id, doc_id, filename=filename)
    meta["translation_file"] = "translation.txt"
    _save_meta(user_id, doc_id, meta)


def save_translation_segments(
    user_id: str,
    doc_id: str,
    filename: str,
    segments: list[dict],
) -> None:
    project_dir = _project_dir(user_id, doc_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / TRANSLATION_SEGMENTS_FILE).write_text(
        json.dumps(segments, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    meta = _touch_meta(user_id, doc_id, filename=filename)
    meta["translation_segments_file"] = TRANSLATION_SEGMENTS_FILE
    _save_meta(user_id, doc_id, meta)


def read_translation_segments(user_id: str, doc_id: str) -> list[dict] | None:
    project_dir = resolve_project_dir(user_id, doc_id)
    if not project_dir:
        return None

    meta_path = project_dir / "metadata.json"
    meta: dict = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            meta = {}

    candidates: list[str] = []
    named = meta.get("translation_segments_file")
    if isinstance(named, str) and named.strip():
        candidates.append(named.strip())
    if TRANSLATION_SEGMENTS_FILE not in candidates:
        candidates.append(TRANSLATION_SEGMENTS_FILE)

    for filename in candidates:
        path = project_dir / filename
        if not path.is_file():
            continue
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    return None


def save_easyread_text(user_id: str, doc_id: str, filename: str, content: str) -> None:
    project_dir = _project_dir(user_id, doc_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "easyread.txt").write_text(content, encoding="utf-8")

    meta = _touch_meta(user_id, doc_id, filename=filename)
    meta["easyread_file"] = "easyread.txt"
    _save_meta(user_id, doc_id, meta)


def save_easyread_docx(user_id: str, doc_id: str, filename: str, content: bytes) -> None:
    project_dir = _project_dir(user_id, doc_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "easyread.docx").write_bytes(content)

    meta = _touch_meta(user_id, doc_id, filename=filename)
    meta["easyread_docx_file"] = "easyread.docx"
    _save_meta(user_id, doc_id, meta)


def save_easyread_pdf(user_id: str, doc_id: str, filename: str, content: bytes) -> None:
    project_dir = _project_dir(user_id, doc_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "easyread.pdf").write_bytes(content)

    meta = _touch_meta(user_id, doc_id, filename=filename)
    meta["easyread_pdf_file"] = "easyread.pdf"
    _save_meta(user_id, doc_id, meta)


def list_user_projects(user_id: str) -> list[dict]:
    root = _user_dir(user_id) / "projects"
    if not root.is_dir():
        return []

    items: list[dict] = []
    for project_dir in root.iterdir():
        if not project_dir.is_dir():
            continue
        meta_path = project_dir / "metadata.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        items.append(
            {
                "doc_id": str(meta.get("doc_id") or project_dir.name),
                "filename": str(meta.get("filename") or "(이름 없음)"),
                "created_at": str(meta.get("created_at") or ""),
                "updated_at": str(meta.get("updated_at") or ""),
                "has_source": _project_has_source(project_dir, meta),
                "has_summary": _project_has_artifact(project_dir, meta, "summary"),
                "has_translation": _project_has_artifact(project_dir, meta, "translation"),
                "has_easyread_pdf": bool(meta.get("easyread_pdf_file")),
                "has_easyread": bool(
                    meta.get("easyread_file")
                    or meta.get("easyread_docx_file")
                    or meta.get("easyread_pdf_file")
                ),
            }
        )

    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return items


def read_artifact_text(user_id: str, doc_id: str, kind: ArtifactKind) -> str | None:
    project_dir = resolve_project_dir(user_id, doc_id)
    if not project_dir:
        return None

    meta_path = project_dir / "metadata.json"
    meta: dict = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            meta = {}

    meta_key = _ARTIFACT_META_KEY[kind]
    candidates: list[str] = []
    named = meta.get(meta_key)
    if isinstance(named, str) and named.strip():
        candidates.append(named.strip())
    default_name = _ARTIFACT_DEFAULT_FILE[kind]
    if default_name not in candidates:
        candidates.append(default_name)

    for filename in candidates:
        path = project_dir / filename
        if not path.is_file():
            continue
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            continue
    return None


def get_source_file(user_id: str, doc_id: str) -> tuple[Path, str] | None:
    meta = _load_meta(user_id, doc_id)
    filename = meta.get("filename")
    project_dir = _project_dir(user_id, doc_id)

    source_file = meta.get("source_file")
    if isinstance(source_file, str) and source_file:
        path = project_dir / source_file
        if path.is_file():
            download_name = str(filename) if isinstance(filename, str) and filename else path.name
            return path, download_name

    for candidate in sorted(project_dir.glob("source.*")):
        if candidate.is_file():
            download_name = str(filename) if isinstance(filename, str) and filename else candidate.name
            return candidate, download_name

    return None


def get_easyread_pdf_file(user_id: str, doc_id: str) -> tuple[Path, str] | None:
    meta = _load_meta(user_id, doc_id)
    pdf_file = meta.get("easyread_pdf_file")
    if not isinstance(pdf_file, str) or not pdf_file:
        return None

    path = _project_dir(user_id, doc_id) / pdf_file
    if not path.is_file():
        return None

    filename = meta.get("filename")
    stem = Path(str(filename)).stem if isinstance(filename, str) and filename else f"easyread_{doc_id[:8]}"
    download_name = f"{stem}_easyread.pdf"
    return path, download_name


def delete_user_project(user_id: str, doc_id: str) -> bool:
    project_dir = _project_dir(user_id, doc_id)
    if not project_dir.is_dir():
        return False
    shutil.rmtree(project_dir, ignore_errors=True)
    return True


def list_all_users_storage() -> list[dict]:
    """관리자용 — 계정(저장 폴더)별 프로젝트 목록."""
    if not _USER_STORAGE_DIR.is_dir():
        return []

    blocks: list[dict] = []
    for user_dir in sorted(_USER_STORAGE_DIR.iterdir(), key=lambda p: p.name.lower()):
        if not user_dir.is_dir():
            continue
        user_id = user_dir.name
        projects = list_user_projects(user_id)
        if not projects:
            continue
        blocks.append({"user_id": user_id, "projects": projects})

    blocks.sort(key=lambda block: block["user_id"].lower())
    return blocks
