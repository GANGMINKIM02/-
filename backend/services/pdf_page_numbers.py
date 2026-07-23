from __future__ import annotations

"""병합 PDF — 원문 쪽표기 제거 후 1부터 순번 부여."""

import logging
import re

import fitz

logger = logging.getLogger(__name__)

# 클립·압축 페이지 하단에 순번을 넣을 여백(본문과 겹침 방지).
PAGE_NUMBER_FOOTER_RESERVE_PT = 42

_PAGE_DASH = re.compile(r"^\s*-\s*\d+\s*-\s*$")
_PAGE_SLASH = re.compile(r"^\s*\(?\s*\d+\s*[/／]\s*\d+\s*\)?\s*쪽?\s*$")
_PAGE_KOR = re.compile(r"^\s*\(\s*\d+\s*[/／]\s*\d+\s*쪽\s*\)\s*$")


def _line_text(line: dict) -> str:
    return "".join(str(s.get("text") or "") for s in line.get("spans") or []).strip()


def _is_page_number_line(text: str) -> bool:
    if not text:
        return False
    if _PAGE_DASH.match(text):
        return True
    if _PAGE_SLASH.match(text):
        return True
    if _PAGE_KOR.match(text):
        return True
    if re.match(r"^\s*\d+\s*쪽\s*$", text):
        return True
    return False


def _footer_band(page: fitz.Page) -> fitz.Rect:
    r = page.rect
    return fitz.Rect(r.x0, r.y0 + r.height * 0.86, r.x1, r.y1)


def redact_page_number_marks(page: fitz.Page) -> None:
    """하단 원문 쪽번호·(n/m쪽) 등 가림."""
    band = _footer_band(page)
    redacted = False
    data = page.get_text("dict") or {}
    for block in data.get("blocks") or []:
        if block.get("type") != 0:
            continue
        for line in block.get("lines") or []:
            text = _line_text(line)
            if not _is_page_number_line(text):
                continue
            bbox = line.get("bbox")
            if not bbox or len(bbox) < 4:
                continue
            rect = fitz.Rect(bbox)
            if rect.y0 < band.y0 - 4:
                continue
            pad = rect + (-4, -3, 4, 3)
            page.add_redact_annot(pad & page.rect, fill=(1, 1, 1))
            redacted = True
    if redacted:
        page.apply_redactions()


def clip_excluding_footer(page: fitz.Page, clip: fitz.Rect) -> fitz.Rect:
    """원문 클립 시 하단 쪽번호 줄은 잘라내기."""
    band = _footer_band(page)
    top_y: float | None = None
    data = page.get_text("dict") or {}
    for block in data.get("blocks") or []:
        if block.get("type") != 0:
            continue
        for line in block.get("lines") or []:
            if not _is_page_number_line(_line_text(line)):
                continue
            bbox = line.get("bbox")
            if not bbox or len(bbox) < 4:
                continue
            if float(bbox[1]) >= band.y0 - 4:
                y = float(bbox[1])
                if top_y is None or y < top_y:
                    top_y = y
    if top_y is not None and top_y > clip.y0 + 20:
        return fitz.Rect(clip.x0, clip.y0, clip.x1, min(clip.y1, top_y - 4))
    return clip


def _number_fontfile() -> str | None:
    from backend.services.court_fonts import NANUM_MYUNGJO_REGULAR

    if NANUM_MYUNGJO_REGULAR.is_file():
        return str(NANUM_MYUNGJO_REGULAR.resolve())
    return None


def page_height_with_number_footer(content_height: float) -> float:
    """클립 본문 높이 + 쪽번호용 하단 여백."""
    return max(content_height, 8) + PAGE_NUMBER_FOOTER_RESERVE_PT


def apply_sequential_page_numbers(doc: fitz.Document, *, start: int = 1) -> None:
    """전 페이지 하단에 - 1 - 형식 순번."""
    fontfile = _number_fontfile()
    for index in range(doc.page_count):
        page = doc[index]
        redact_page_number_marks(page)
        label = f"- {start + index} -"
        r = page.rect
        if r.height < 28:
            continue
        box = fitz.Rect(r.x0 + 40, r.y1 - 30, r.x1 - 40, r.y1 - 10)
        kwargs: dict = {
            "fontsize": 11,
            "color": (0, 0, 0),
            "align": fitz.TEXT_ALIGN_CENTER,
        }
        if fontfile:
            kwargs["fontfile"] = fontfile
        else:
            kwargs["fontname"] = "helv"
        page.insert_textbox(box, label, **kwargs)


def renumber_merged_document(doc: fitz.Document) -> None:
    apply_sequential_page_numbers(doc, start=1)
    logger.info("merged pdf renumbered: %d pages", doc.page_count)
