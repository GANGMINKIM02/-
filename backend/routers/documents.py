from __future__ import annotations

"""문서 API 라우터.

역할: /api/documents 하위 REST 엔드포인트를 제공한다.
주요 기능: 업로드(OCR), 조회, 요약·번역·체크리스트, 이미지 배치, Word 내보내기.
관계: database(저장), services(upstage·translator·word_export 등), models/schemas(요청·응답).
"""

import mimetypes
import re
import uuid
import base64
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response

from backend.config import UPLOAD_DIR, settings
from backend.database import (
    create_document,
    ensure_document,
    get_document,
    get_doc_type,
    get_page,
    update_doc_type,
    update_summary,
    update_translation,
)
from backend.models.schemas import (
    ChecklistReport,
    DocTypeUpdate,
    DocumentResponse,
    DocumentEnsureRequest,
    DetectPlacementsRequest,
    ExportRequest,
    ImageCatalogItem,
    ImagePlacement,
    ArtifactTextResponse,
    RefineRequest,
    SummarizeRequest,
    SummaryUpdate,
    TranslationUpdate,
    TranslationSegment,
    UserProjectItem,
    AdminStorageOverview,
    AdminUserStorageBlock,
    UploadResponse,
)
from backend.services.image_matcher import (
    detect_image_placements,
    fill_missing_item_placements_async,
    list_image_catalog,
)
from backend.services.image_web_search import search_web_images
from backend.services.easy_read_sanitize import extract_refined_translation
from backend.services import parser, prompts, translator, upstage, word_export, pdf_export, user_storage

router = APIRouter(prefix="/documents", tags=["documents"])

# --- 헬퍼: 원본 파일 경로 ---


def _source_path(doc_id: str, filename: str) -> Path:
    ext = Path(filename).suffix.lower() or ".bin"
    return UPLOAD_DIR / f"{doc_id}_source{ext}"


def _full_text_sufficient_for_summary(full_text: str | None) -> bool:
    if not full_text or not full_text.strip():
        return False
    degraded = full_text.replace("추출된 텍스트 없음", "").replace("(페이지", "")
    compact = re.sub(r"\s+", "", degraded)
    return len(compact) >= 180


async def _backfill_user_source_if_missing(user_id: str, doc_id: str) -> None:
    if user_storage.get_source_file(user_id, doc_id):
        return
    doc = await get_document(doc_id)
    if not doc:
        return
    path = _source_path(doc_id, doc.filename)
    if path.is_file():
        user_storage.save_source(user_id, doc_id, doc.filename, path.read_bytes())


def _segments_to_storage(segments: list[TranslationSegment]) -> list[dict]:
    return [segment.model_dump(mode="json") for segment in segments]


async def _persist_user_translation(
    user_id: str | None,
    doc_id: str,
    doc: DocumentResponse | None,
) -> None:
    if not user_id or not doc:
        return
    filename = doc.filename
    if doc.translation_text:
        user_storage.save_translation(user_id, doc_id, filename, doc.translation_text)
        user_storage.save_easyread_text(user_id, doc_id, filename, doc.translation_text)
    if doc.translation_segments:
        user_storage.save_translation_segments(
            user_id,
            doc_id,
            filename,
            _segments_to_storage(doc.translation_segments),
        )
    await _backfill_user_source_if_missing(user_id, doc_id)


async def _project_has_global_source(doc_id: str) -> bool:
    doc = await get_document(doc_id)
    if not doc:
        return False
    return _source_path(doc_id, doc.filename).is_file()


def _file_response_inline(path: Path, filename: str) -> FileResponse:
    media_type, _ = mimetypes.guess_type(filename)
    return FileResponse(
        path=path,
        media_type=media_type or "application/octet-stream",
        filename=filename,
        content_disposition_type="inline",
    )

# --- 요약 텍스트 정규화·교정 ---


_ITEM_START_RE = re.compile(
    r"^(?:<[^>]{1,60}>|\(\d+\)|\d+[.)]|[①②③④⑤⑥⑦⑧⑨⑩]|[가-힣]\.|[-*•·])\s*"
)

_PAGE_NUMBER_RE = re.compile(r"^\s*-\s*\d+\s*-\s*$")

_SUMMARY_HEADING_ALIASES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^(?:1[.)]\s*)?<*\s*먼저,?\s*법원의\s*판단을\s*알려드립니다\s*>*$"), "<먼저, 법원의 판단을 알려드립니다>"),
    (re.compile(r"^(?:2[.)]\s*)?<*\s*어떤\s*일이\s*있었나요\??\s*>*$"), "<어떤 일이 있었나요?>"),
    (re.compile(r"^(?:3[.)]\s*)?<*\s*법원이\s*판단한\s*문제는\s*무엇인가요\??\s*>*$"), "<법원이 판단한 문제는 무엇인가요?>"),
    (re.compile(r"^(?:4[.)]\s*)?<*\s*법원은\s*어떻게\s*판단했나요\??\s*>*$"), "<법원은 어떻게 판단했나요?>"),
    (re.compile(r"^(?:5[.)]\s*)?<*\s*최종\s*결과는\s*무엇인가요\??\s*>*$"), "<최종 결과는 무엇인가요?>"),
]

_TRUNCATED_END_RE = re.compile(r"[,:;\-\(\[\{]$|(?:및|또는|등)$")


def _canonicalize_summary_heading(line: str) -> str | None:
    target = line.strip()
    for pattern, canonical in _SUMMARY_HEADING_ALIASES:
        if pattern.match(target):
            return canonical
    return None


def _standardize_summary_sections(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        canonical = _canonicalize_summary_heading(stripped)
        if canonical:
            if out and out[-1] != "":
                out.append("")
            out.append(canonical)
            continue
        out.append(raw.rstrip())
    return "\n".join(out)


def _enforce_item_paragraphs(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    prev_nonblank = ""

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            if out and out[-1] != "":
                out.append("")
            continue

        if _PAGE_NUMBER_RE.match(stripped):
            continue

        is_item_start = bool(_ITEM_START_RE.match(stripped))
        if out and out[-1] != "" and is_item_start and prev_nonblank:
            out.append("")

        out.append(stripped)
        prev_nonblank = stripped

    return "\n".join(out).strip()


def _normalize_summary_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = _standardize_summary_sections(cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = _enforce_item_paragraphs(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _count_canonical_headings(text: str) -> int:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    count = 0
    for line in lines:
        if _canonicalize_summary_heading(line):
            count += 1
    return count


def _looks_truncated_summary(base: str, candidate: str) -> bool:
    if not candidate:
        return True

    if len(candidate) < max(240, int(len(base) * 0.65)):
        return True

    base_headings = _count_canonical_headings(base)
    cand_headings = _count_canonical_headings(candidate)
    if base_headings >= 3 and cand_headings < max(1, base_headings - 1):
        return True

    tail = candidate.strip()
    if _TRUNCATED_END_RE.search(tail):
        return True

    return False


async def _polish_summary_text(text: str) -> str:
    base = _normalize_summary_text(text)
    if not base:
        return base
    if settings.use_mock:
        return base

    system = (
        "당신은 한국어 교정 편집자입니다. 문서의 의미·사실관계는 절대 바꾸지 말고, "
        "맞춤법/띄어쓰기/문장부호를 교정하고 문단 구분만 읽기 쉽게 정리하세요."
    )
    user = (
        "아래 요약문을 교정하세요.\n"
        "- 원래 의미·결론·수치·고유명사는 변경 금지\n"
        "- 맞춤법, 띄어쓰기, 문장부호만 교정\n"
        "- 문단은 주제 전환마다 줄바꿈하여 읽기 쉽게 정리\n"
        "- 제목, 주석, 설명 문구를 추가하지 말고 교정된 본문만 출력\n\n"
        f"{base}"
    )
    try:
        polished = await upstage.chat_completion(system, user, max_tokens=5000)
    except Exception:
        return base
    polished = _normalize_summary_text(polished)
    if _looks_truncated_summary(base, polished):
        return base
    return polished or base

# --- Word 내보내기 헬퍼 ---


def _doc_for_export(doc_id: str, doc: DocumentResponse | None, body: ExportRequest | None) -> DocumentResponse | None:
    if body and body.segments:
        text = body.translation_text or "\n\n".join(
            s.easy_text for s in body.segments if s.easy_text
        )
        if doc:
            return doc.model_copy(
                update={
                    "summary": body.summary if body.summary is not None else doc.summary,
                    "translation_segments": body.segments,
                    "translation_text": text,
                    "stage": "translated",
                }
            )
        return DocumentResponse(
            id=doc_id,
            filename=body.filename or "document.pdf",
            doc_type=body.doc_type or "unknown",
            stage="translated",
            page_count=len(body.pages or []),
            full_text=body.full_text or "",
            summary=body.summary,
            translation_segments=body.segments,
            translation_text=text,
        )
    return doc


async def _resolve_document(doc_id: str, body: ExportRequest | None) -> DocumentResponse | None:
    doc = await get_document(doc_id)
    if doc:
        return doc
    if body and body.full_text:
        pages = body.pages or [body.full_text]
        await ensure_document(
            doc_id,
            filename=body.filename or "upload.pdf",
            doc_type=body.doc_type or "unknown",
            pages=pages,
            full_text=body.full_text,
        )
        return await get_document(doc_id)
    return None


async def _ensure_doc_from_request(
    doc_id: str,
    body: DocumentEnsureRequest | None,
) -> DocumentResponse:
    doc = await get_document(doc_id)
    if doc:
        return doc
    if not body or not body.full_text:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    pages = body.pages or [body.full_text]
    await ensure_document(
        doc_id,
        filename=body.filename or "upload.pdf",
        doc_type=body.doc_type or "unknown",
        pages=pages,
        full_text=body.full_text,
    )
    if body.summary is not None and body.summary.strip():
        await update_summary(doc_id, body.summary)
    doc = await get_document(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 복구하지 못했습니다.")
    return doc


def _require_user_id(x_user_id: str | None, user_id_query: str | None = None) -> str:
    user_id = (x_user_id or user_id_query or "").strip()
    if not user_id:
        raise HTTPException(401, "로그인 사용자가 필요합니다.")
    return user_id


def _admin_email_set() -> set[str]:
    raw = settings.admin_emails or ""
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _require_admin(x_user_id: str | None) -> str:
    user_id = _require_user_id(x_user_id, None)
    allowed = _admin_email_set()
    if not allowed:
        raise HTTPException(503, "관리자 기능이 설정되지 않았습니다.")
    if user_id.lower() not in allowed:
        raise HTTPException(403, "관리자만 접근할 수 있습니다.")
    return user_id


# --- 업로드·조회 ---


@router.get("/catalog/images", response_model=list[ImageCatalogItem])
async def image_catalog(q: str = Query("")) -> list[ImageCatalogItem]:
    return [ImageCatalogItem(**item) for item in list_image_catalog(q)]


@router.get("/catalog/images/web", response_model=list[ImageCatalogItem])
async def image_catalog_web(q: str = Query(..., min_length=1)) -> list[ImageCatalogItem]:
    """AI 프롬프트 기반 웹 이미지 검색 (그림 탭)."""
    items = await search_web_images(q)
    return [ImageCatalogItem(**item) for item in items]


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(400, "파일명이 없습니다.")

    ext = Path(file.filename).suffix.lower()
    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".doc", ".docx", ".hwp", ".hwpx"}
    if ext not in allowed:
        raise HTTPException(400, f"지원하지 않는 형식: {ext}")

    content = await file.read()
    save_path = UPLOAD_DIR / f"{uuid.uuid4()}{ext}"
    save_path.write_bytes(content)

    try:
        pages, full_text = await upstage.extract_text_from_file(save_path, file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    doc_type = parser.classify_doc_type(full_text)

    doc_id = await create_document(file.filename, doc_type, pages, full_text)
    _source_path(doc_id, file.filename).write_bytes(content)
    if x_user_id:
        user_storage.save_source(x_user_id, doc_id, file.filename, content)
    return UploadResponse(
        id=doc_id,
        filename=file.filename,
        doc_type=doc_type,
        page_count=len(pages),
        message="업로드 및 OCR 완료",
        pages=pages,
        full_text=full_text,
    )


@router.get("/user-projects", response_model=list[UserProjectItem])
async def list_user_projects(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    user_id: str | None = Query(default=None),
) -> list[UserProjectItem]:
    resolved = _require_user_id(x_user_id, user_id)
    items: list[UserProjectItem] = []
    for raw in user_storage.list_user_projects(resolved):
        data = dict(raw)
        doc_id = str(data["doc_id"])
        if not data.get("has_source"):
            if user_storage.get_source_file(resolved, doc_id):
                data["has_source"] = True
            elif await _project_has_global_source(doc_id):
                data["has_source"] = True
        doc = await get_document(doc_id)
        if doc:
            if not data.get("has_summary") and doc.summary and doc.summary.strip():
                data["has_summary"] = True
            if not data.get("has_translation") and doc.translation_text and doc.translation_text.strip():
                data["has_translation"] = True
            if not data.get("has_translation") and doc.translation_segments:
                data["has_translation"] = True
        if not data.get("has_translation") and user_storage.read_translation_segments(resolved, doc_id):
            data["has_translation"] = True
        items.append(UserProjectItem(**data))
    return items


@router.get("/user-projects/{doc_id}/artifact/{kind}", response_model=ArtifactTextResponse)
async def open_user_project_artifact(
    doc_id: str,
    kind: Literal["summary", "translation", "easyread"],
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    user_id: str | None = Query(default=None),
) -> ArtifactTextResponse:
    resolved = _require_user_id(x_user_id, user_id)
    text = user_storage.read_artifact_text(resolved, doc_id, kind)
    if text is None:
        doc = await get_document(doc_id)
        if doc:
            if kind == "summary" and doc.summary and doc.summary.strip():
                text = doc.summary.strip()
            elif kind == "translation" and doc.translation_text and doc.translation_text.strip():
                text = doc.translation_text.strip()
            elif kind == "easyread":
                fallback = (doc.translation_text or doc.summary or "").strip()
                if fallback:
                    text = fallback
    if text is None:
        raise HTTPException(404, "저장된 파일을 찾을 수 없습니다.")
    return ArtifactTextResponse(content=text)


@router.get(
    "/user-projects/{doc_id}/translation-segments",
    response_model=list[TranslationSegment],
)
async def open_user_project_translation_segments(
    doc_id: str,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    user_id: str | None = Query(default=None),
) -> list[TranslationSegment]:
    resolved = _require_user_id(x_user_id, user_id)
    raw = user_storage.read_translation_segments(resolved, doc_id)
    if raw:
        return [TranslationSegment(**item) for item in raw]

    doc = await get_document(doc_id)
    if doc and doc.translation_segments:
        segments = doc.translation_segments
        await _persist_user_translation(resolved, doc_id, doc)
        return segments

    raise HTTPException(404, "저장된 번역 세그먼트를 찾을 수 없습니다.")


@router.post("/user-projects/{doc_id}/source", status_code=204)
async def upload_user_project_source(
    doc_id: str,
    file: UploadFile = File(...),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    user_id: str | None = Query(default=None),
) -> Response:
    """브라우저 IndexedDB 등에만 남은 원본을 회원 저장소로 다시 올릴 때 사용."""
    resolved = _require_user_id(x_user_id, user_id)
    if not file.filename:
        raise HTTPException(400, "파일명이 없습니다.")
    content = await file.read()
    user_storage.save_source(resolved, doc_id, file.filename, content)

    doc = await get_document(doc_id)
    filename = doc.filename if doc else file.filename
    _source_path(doc_id, filename).write_bytes(content)
    return Response(status_code=204)


@router.get("/user-projects/{doc_id}/source")
async def open_user_project_source(
    doc_id: str,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    user_id: str | None = Query(default=None),
) -> FileResponse:
    resolved_user = _require_user_id(x_user_id, user_id)
    await _backfill_user_source_if_missing(resolved_user, doc_id)
    resolved = user_storage.get_source_file(resolved_user, doc_id)
    if resolved:
        path, filename = resolved
        return _file_response_inline(path, filename)

    doc = await get_document(doc_id)
    if doc:
        global_path = _source_path(doc_id, doc.filename)
        if global_path.is_file():
            return _file_response_inline(global_path, doc.filename)

    raise HTTPException(404, "원본 파일을 찾을 수 없습니다.")


@router.get("/user-projects/{doc_id}/easyread.pdf")
async def open_user_project_easyread_pdf(
    doc_id: str,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    user_id: str | None = Query(default=None),
) -> FileResponse:
    resolved_user = _require_user_id(x_user_id, user_id)
    resolved = user_storage.get_easyread_pdf_file(resolved_user, doc_id)
    if not resolved:
        raise HTTPException(404, "저장된 이지리드 PDF를 찾을 수 없습니다.")
    path, filename = resolved
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline",
    )


@router.delete("/user-projects/{doc_id}", status_code=204)
async def delete_user_project(
    doc_id: str,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    user_id: str | None = Query(default=None),
) -> Response:
    resolved_user = _require_user_id(x_user_id, user_id)
    deleted = user_storage.delete_user_project(resolved_user, doc_id)
    if not deleted:
        raise HTTPException(404, "삭제할 프로젝트를 찾을 수 없습니다.")
    return Response(status_code=204)


@router.get("/admin/user-storage", response_model=AdminStorageOverview)
async def admin_list_user_storage(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> AdminStorageOverview:
    _require_admin(x_user_id)
    blocks = [
        AdminUserStorageBlock(
            user_id=block["user_id"],
            projects=[UserProjectItem(**item) for item in block["projects"]],
        )
        for block in user_storage.list_all_users_storage()
    ]
    return AdminStorageOverview(users=blocks)


@router.delete("/admin/user-storage/{storage_user_id}/projects/{doc_id}", status_code=204)
async def admin_delete_user_project(
    storage_user_id: str,
    doc_id: str,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> Response:
    _require_admin(x_user_id)
    deleted = user_storage.delete_user_project(storage_user_id.strip(), doc_id)
    if not deleted:
        raise HTTPException(404, "삭제할 프로젝트를 찾을 수 없습니다.")
    return Response(status_code=204)


@router.get("/{doc_id}/source")
async def read_source_file(doc_id: str) -> FileResponse:
    doc = await get_document(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")

    path = _source_path(doc_id, doc.filename)
    if not path.is_file():
        raise HTTPException(404, "원본 파일을 찾을 수 없습니다.")

    media_type, _ = mimetypes.guess_type(doc.filename)
    return FileResponse(
        path=path,
        media_type=media_type or "application/octet-stream",
        filename=doc.filename,
        content_disposition_type="inline",
    )


@router.head("/{doc_id}/source")
async def head_source_file(doc_id: str) -> Response:
    doc = await get_document(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")

    path = _source_path(doc_id, doc.filename)
    if not path.is_file():
        raise HTTPException(404, "원본 파일을 찾을 수 없습니다.")

    media_type, _ = mimetypes.guess_type(doc.filename)
    return Response(status_code=200, media_type=media_type or "application/octet-stream")


@router.get("/{doc_id}", response_model=DocumentResponse)
async def read_document(doc_id: str) -> DocumentResponse:
    doc = await get_document(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    return doc


@router.patch("/{doc_id}/doc-type", response_model=DocumentResponse)
async def patch_doc_type(doc_id: str, body: DocTypeUpdate) -> DocumentResponse:
    doc = await get_document(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    if body.doc_type == "unknown":
        raise HTTPException(400, "unknown 유형은 선택할 수 없습니다.")
    await update_doc_type(doc_id, body.doc_type)
    updated = await get_document(doc_id)
    if not updated:
        raise HTTPException(404, "문서를 갱신하지 못했습니다.")
    return updated


@router.get("/{doc_id}/pages/{page_num}")
async def read_page(doc_id: str, page_num: int) -> dict[str, str]:
    page = await get_page(doc_id, page_num)
    if page is None:
        raise HTTPException(404, "페이지를 찾을 수 없습니다.")
    return {"page": page}

# --- 요약 API ---


@router.post("/{doc_id}/summarize", response_model=DocumentResponse)
async def summarize_document(
    doc_id: str,
    force: bool = Query(False),
    body: SummarizeRequest | None = None,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> DocumentResponse:
    doc = await get_document(doc_id)
    if not doc:
        if not body or not body.full_text:
            raise HTTPException(404, "문서를 찾을 수 없습니다.")
        pages = body.pages or [body.full_text]
        await ensure_document(
            doc_id,
            filename=body.filename or "upload.pdf",
            doc_type=body.doc_type or "unknown",
            pages=pages,
            full_text=body.full_text,
        )
        doc = await get_document(doc_id)
        if not doc:
            raise HTTPException(404, "문서를 복구하지 못했습니다.")
    if doc.summary and not force:
        return doc

    if not _full_text_sufficient_for_summary(doc.full_text):
        raise HTTPException(
            400,
            "원문 OCR 텍스트가 부족합니다. PDF를 다시 업로드하거나 스캔 PDF면 Upstage OCR 설정을 확인하세요.",
        )

    system = prompts.build_summary_system_prompt(doc.doc_type)
    user = (
        "아래 판결문 **전문만** 보고, 요약 출력 형식에 맞게 **발췌 요약**하세요. "
        "원문에 없는 사건·인물·형량을 invent하지 마세요.\n\n"
        f"{doc.full_text}"
    )
    summary = await upstage.chat_completion(system, user)
    summary = await _polish_summary_text(summary)
    await update_summary(doc_id, summary)
    updated = await get_document(doc_id)
    if updated and x_user_id and updated.summary:
        user_storage.save_summary(x_user_id, doc_id, updated.filename, updated.summary)
        await _backfill_user_source_if_missing(x_user_id, doc_id)
    return updated  # type: ignore[return-value]


@router.patch("/{doc_id}/summary", response_model=DocumentResponse)
async def patch_summary(
    doc_id: str,
    body: SummaryUpdate,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> DocumentResponse:
    doc = await get_document(doc_id)
    if not doc and body.full_text:
        pages = body.pages or [body.full_text]
        await ensure_document(
            doc_id,
            filename=body.filename or "upload.pdf",
            doc_type=body.doc_type or "unknown",
            pages=pages,
            full_text=body.full_text,
        )
        doc = await get_document(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    await update_summary(doc_id, body.summary)
    updated = await get_document(doc_id)
    if updated and x_user_id and updated.summary:
        user_storage.save_summary(x_user_id, doc_id, updated.filename, updated.summary)
        await _backfill_user_source_if_missing(x_user_id, doc_id)
    return updated  # type: ignore[return-value]


@router.post("/{doc_id}/summary/refine", response_model=DocumentResponse)
async def refine_summary(
    doc_id: str,
    body: RefineRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> DocumentResponse:
    doc = await get_document(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    current = (body.summary if body.summary is not None else doc.summary) or ""
    if body.summary is not None and body.summary.strip():
        await update_summary(doc_id, body.summary.strip())
    system = prompts.build_summary_system_prompt(doc.doc_type)
    user = (
        f"현재 요약:\n{current}\n\n"
        f"다음 지시에 따라 요약을 **수정**하세요:\n{body.prompt}\n\n"
        "규칙:\n"
        "- 사용자 지시를 **반드시 반영**하세요.\n"
        "- **수정된 요약 본문만** 출력하세요. 설명·메타 제목은 출력하지 마세요."
    )
    revised = await upstage.chat_completion(system, user, max_tokens=5000, temperature=0.45)
    revised = extract_refined_translation(revised, fallback=current)
    revised = await _polish_summary_text(revised)
    await update_summary(doc_id, revised)
    updated = await get_document(doc_id)
    if updated and x_user_id and updated.summary:
        user_storage.save_summary(x_user_id, doc_id, updated.filename, updated.summary)
        await _backfill_user_source_if_missing(x_user_id, doc_id)
    return updated  # type: ignore[return-value]

# --- 쉬운 글(번역) API ---


@router.post("/{doc_id}/translate", response_model=DocumentResponse)
async def translate_document(
    doc_id: str,
    body: DocumentEnsureRequest | None = None,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> DocumentResponse:
    doc = await _ensure_doc_from_request(doc_id, body)
    if not doc.summary:
        raise HTTPException(400, "먼저 요약을 생성하세요.")
    if doc.translation_segments:
        return doc

    segments, text, checklist_report = await translator.translate_summary(
        doc.summary, doc.full_text, doc.doc_type
    )
    await update_translation(doc_id, segments, text, checklist=checklist_report)
    updated = await get_document(doc_id)
    if updated:
        await _persist_user_translation(x_user_id, doc_id, updated)
    return updated  # type: ignore[return-value]


@router.post("/{doc_id}/translation/detect-placements", response_model=list[ImagePlacement])
async def detect_translation_placements(
    doc_id: str,
    body: DetectPlacementsRequest | None = None,
) -> list[ImagePlacement]:
    doc = await _ensure_doc_from_request(doc_id, body)
    text = (
        (body.translation_text if body and body.translation_text else None)
        or doc.translation_text
        or "\n\n".join(s.easy_text for s in doc.translation_segments if s.easy_text)
    )
    if not text.strip():
        raise HTTPException(400, "번역본이 없습니다.")
    existing = body.existing_placements if body else []
    return await fill_missing_item_placements_async(text, existing)


@router.patch("/{doc_id}/translation", response_model=DocumentResponse)
async def patch_translation(
    doc_id: str,
    body: TranslationUpdate,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> DocumentResponse:
    doc = await get_document(doc_id)
    if not doc and body.full_text:
        pages = body.pages or [body.full_text]
        await ensure_document(
            doc_id,
            filename=body.filename or "upload.pdf",
            doc_type=body.doc_type or "unknown",
            pages=pages,
            full_text=body.full_text,
        )
        doc = await get_document(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    if body.summary is not None and body.summary.strip():
        await update_summary(doc_id, body.summary)
        doc = await get_document(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    text = "\n\n".join(s.easy_text for s in body.segments)
    checklist_report = translator.run_checklist(text)
    await update_translation(doc_id, body.segments, text, checklist=checklist_report)
    updated = await get_document(doc_id)
    if updated:
        await _persist_user_translation(x_user_id, doc_id, updated)
    return updated  # type: ignore[return-value]


@router.post("/{doc_id}/translation/refine", response_model=DocumentResponse)
async def refine_translation(
    doc_id: str,
    body: RefineRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> DocumentResponse:
    doc = await get_document(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    doc_type = await get_doc_type(doc_id) or "unknown"
    segments = body.segments if body.segments is not None else doc.translation_segments
    if body.segments is not None and body.segments:
        text = "\n\n".join(s.easy_text for s in body.segments if s.easy_text)
        await update_translation(doc_id, body.segments, text)
    try:
        segments, text, checklist_report = await translator.refine_translation(
            segments, body.prompt, doc_type
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await update_translation(doc_id, segments, text, checklist=checklist_report)
    updated = await get_document(doc_id)
    if updated:
        await _persist_user_translation(x_user_id, doc_id, updated)
    return updated  # type: ignore[return-value]


@router.post("/{doc_id}/translation/checklist", response_model=ChecklistReport)
async def run_translation_checklist(doc_id: str) -> ChecklistReport:
    doc = await get_document(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    text = doc.translation_text or "\n\n".join(
        s.easy_text for s in doc.translation_segments
    )
    if not text.strip():
        raise HTTPException(400, "번역본이 없습니다.")
    report = translator.run_checklist(text)
    if doc.translation_segments:
        await update_translation(
            doc_id, doc.translation_segments, text, checklist=report
        )
    return report

# --- Word 내보내기 ---


@router.get("/{doc_id}/export.docx")
async def export_docx_get(
    doc_id: str,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> Response:
    return await _export_docx(doc_id, None, x_user_id=x_user_id)


@router.post("/{doc_id}/export.docx")
async def export_docx_post(
    doc_id: str,
    body: ExportRequest | None = None,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> Response:
    return await _export_docx(doc_id, body, x_user_id=x_user_id)


def _resolve_upload_source_path(
    doc_id: str,
    filename: str,
    user_id: str | None = None,
    body: ExportRequest | None = None,
) -> Path | None:
    if body and body.source_pdf_base64:
        try:
            raw = base64.b64decode(body.source_pdf_base64, validate=True)
        except Exception:
            raw = b""
        if raw.startswith(b"%PDF"):
            path = _source_path(doc_id, filename or "source.pdf")
            path.write_bytes(raw)
            if user_id:
                user_storage.save_source(user_id, doc_id, filename or path.name, raw)

    path = _source_path(doc_id, filename)
    if path.is_file() and path.suffix.lower() == ".pdf":
        return path
    if user_id:
        resolved = user_storage.get_source_file(user_id, doc_id)
        if resolved:
            file_path, _ = resolved
            if file_path.is_file() and file_path.suffix.lower() == ".pdf":
                return file_path
    return None


async def _export_docx(
    doc_id: str,
    body: ExportRequest | None,
    *,
    x_user_id: str | None,
) -> Response:
    doc = await _resolve_document(doc_id, body)
    doc = _doc_for_export(doc_id, doc, body)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    if not doc.translation_text and not doc.summary and not doc.translation_segments:
        raise HTTPException(400, "내보낼 내용이 없습니다.")

    content = word_export.export_to_docx(
        doc,
        source_file=_resolve_upload_source_path(doc_id, doc.filename, x_user_id, body),
    )
    if x_user_id:
        easyread_text = doc.translation_text or doc.summary or ""
        if easyread_text:
            user_storage.save_easyread_text(x_user_id, doc_id, doc.filename, easyread_text)
        user_storage.save_easyread_docx(x_user_id, doc_id, doc.filename, content)
        await _persist_user_translation(x_user_id, doc_id, doc)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="easyread_{doc_id[:8]}.docx"'},
    )


# --- PDF 내보내기 ---


@router.get("/{doc_id}/export.pdf")
async def export_pdf_get(
    doc_id: str,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> Response:
    return await _export_pdf(doc_id, None, inline=True, x_user_id=x_user_id)


@router.post("/{doc_id}/export.pdf")
async def export_pdf_post(
    doc_id: str,
    body: ExportRequest | None = None,
    download: bool = Query(False),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> Response:
    return await _export_pdf(doc_id, body, inline=not download, x_user_id=x_user_id)


async def _export_pdf(
    doc_id: str,
    body: ExportRequest | None,
    *,
    inline: bool,
    x_user_id: str | None,
) -> Response:
    doc = await _resolve_document(doc_id, body)
    doc = _doc_for_export(doc_id, doc, body)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    if not doc.translation_text and not doc.summary and not doc.translation_segments:
        raise HTTPException(400, "내보낼 내용이 없습니다.")

    from backend.services.docx_to_pdf import DocxToPdfError

    try:
        content = pdf_export.export_to_pdf(
            doc,
            source_file=_resolve_upload_source_path(doc_id, doc.filename, x_user_id, body),
        )
    except DocxToPdfError as exc:
        raise HTTPException(
            503,
            "서버에 Word/LibreOffice PDF 변환기가 없습니다. 브라우저 인쇄(Microsoft Print to PDF)를 사용하세요.",
        ) from exc

    if x_user_id:
        easyread_text = doc.translation_text or doc.summary or ""
        if easyread_text:
            user_storage.save_easyread_text(x_user_id, doc_id, doc.filename, easyread_text)
        user_storage.save_easyread_pdf(x_user_id, doc_id, doc.filename, content)
        await _persist_user_translation(x_user_id, doc_id, doc)

    disposition = "inline" if inline else "attachment"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="easyread_{doc_id[:8]}.pdf"'
        },
    )
