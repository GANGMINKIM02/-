from __future__ import annotations

"""이지리드 문서 PDF 내보내기.

역할: Word(.docx) export 결과를 PDF로 변환해 미리보기·다운로드에 사용한다.
주요 기능: export_to_pdf — Word 완성 → docx→pdf (실패 시 HTML/PyMuPDF 폴백).
관계: word_export, docx_to_pdf, routers/documents.
"""

import base64
import html
import io
import logging
import mimetypes
import os
import re
import tempfile
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

from backend.models.schemas import DocumentResponse, ImagePlacement
from backend.services.export_layout import (
    align_placements_one_per_section,
    is_image_placeholder,
    is_major_section_page_break,
    parse_export_sections,
    parse_section_items,
    prepare_placements_for_export,
    split_item_lines_into_blocks,
)
from backend.services.easy_read_sanitize import split_standard_closing
from backend.services.image_assets import resolve_placement_image
from backend.services.rich_text import iter_styled_runs
from backend.services.image_matcher import MAX_IMAGES_PER_TEXT, ensure_item_placements, find_images_for_line
from backend.services.word_export import (
    _META_SECTION_START,
    _SKIP_LINE,
    _clean_heading,
    _collect_body_text,
    _collect_placements,
    _is_heading,
    EASY_READ_FONT_PROFILE,
    ExportFontProfile,
)
from backend.services.court_fonts import (
    css_font_family_stack,
    story_font_face_css,
)

FONT_URL = (
    "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
)
PAGE_WIDTH = 595.28
PAGE_HEIGHT = 841.89
MARGIN = 43  # 0.6in — word_export PAGE_MARGIN 과 맞춤
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
IMAGE_COL_PT = round(CONTENT_WIDTH * 0.32)
IMAGE_INSET_PT = IMAGE_COL_PT - 12
IMAGE_MAX_HEIGHT_PT = 130

_BOLD = re.compile(r"\*\*(.+?)\*\*")


def _font_dir() -> Path:
    from backend.services.court_fonts import FONT_DIR, register_bundled_fonts_for_process

    register_bundled_fonts_for_process()
    if FONT_DIR.is_dir() and any(FONT_DIR.glob("*.ttf")):
        return FONT_DIR
    cache_dir = Path(os.environ.get("TMPDIR", os.environ.get("TEMP", "/tmp")))
    cached = cache_dir / "nanumgothic-regular.ttf"
    if not cached.exists():
        import httpx

        response = httpx.get(FONT_URL, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        cached.write_bytes(response.content)
    return cache_dir


def _font_css(
    family: str | None = None,
    body_pt: float = 12,
) -> tuple[str, fitz.Archive]:
    font_dir = _font_dir()
    archive = fitz.Archive(str(font_dir))
    stack = css_font_family_stack() if family is None else f'"{family.replace(chr(34), "")}", "Nanum Myeongjo", serif'
    css = f"""
    {story_font_face_css()}
    body {{
      font-family: {stack};
      font-size: {body_pt}px;
      line-height: 2;
      color: #21272a;
    }}
    p.body {{
      margin: 0 0 8px 0;
    }}
    p.heading {{
      margin: 16px 0 8px 0;
      font-size: 17px;
      font-weight: bold;
      page-break-after: avoid;
      break-after: avoid-page;
    }}
    p.form-header {{
      margin: 0 0 12px 0;
      font-size: 17px;
      font-weight: bold;
    }}
    table.item-row {{
      width: 100%;
      border-collapse: collapse;
      margin: 0 0 20px 0;
      page-break-inside: avoid;
      break-inside: avoid-page;
    }}
    table.item-row td {{
      vertical-align: top;
    }}
    td.image-col {{
      width: 32%;
      padding: 8px 8px 8px 0;
      box-sizing: border-box;
    }}
    img.section-img {{
      width: {IMAGE_INSET_PT}pt;
      max-height: {IMAGE_MAX_HEIGHT_PT}pt;
      height: auto;
      display: block;
    }}
    div.image-empty {{
      min-height: 40pt;
    }}
    td.body-col {{
      width: 68%;
      padding: 8px 0 8px 4px;
    }}
    p.image-block {{
      margin: 8px 0 12px 0;
    }}
    p.image-block img {{
      max-width: 230px;
      height: auto;
    }}
    div.item-full-width {{
      clear: both;
      width: 100%;
      margin: 0 0 20px 0;
    }}
    p.closing-line {{
      clear: both;
      margin: 12px 0 0 0;
    }}
    div.easy-read-provision {{
      page-break-after: always;
      break-after: page;
      margin: 0 0 12pt 0;
    }}
    div.easy-read-frame {{
      border: 1.5pt solid #b8b0a4;
      background: #ffffff;
      padding: 14pt 16pt;
      box-sizing: border-box;
      margin: 0 0 12pt 0;
    }}
    div.easy-read-section {{
      margin: 0 0 4px 0;
    }}
    div.easy-read-section-lead {{
      page-break-inside: avoid;
      break-inside: avoid-page;
    }}
    div.easy-read-major-section {{
      page-break-before: always;
      break-before: page;
    }}
    div.easy-read-item {{
      page-break-inside: avoid;
      break-inside: avoid-page;
    }}
    """
    return css, archive


def _line_to_html(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or _SKIP_LINE.match(stripped):
        return None
    if stripped == "## 수정된 이지리드 번역본":
        return None
    if is_image_placeholder(stripped):
        return None

    if _is_heading(stripped):
        text = html.escape(_clean_heading(stripped))
        return f'<p class="heading">{text}</p>'

    chunks: list[str] = []
    for part, is_bold, size_pt in iter_styled_runs(stripped):
        escaped = html.escape(part)
        inner = f"<strong>{escaped}</strong>" if is_bold else escaped
        if size_pt != 12:
            inner = f'<span style="font-size:{int(size_pt)}px">{inner}</span>'
        chunks.append(inner)
    return f'<p class="body">{"".join(chunks)}</p>'


def _lines_to_html(lines: list[str]) -> str:
    return "".join(block for line in lines if (block := _line_to_html(line)))


def _image_to_img_tag(image_file: str, image_url: str | None = None) -> str | None:
    img_path = resolve_placement_image(image_file=image_file, image_url=image_url)
    if not img_path:
        return None
    mime = mimetypes.guess_type(str(img_path))[0] or "image/png"
    encoded = base64.b64encode(img_path.read_bytes()).decode("ascii")
    return f'<img src="data:{mime};base64,{encoded}" alt="" />'


def _placement_to_img_tag(placement: ImagePlacement) -> str | None:
    raw = (placement.image_base64 or "").strip()
    if raw:
        src = raw if raw.startswith("data:") else f"data:image/png;base64,{raw}"
        return (
            f'<img class="section-img" src="{src}" '
            f'width="{IMAGE_INSET_PT}" alt="" />'
        )
    file_tag = _image_to_img_tag(placement.image_file, placement.image_url)
    if not file_tag:
        return None
    return file_tag.replace("<img ", f'<img class="section-img" width="{IMAGE_INSET_PT}" ', 1)


def _item_row_html(
    lines: list[str],
    placement: ImagePlacement | None,
) -> str:
    """항목별 (삽화 | 글) 2단 — 그림 없어도 왼쪽 빈칸 유지."""
    body_html = _lines_to_html(lines)
    if not body_html:
        return ""

    img_tag: str | None = None
    if placement:
        img_tag = _placement_to_img_tag(placement)

    image_cell = img_tag if img_tag else '<div class="image-empty">&nbsp;</div>'
    return (
        '<table class="item-row"><tr>'
        f'<td class="image-col">{image_cell}</td>'
        f'<td class="body-col">{body_html}</td>'
        "</tr></table>"
    )


def _item_rows_html_for_item(item, by_item: dict) -> str:
    placement = by_item.get(item.start_line_index)
    if placement is not None and not isinstance(placement, ImagePlacement):
        placement = ImagePlacement(**placement)  # type: ignore[arg-type]
    parts: list[str] = []
    if placement:
        line_blocks = split_item_lines_into_blocks(item.lines)
        row = _item_row_html(line_blocks[0], placement)
        if row:
            parts.append(row)
        for block in line_blocks[1:]:
            follow = _item_row_html(block, None)
            if follow:
                parts.append(follow)
    else:
        row = _item_row_html(item.lines, None)
        if row:
            parts.append(row)
    return "".join(parts)


def _section_block_html(
    section,
    by_item: dict[int, ImagePlacement],
    *,
    major_page_break: bool = False,
) -> str:
    """소제목 + 항목마다 (삽화 | 글) — 소제목은 첫 항목과 같은 블록."""
    items = list(parse_section_items(section))
    chunks: list[str] = []
    heading_html = ""
    if section.heading:
        heading_html = _line_to_html(section.heading) or ""

    if section.heading and items:
        lead = heading_html + _item_rows_html_for_item(items[0], by_item)
        if lead.strip():
            major = " easy-read-major-section" if major_page_break else ""
            chunks.append(f'<div class="easy-read-section-lead{major}">{lead}</div>')
        for item in items[1:]:
            body = _item_rows_html_for_item(item, by_item)
            if body:
                chunks.append(f'<div class="easy-read-item">{body}</div>')
    else:
        inner: list[str] = []
        if heading_html:
            inner.append(heading_html)
        for item in items:
            body = _item_rows_html_for_item(item, by_item)
            if body:
                inner.append(body)
        if inner:
            chunks.append(f'<div class="easy-read-section">{"".join(inner)}</div>')

    return "".join(chunks)


def _build_html(
    doc: DocumentResponse,
    *,
    font_profile: ExportFontProfile | None = None,
) -> tuple[str, str]:
    body = _collect_body_text(doc)
    profile = font_profile or EASY_READ_FONT_PROFILE
    if not body:
        css, _ = _font_css(profile.east_asia, profile.body_pt)
        return "<body></body>", css

    export_body, closing = split_standard_closing(body)
    blocks: list[str] = []
    sections = parse_export_sections(export_body)
    raw_placements = _collect_placements(doc) or []
    filled = ensure_item_placements(export_body, raw_placements)
    placements = prepare_placements_for_export(export_body, filled)
    has_section_layout = any(section.heading for section in sections)

    if has_section_layout:
        by_item_raw = align_placements_one_per_section(export_body, placements)
        by_item = {
            k: (v if isinstance(v, ImagePlacement) else ImagePlacement(**v))  # type: ignore[arg-type]
            for k, v in by_item_raw.items()
        }
        major_section_ord = 0
        for section in sections:
            major_page = False
            if section.heading and is_major_section_page_break(section.heading):
                major_section_ord += 1
                major_page = major_section_ord >= 2
            section_html = _section_block_html(
                section, by_item, major_page_break=major_page
            )
            if section_html:
                blocks.append(section_html)
    elif placements:
        by_item_raw = align_placements_one_per_section(export_body, placements)
        by_item = {
            k: (v if isinstance(v, ImagePlacement) else ImagePlacement(**v))  # type: ignore[arg-type]
            for k, v in by_item_raw.items()
        }
        major_section_ord = 0
        for section in sections:
            major_page = False
            if section.heading and is_major_section_page_break(section.heading):
                major_section_ord += 1
                major_page = major_section_ord >= 2
            section_html = _section_block_html(
                section, by_item, major_page_break=major_page
            )
            if section_html:
                blocks.append(section_html)
    else:
        in_meta_section = False
        inserted_images: set[str] = set()
        for line in export_body.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("원본 파일:"):
                continue
            if stripped == "## 수정된 이지리드 번역본":
                continue
            if _META_SECTION_START.match(stripped):
                in_meta_section = True
                continue
            if in_meta_section:
                continue

            line_html = _line_to_html(line)
            if line_html:
                blocks.append(line_html)

            if len(inserted_images) >= MAX_IMAGES_PER_TEXT:
                continue
            for match in find_images_for_line(
                stripped,
                exclude=inserted_images,
                max_total=MAX_IMAGES_PER_TEXT,
            ):
                tag = _image_to_img_tag(match.image_file)
                if tag:
                    blocks.append(f'<p class="image-block">{tag}</p>')
                    inserted_images.add(match.image_file)

    css, _ = _font_css(profile.east_asia, profile.body_pt)
    if closing:
        closing_html = _line_to_html(closing)
        if closing_html:
            blocks.append(closing_html.replace('class="body"', 'class="body closing-line"', 1))
    content = "\n".join(blocks)
    framed = f'<div class="easy-read-frame">{content}</div>' if content.strip() else content
    return f"<html><head></head><body>{framed}</body></html>", css


def _provision_blocks_html() -> list[str]:
    from backend.services.judgment_merge import EASY_READ_PROVISION_PARAGRAPHS

    blocks: list[str] = []
    for block in EASY_READ_PROVISION_PARAGRAPHS:
        for line in block.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            cls = "body"
            if stripped.startswith("※") or stripped.startswith(("가.", "나.")):
                cls = "heading"
            blocks.append(f'<p class="{cls}">{html.escape(stripped)}</p>')
    return blocks


def _html_story_to_pdf(html_doc: str, css: str) -> bytes:
    _, archive = _font_css()
    story = fitz.Story(html=html_doc, user_css=css, archive=archive)
    mediabox = fitz.Rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT)
    content_rect = fitz.Rect(MARGIN, MARGIN, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN)

    out_path = Path(tempfile.mktemp(suffix=".pdf"))
    writer = fitz.DocumentWriter(str(out_path))
    more = 1
    try:
        while more:
            dev = writer.begin_page(mediabox)
            more, _ = story.place(content_rect)
            story.draw(dev)
            writer.end_page()
    finally:
        writer.close()

    try:
        return out_path.read_bytes()
    finally:
        try:
            out_path.unlink(missing_ok=True)
        except OSError:
            pass


def render_easy_read_insert_html_pdf(
    doc: DocumentResponse,
    *,
    font_profile: ExportFontProfile | None = None,
) -> bytes | None:
    profile = font_profile or EASY_READ_FONT_PROFILE
    body_html, css = _build_html(doc, font_profile=profile)
    if not body_html.strip():
        return None
    provision = "".join(_provision_blocks_html())
    if provision:
        provision = f'<div class="easy-read-provision">{provision}</div>'
    inner = body_html
    if provision and 'class="easy-read-frame"' in inner:
        inner = inner.replace(
            '<div class="easy-read-frame">',
            f'<div class="easy-read-frame">{provision}',
            1,
        )
    elif provision:
        inner = body_html.replace("<body>", f"<body>{provision}", 1)
    return _html_story_to_pdf(inner, css)


def _finalize_easy_read_only_pdf(pdf_bytes: bytes) -> bytes:
    """Word 표 테두리만 사용(PDF 위에 테두리를 겹쳐 그리지 않음)."""
    return pdf_bytes


def export_to_pdf(doc: DocumentResponse, *, source_file: Path | None = None) -> bytes:
    """이지리드 판결문만 PDF로 내보냄(원문 PDF 병합 없음)."""
    from backend.services import word_export
    from backend.services.docx_to_pdf import DocxToPdfError, convert_docx_bytes_to_pdf

    docx_bytes = word_export.export_to_docx(doc)
    try:
        return _finalize_easy_read_only_pdf(convert_docx_bytes_to_pdf(docx_bytes))
    except DocxToPdfError as exc:
        rendered = render_easy_read_insert_html_pdf(doc)
        if rendered:
            logger.warning("export pdf: easy-read only PyMuPDF fallback")
            return _finalize_easy_read_only_pdf(rendered)
        raise exc
