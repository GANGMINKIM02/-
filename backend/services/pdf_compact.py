from __future__ import annotations

"""PDF 병합 전 이지리드 PDF 여백·빈 페이지 정리."""

import fitz


def _page_text_len(page: fitz.Page) -> int:
    return len((page.get_text("text") or "").replace("\n", "").strip())


def _visible_content_rect(page: fitz.Page, *, margin: float = 6) -> fitz.Rect | None:
    union: fitz.Rect | None = None
    data = page.get_text("dict") or {}
    for block in data.get("blocks") or []:
        if block.get("type") != 0:
            continue
        bbox = block.get("bbox")
        if bbox and len(bbox) >= 4:
            r = fitz.Rect(bbox)
            union = r if union is None else union | r
    try:
        for img in page.get_image_info(xrefs=True) or []:
            bbox = img.get("bbox")
            if bbox:
                r = fitz.Rect(bbox)
                union = r if union is None else union | r
    except (AttributeError, TypeError):
        pass
    if union is None or union.is_empty:
        return None
    expanded = fitz.Rect(
        union.x0 - margin,
        union.y0 - margin,
        union.x1 + margin,
        union.y1 + margin,
    )
    return expanded & page.rect


def _page_is_blank(page: fitz.Page) -> bool:
    if _page_text_len(page) > 4:
        return False
    rect = _visible_content_rect(page, margin=0)
    return rect is None or rect.height < 12


def compact_pdf_for_insert(doc: fitz.Document) -> fitz.Document:
    """빈 꼬리 페이지 제거 + 각 페이지를 보이는 영역 높이로 잘라 연속 흐름에 맞춤."""
    from backend.services.pdf_page_numbers import page_height_with_number_footer

    if doc.page_count == 0:
        return doc

    while doc.page_count > 1 and _page_is_blank(doc[doc.page_count - 1]):
        doc.delete_page(doc.page_count - 1)

    out = fitz.open()
    for index in range(doc.page_count):
        page = doc[index]
        if _page_is_blank(page):
            continue
        clip = _visible_content_rect(page) or page.rect
        clip = clip & page.rect
        if clip.is_empty or clip.height < 8:
            continue
        w = page.rect.width
        total_h = page_height_with_number_footer(clip.height)
        new_page = out.new_page(width=w, height=total_h)
        new_page.show_pdf_page(fitz.Rect(0, 0, w, clip.height), doc, index, clip=clip)
    if out.page_count == 0:
        return doc
    return out


def _append_clipped(
    out: fitz.Document,
    doc: fitz.Document,
    page_number: int,
    clip: fitz.Rect,
    page_w: float,
) -> None:
    from backend.services.pdf_page_numbers import page_height_with_number_footer

    clip = clip & doc[page_number].rect
    if clip.is_empty or clip.height < 8:
        return
    total_h = page_height_with_number_footer(clip.height)
    new_page = out.new_page(width=page_w, height=total_h)
    new_page.show_pdf_page(fitz.Rect(0, 0, page_w, clip.height), doc, page_number, clip=clip)


_SUFFIX_FLOW_GAP_PT = 8.0


def _visible_union_in_rect(page: fitz.Page, region: fitz.Rect, *, margin: float = 4) -> fitz.Rect | None:
    region = region & page.rect
    if region.is_empty or region.height < 8:
        return None
    union: fitz.Rect | None = None
    data = page.get_text("dict") or {}
    for block in data.get("blocks") or []:
        if block.get("type") != 0:
            continue
        bbox = block.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        r = fitz.Rect(bbox) & region
        if r.is_empty or r.height < 4:
            continue
        union = r if union is None else union | r
    if union is None or union.is_empty or union.height < 8:
        return None
    return fitz.Rect(
        region.x0,
        max(region.y0, union.y0 - margin),
        region.x1,
        min(region.y1, union.y1 + margin),
    ) & region


def _flow_clip_from_band(page: fitz.Page, band: fitz.Rect) -> fitz.Rect | None:
    """밴드 안 실제 글자·그림 영역만 (페이지 하단 빈 여백 제외)."""
    band = band & page.rect
    if band.is_empty or band.height < 8:
        return None
    tight = _visible_union_in_rect(page, band, margin=4)
    if tight is None:
        return band if band.height >= 8 else None
    return tight


def _flow_clip_full_page(page: fitz.Page) -> fitz.Rect | None:
    from backend.services.pdf_page_numbers import clip_excluding_footer

    band = clip_excluding_footer(page, page.rect)
    return _flow_clip_from_band(page, band)


def _append_stacked_source_clips(
    out: fitz.Document,
    src: fitz.Document,
    first_page: int,
    first_clip: fitz.Rect,
    second_page: int,
    second_clip: fitz.Rect,
    page_w: float,
    page_h: float,
) -> bool:
    from backend.services.pdf_page_numbers import PAGE_NUMBER_FOOTER_RESERVE_PT

    stack_h = first_clip.height + _SUFFIX_FLOW_GAP_PT + second_clip.height
    footer = PAGE_NUMBER_FOOTER_RESERVE_PT
    if stack_h > page_h - footer + 4:
        return False

    dest_page = out.new_page(width=page_w, height=page_h)
    y = 0.0
    dest_page.show_pdf_page(
        fitz.Rect(0, y, page_w, y + first_clip.height),
        src,
        first_page,
        clip=first_clip,
    )
    y += first_clip.height + _SUFFIX_FLOW_GAP_PT
    dest_page.show_pdf_page(
        fitz.Rect(0, y, page_w, y + second_clip.height),
        src,
        second_page,
        clip=second_clip,
    )
    return True


def _append_source_pages_flow(
    out: fitz.Document,
    src: fitz.Document,
    from_page: int,
    to_page: int,
    page_w: float,
) -> None:
    """원문 페이지를 본문 영역만 잘라 연속 배치(원본 A4 여백 제거)."""
    last = min(to_page, src.page_count - 1)
    for index in range(from_page, last + 1):
        clip = _flow_clip_full_page(src[index])
        if clip:
            _append_clipped(out, src, index, clip, page_w)


def append_easy_read_then_suffix(
    out: fitz.Document,
    easy: fitz.Document,
    src: fitz.Document,
    reason_page: int,
    suffix_clip: fitz.Rect,
    *,
    gap_pt: float = 10,
) -> None:
    """이지리드 다음 원문 — 위쪽 빈 여백만 줄이고, 다음 페이지와 한 장에 맞으면 이어 붙임."""
    from backend.services.pdf_page_numbers import clip_excluding_footer

    if easy.page_count:
        out.insert_pdf(easy)

    src_page = src[reason_page]
    page_w = src_page.rect.width
    page_h = src_page.rect.height
    band = clip_excluding_footer(src_page, suffix_clip & src_page.rect)
    first_clip = _flow_clip_from_band(src_page, band)

    if first_clip is None:
        if reason_page + 1 < src.page_count:
            _append_source_pages_flow(
                out, src, reason_page + 1, src.page_count - 1, page_w
            )
        return

    if reason_page + 1 < src.page_count:
        next_clip = _flow_clip_full_page(src[reason_page + 1])
        if next_clip and _append_stacked_source_clips(
            out,
            src,
            reason_page,
            first_clip,
            reason_page + 1,
            next_clip,
            page_w,
            page_h,
        ):
            if reason_page + 2 < src.page_count:
                _append_source_pages_flow(
                    out, src, reason_page + 2, src.page_count - 1, page_w
                )
            return

    _append_clipped(out, src, reason_page, first_clip, page_w)

    if reason_page + 1 < src.page_count:
        _append_source_pages_flow(out, src, reason_page + 1, src.page_count - 1, page_w)
