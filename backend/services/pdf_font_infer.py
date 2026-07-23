from __future__ import annotations

"""원본 PDF 텍스트 레이어에서 글꼴 이름·크기 추정 (PyMuPDF)."""

import logging
import re
from collections import Counter

import fitz

from backend.services.court_fonts import (
    ExportFontProfile,
    bundled_court_font_profile,
    is_known_export_font_name,
)
from backend.services.pdf_native_merge import _split_y_after_reason_heading
from backend.services.word_export import BODY_PT, _pick_dominant_font

logger = logging.getLogger(__name__)

_INTERNAL_FONT = re.compile(r"^[fg]_\d+(_f\d+)?$", re.I)


def normalize_pdf_font_name(raw: str) -> str:
    """'ABCDEF+CourtBT' → 'CourtBT'."""
    name = (raw or "").strip()
    if not name:
        return name
    if "+" in name:
        name = name.split("+", 1)[1]
    return name.strip()


def _page_font_map(page: fitz.Page) -> dict[str, str]:
    """span['font'] / get_fonts 이름 → 정규화된 basefont."""
    mapping: dict[str, str] = {}
    try:
        entries = page.get_fonts(full=True)
    except TypeError:
        entries = page.get_fonts()
    for entry in entries or []:
        if len(entry) < 4:
            continue
        basefont = normalize_pdf_font_name(str(entry[3] or ""))
        if not basefont:
            continue
        mapping[str(entry[3] or "")] = basefont
        if len(entry) > 4:
            mapping[str(entry[4] or "")] = basefont
        if len(entry) > 0:
            mapping[str(entry[0])] = basefont
    return mapping


def resolve_span_font_name(span: dict, font_map: dict[str, str]) -> str:
    raw = str(span.get("font") or "").strip()
    if not raw:
        return ""
    if raw in font_map:
        return font_map[raw]
    normalized = normalize_pdf_font_name(raw)
    if normalized and not _INTERNAL_FONT.match(normalized):
        return normalized
    for key, base in font_map.items():
        if key and key in raw:
            return base
    return ""


def _collect_span_weights(
    page: fitz.Page,
    font_weights: Counter[str],
    size_weights: Counter[float],
    *,
    min_y: float = 0,
    max_y: float | None = None,
    max_chars: int = 12000,
    collected: list[int] | None = None,
) -> None:
    if collected is None:
        collected = [0]
    if collected[0] >= max_chars:
        return

    font_map = _page_font_map(page)
    data = page.get_text("dict") or {}

    for block in data.get("blocks") or []:
        if block.get("type") != 0:
            continue
        for line in block.get("lines") or []:
            for span in line.get("spans") or []:
                bbox = span.get("bbox")
                if not bbox or len(bbox) < 4:
                    continue
                y0 = float(bbox[1])
                if y0 < min_y - 0.5:
                    continue
                if max_y is not None and y0 >= max_y:
                    continue
                text = str(span.get("text") or "")
                if not text.strip():
                    continue
                weight = len(text)
                collected[0] += weight
                font = resolve_span_font_name(span, font_map)
                if font:
                    font_weights[font] += weight
                size = span.get("size")
                if size is not None:
                    try:
                        size_weights[float(size)] += weight
                    except (TypeError, ValueError):
                        pass
                if collected[0] >= max_chars:
                    return


def infer_font_profile_from_reason_vicinity_pdf(
    pdf: fitz.Document,
    reason_page: int,
    reason_rect: fitz.Rect,
    *,
    max_chars: int = 12000,
) -> ExportFontProfile | None:
    """원문 PDF(이유 페이지까지)에서 지배적 글꼴·크기 추정 → 이지리드 export에 적용."""
    if reason_page < 0 or reason_page >= pdf.page_count:
        return None

    font_weights: Counter[str] = Counter()
    size_weights: Counter[float] = Counter()
    collected = [0]

    for page_idx in range(0, reason_page + 1):
        page = pdf.load_page(page_idx)
        max_y: float | None = None
        if page_idx == reason_page:
            max_y = _split_y_after_reason_heading(page, reason_rect)
        _collect_span_weights(
            page,
            font_weights,
            size_weights,
            min_y=0,
            max_y=max_y,
            max_chars=max_chars,
            collected=collected,
        )
        if collected[0] >= max_chars:
            break

    if not font_weights:
        for page_idx in range(0, reason_page + 1):
            page = pdf.load_page(page_idx)
            for entry in page.get_fonts() or []:
                if len(entry) < 4:
                    continue
                base = normalize_pdf_font_name(str(entry[3] or ""))
                if base:
                    font_weights[base] += 1

    if not font_weights:
        return None

    dominant = _pick_dominant_font(font_weights) or font_weights.most_common(1)[0][0]
    body_pt = size_weights.most_common(1)[0][0] if size_weights else BODY_PT
    logger.info(
        "pdf font infer: through_page=%d font=%s pt=%.1f top=%s",
        reason_page,
        dominant,
        body_pt,
        dict(font_weights.most_common(4)),
    )
    return ExportFontProfile(
        ascii=dominant,
        h_ansi=dominant,
        east_asia=dominant,
        body_pt=body_pt,
    )


def font_profile_for_easy_read_export(
    pdf: fitz.Document | None,
    reason_page: int | None,
    reason_rect: fitz.Rect | None,
) -> ExportFontProfile:
    return bundled_court_font_profile()
