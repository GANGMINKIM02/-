from __future__ import annotations

"""원본 PDF 양식 유지 3단 병합: [이유 제목줄까지] + [이지리드 PDF] + [이유 다음 나머지]."""

import io
import logging
import re
from pathlib import Path

import fitz

from backend.models.schemas import DocumentResponse
from backend.services import word_export
from backend.services.judgment_merge import split_judgment_at_reason
from backend.services.pdf_compact import append_easy_read_then_suffix

logger = logging.getLogger(__name__)

_REASON_LINE = re.compile(r"^이\s*유\s*$")


def _reason_heading_rect(page: fitz.Page) -> fitz.Rect | None:
    data = page.get_text("dict") or {}
    for block in data.get("blocks") or []:
        if block.get("type") != 0:
            continue
        for line in block.get("lines") or []:
            spans = line.get("spans") or []
            line_text = "".join(str(s.get("text") or "") for s in spans)
            if _REASON_LINE.match(line_text.strip()):
                bbox = line.get("bbox")
                if bbox and len(bbox) >= 4:
                    return fitz.Rect(bbox)
    for label in ("이 유", "이유", "이  유"):
        for rect in page.search_for(label):
            expanded = fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2)
            sample = (page.get_text("text", clip=expanded) or "").strip()
            compact = re.sub(r"\s+", " ", sample)
            if _REASON_LINE.match(compact) or compact in ("이유", "이 유"):
                return fitz.Rect(rect)
    return None


def _page_has_reason_heading(page: fitz.Page) -> bool:
    return _reason_heading_rect(page) is not None


def find_reason_page_index(pdf: fitz.Document, full_text: str | None) -> int | None:
    for index in range(pdf.page_count):
        if _page_has_reason_heading(pdf.load_page(index)):
            return index

    if full_text and split_judgment_at_reason(full_text):
        for index in range(pdf.page_count):
            page_text = pdf.load_page(index).get_text("text") or ""
            if re.search(r"이\s*유", page_text):
                return index
    return None


def _line_plain_text(line: dict) -> str:
    spans = line.get("spans") or []
    return "".join(str(s.get("text") or "") for s in spans).strip()


def _split_y_after_reason_heading(page: fitz.Page, reason_rect: fitz.Rect) -> float:
    """「이유」 제목줄 바로 아래(다음 줄 시작)에서 잘라 이지리드를 끼워 넣는다."""
    next_line_y: float | None = None
    data = page.get_text("dict") or {}
    for block in data.get("blocks") or []:
        if block.get("type") != 0:
            continue
        for line in block.get("lines") or []:
            bbox = line.get("bbox")
            if not bbox or len(bbox) < 4:
                continue
            if _REASON_LINE.match(_line_plain_text(line)):
                continue
            y0 = float(bbox[1])
            if y0 > reason_rect.y1 + 0.5:
                if next_line_y is None or y0 < next_line_y:
                    next_line_y = y0
    if next_line_y is not None:
        return max(reason_rect.y1 + 2, next_line_y - 1)
    return min(reason_rect.y1 + 8, page.rect.y1)


def find_reason_heading_position(
    doc: fitz.Document,
    full_text: str | None = None,
) -> tuple[int, fitz.Rect] | None:
    candidates: list[tuple[int, fitz.Rect]] = []
    for index in range(doc.page_count):
        rect = _reason_heading_rect(doc.load_page(index))
        if rect is not None:
            candidates.append((index, rect))
    if not candidates:
        return None
    if full_text:
        split = split_judgment_at_reason(full_text)
        if split:
            suffix = split[1].strip()
            needle = re.sub(r"\s+", "", suffix[:48])
            if len(needle) >= 6:
                for page_index, rect in reversed(candidates):
                    page_text = re.sub(r"\s+", "", doc.load_page(page_index).get_text("text") or "")
                    if needle[: min(24, len(needle))] in page_text:
                        return page_index, rect
    return candidates[-1]


def _append_clipped_page(out: fitz.Document, src: fitz.Document, page_number: int, clip: fitz.Rect) -> None:
    from backend.services.pdf_page_numbers import clip_excluding_footer, page_height_with_number_footer

    src_page = src[page_number]
    clip = clip_excluding_footer(src_page, clip)
    clip = clip & src_page.rect
    page_w = src_page.rect.width
    if clip.is_empty or clip.height < 8:
        return
    total_h = page_height_with_number_footer(clip.height)
    new_page = out.new_page(width=page_w, height=total_h)
    target = fitz.Rect(0, 0, page_w, clip.height)
    new_page.show_pdf_page(target, src, page_number, clip=clip)


def _prepare_easy_read_pdf_bytes(pdf_bytes: bytes) -> bytes:
    """병합 직전 compact·decorate 순서는 merge 쪽에서 처리한다."""
    return pdf_bytes


def _easy_read_insert_pdf_bytes(
    doc: DocumentResponse,
    *,
    source_pdf: fitz.Document | None = None,
    reason_page: int | None = None,
    reason_rect: fitz.Rect | None = None,
) -> bytes | None:
    from backend.services.docx_to_pdf import DocxToPdfError, convert_docx_bytes_to_pdf
    from backend.services.pdf_export import render_easy_read_insert_html_pdf
    from backend.services.pdf_font_infer import font_profile_for_easy_read_export

    font_profile = font_profile_for_easy_read_export(source_pdf, reason_page, reason_rect)

    insert_doc = word_export.build_easy_read_insert_document(doc, font_profile=font_profile)
    buffer = io.BytesIO()
    insert_doc.save(buffer)
    try:
        return _prepare_easy_read_pdf_bytes(convert_docx_bytes_to_pdf(buffer.getvalue()))
    except DocxToPdfError:
        logger.info("easy-read insert: docx2pdf unavailable, using PyMuPDF HTML")
        rendered = render_easy_read_insert_html_pdf(doc, font_profile=font_profile)
        if not rendered:
            return None
        return _prepare_easy_read_pdf_bytes(rendered)


def merge_pdf_three_part_with_easy_read(pdf_path: Path, doc: DocumentResponse) -> bytes | None:
    """이유 제목줄까지 원문 → 이지리드 → 이유 다음 원문 나머지."""
    if pdf_path.suffix.lower() != ".pdf" or not pdf_path.is_file():
        return None
    if not word_export.collect_body_text(doc):
        return None

    src = fitz.open(pdf_path)
    try:
        found = find_reason_heading_position(src, doc.full_text)
        if found is None:
            logger.info("pdf 3-part merge: 「이유」 좌표 없음")
            return None

        reason_page, reason_rect = found
        easy_bytes = _easy_read_insert_pdf_bytes(
            doc,
            source_pdf=src,
            reason_page=reason_page,
            reason_rect=reason_rect,
        )
        if not easy_bytes:
            return None

        easy = fitz.open(stream=easy_bytes, filetype="pdf")
        from backend.services.pdf_compact import compact_pdf_for_insert
        from backend.services.pdf_easy_read_frame import decorate_easy_read_pdf

        compacted = compact_pdf_for_insert(easy)
        if compacted is not easy:
            easy.close()
            easy = compacted
        decorate_easy_read_pdf(easy)
        out = fitz.open()
        try:
            page = src[reason_page]
            split_y = _split_y_after_reason_heading(page, reason_rect)
            split_y = min(max(split_y, reason_rect.y1 + 2), page.rect.y1)

            if reason_page > 0:
                out.insert_pdf(src, from_page=0, to_page=reason_page - 1)

            prefix_clip = fitz.Rect(page.rect.x0, page.rect.y0, page.rect.x1, split_y)
            _append_clipped_page(out, src, reason_page, prefix_clip)

            append_easy_read_then_suffix(
                out,
                easy,
                src,
                reason_page,
                fitz.Rect(page.rect.x0, split_y, page.rect.x1, page.rect.y1),
            )

            from backend.services.pdf_page_numbers import renumber_merged_document

            renumber_merged_document(out)

            logger.info(
                "pdf 3-part merge: page=%d split_y=%.1f pages_out=%d",
                reason_page,
                split_y,
                out.page_count,
            )
            return out.tobytes(garbage=4, deflate=True)
        finally:
            easy.close()
    finally:
        src.close()


def merge_original_pdf_with_easy_read(pdf_path: Path, doc: DocumentResponse) -> bytes | None:
    return merge_pdf_three_part_with_easy_read(pdf_path, doc)
