from __future__ import annotations

"""이지리드 PDF — Word 표 테두리가 PDF 변환에서 빠질 때 보이는 프레임."""

import fitz

from backend.services.pdf_compact import _page_text_len, _visible_content_rect

_FRAME_COLOR = (0.72, 0.69, 0.64)
_FRAME_PAD = 10.0
_FRAME_WIDTH = 1.4
# word_export PAGE_MARGIN_IN = 0.6
_EASY_READ_MARGIN_PT = 0.6 * 72.0


def _frame_rect_for_page(page: fitz.Page) -> fitz.Rect | None:
    """본문 bbox + 여백 밴드 fallback (Word PDF에서 get_text가 비는 페이지 대비)."""
    r = page.rect
    band = fitz.Rect(
        r.x0 + _EASY_READ_MARGIN_PT,
        r.y0 + _EASY_READ_MARGIN_PT,
        r.x1 - _EASY_READ_MARGIN_PT,
        r.y1 - _EASY_READ_MARGIN_PT,
    )
    if band.is_empty or band.width < 40:
        return None

    content = _visible_content_rect(page, margin=4)
    if content is None or content.is_empty or content.height < 8:
        if _page_text_len(page) > 4:
            return band
        return None

    frame = fitz.Rect(
        band.x0,
        max(band.y0, content.y0 - _FRAME_PAD),
        band.x1,
        min(band.y1, content.y1 + _FRAME_PAD),
    )
    return frame & r


def decorate_easy_read_pdf(doc: fitz.Document) -> fitz.Document:
    """각 이지리드 페이지 본문 주변에 글상자 테두리만 그린다(배경은 원문과 동일한 흰색)."""
    if doc.page_count == 0:
        return doc

    for index in range(doc.page_count):
        page = doc[index]
        frame = _frame_rect_for_page(page)
        if frame is None or frame.is_empty or frame.height < 12:
            continue
        page.draw_rect(
            frame,
            color=_FRAME_COLOR,
            width=_FRAME_WIDTH,
            overlay=True,
        )
    return doc
