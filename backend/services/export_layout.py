from __future__ import annotations

"""이지리드 export용 섹션·항목 파싱 (프론트 translationSections와 동일 규칙)."""

import re
from dataclasses import dataclass

from backend.services.image_matcher import preview_lines

_IMAGE_PLACEHOLDER = re.compile(r"^\[image\]\s*$", re.I)
_NUMBERED_ITEM = re.compile(r"^\s*\d+[\)\.]\s")
_ORDINAL_START = re.compile(r"^\s*(?:첫째|둘째|셋째|넷째|다섯째|여섯째)\b")


@dataclass(frozen=True)
class ExportSection:
    heading: str | None
    body_lines: list[str]
    start_line_index: int


@dataclass(frozen=True)
class ExportItem:
    """양식 PDF: 1., 2. 등 번호 항목마다 (삽화 | 글) 2단."""

    lines: list[str]
    start_line_index: int


def is_image_placeholder(line: str) -> bool:
    return bool(_IMAGE_PLACEHOLDER.match(line.strip()))


def is_section_heading(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("<") and stripped.endswith(">"):
        return True
    if stripped.startswith("■"):
        return True
    return stripped.startswith("#")


def _line_for_item_detection(line: str) -> str:
    """**굵게** 등 마크다운 제거 후 번호/첫째·둘째 항목 판별."""
    return re.sub(r"\*+", "", line.strip()).strip()


def is_numbered_item_line(line: str) -> bool:
    stripped = _line_for_item_detection(line)
    if _NUMBERED_ITEM.match(stripped):
        return True
    return bool(_ORDINAL_START.match(stripped))


def split_item_lines_into_blocks(lines: list[str]) -> list[list[str]]:
    """그림 2단은 첫 블록만 — 2./둘째 이후는 별도 행(왼쪽 빈칸 + 오른쪽 본문)."""
    if not lines:
        return []
    blocks: list[list[str]] = []
    current: list[str] = []
    for i, line in enumerate(lines):
        if i > 0 and is_numbered_item_line(line):
            if current:
                blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks if len(blocks) > 1 else [lines]


def parse_section_items(section: ExportSection) -> list[ExportItem]:
    body = section.body_lines
    if not body:
        return []

    body_start = section.start_line_index + (1 if section.heading else 0)
    has_numbered = any(is_numbered_item_line(line) for line in body)

    if not has_numbered:
        return [ExportItem(lines=list(body), start_line_index=body_start)]

    items: list[ExportItem] = []
    current: list[str] = []
    current_start = body_start

    for offset, line in enumerate(body):
        global_idx = body_start + offset
        if is_numbered_item_line(line):
            if current:
                items.append(ExportItem(lines=current, start_line_index=current_start))
            current = [line]
            current_start = global_idx
        else:
            if not current:
                current_start = global_idx
            current.append(line)

    if current:
        items.append(ExportItem(lines=current, start_line_index=current_start))

    return items


def parse_export_sections(text: str) -> list[ExportSection]:
    lines = preview_lines(text)
    if not lines:
        return []

    sections: list[ExportSection] = []
    index = 0
    while index < len(lines):
        if is_section_heading(lines[index]):
            heading = lines[index]
            start = index
            index += 1
            body: list[str] = []
            while index < len(lines) and not is_section_heading(lines[index]):
                line = lines[index]
                if not is_image_placeholder(line):
                    body.append(line)
                index += 1
            sections.append(ExportSection(heading=heading, body_lines=body, start_line_index=start))
            continue

        start = index
        body = []
        while index < len(lines) and not is_section_heading(lines[index]):
            line = lines[index]
            if not is_image_placeholder(line):
                body.append(line)
            index += 1
        sections.append(ExportSection(heading=None, body_lines=body, start_line_index=start))

    return sections


def _normalize_heading(text: str) -> str:
    return text.strip().lstrip("#").strip()


_MAJOR_SECTION_PAGE = re.compile(
    r"이\s*판결의\s*결론|"
    r"검사가\s*요구|"
    r"소송에서\s*검사|"
    r"이런\s*결론을\s*내린\s*이유",
    re.I,
)


def is_major_section_page_break(heading: str | None) -> bool:
    """결론·검사 청구·이유 등 — 추출 시 새 페이지에서 시작."""
    if not heading:
        return False
    inner = _normalize_heading(heading.strip("<>").strip())
    return bool(_MAJOR_SECTION_PAGE.search(inner))


def prepare_placements_for_export(body: str, placements: list) -> list:
    """항목(line_index)별 배치 유지. section_heading 수동 배치 우선."""
    from backend.models.schemas import ImagePlacement

    if not placements:
        return []

    typed = [p if isinstance(p, ImagePlacement) else ImagePlacement(**p) for p in placements]
    manual = [p for p in typed if p.section_heading]
    source = manual if manual else typed

    by_line: dict[int, ImagePlacement] = {}
    for placement in sorted(source, key=lambda p: p.line_index):
        by_line[placement.line_index] = placement
    return list(by_line.values())


def align_placements_to_items(body: str, placements: list) -> dict[int, object]:
    """Map placements to ExportItem.start_line_index (양식: 항목마다 삽화)."""
    from backend.models.schemas import ImagePlacement

    if not placements:
        return {}

    sections = parse_export_sections(body)
    typed = [p if isinstance(p, ImagePlacement) else ImagePlacement(**p) for p in placements]

    item_refs: list[tuple[ExportSection, ExportItem]] = []
    for section in sections:
        for item in parse_section_items(section):
            item_refs.append((section, item))

    if not item_refs:
        return {}

    by_item: dict[int, ImagePlacement] = {}
    used: set[str] = set()

    for placement in typed:
        if placement.id in used:
            continue
        assigned = False

        for _section, item in item_refs:
            if placement.line_index == item.start_line_index:
                by_item[item.start_line_index] = placement
                used.add(placement.id)
                assigned = True
                break
        if assigned:
            continue

        _section, nearest = min(
            item_refs,
            key=lambda ref: abs(ref[1].start_line_index - placement.line_index),
        )
        if nearest.start_line_index not in by_item:
            by_item[nearest.start_line_index] = placement
            used.add(placement.id)

    return by_item


def align_placements_one_per_section(body: str, placements: list) -> dict[int, object]:
    """소제목(섹션)마다 첫 번째 항목에만 대표 삽화 1장."""
    from backend.models.schemas import ImagePlacement

    if not placements:
        return {}

    prepared = prepare_placements_for_export(body, placements)
    by_item = align_placements_to_items(body, prepared)
    sections = parse_export_sections(body)
    result: dict[int, ImagePlacement] = {}

    for section in sections:
        items = parse_section_items(section)
        if not items:
            continue
        first_idx = items[0].start_line_index
        chosen: ImagePlacement | None = None

        raw = by_item.get(first_idx)
        if raw is not None:
            chosen = raw if isinstance(raw, ImagePlacement) else ImagePlacement(**raw)  # type: ignore[arg-type]
        else:
            for item in items:
                raw = by_item.get(item.start_line_index)
                if raw is not None:
                    chosen = raw if isinstance(raw, ImagePlacement) else ImagePlacement(**raw)  # type: ignore[arg-type]
                    break

        if chosen is None:
            continue
        if chosen.line_index != first_idx:
            chosen = chosen.model_copy(update={"line_index": first_idx})
        result[first_idx] = chosen

    return result


def align_placements_to_section_headings(body: str, placements: list) -> dict[int, object]:
    """소제목 줄(line_index)에 배치된 대표 그림."""
    from backend.models.schemas import ImagePlacement

    if not placements:
        return {}

    sections = parse_export_sections(body)
    section_starts = {section.start_line_index for section in sections if section.heading}
    typed = [p if isinstance(p, ImagePlacement) else ImagePlacement(**p) for p in placements]

    by_section: dict[int, ImagePlacement] = {}
    for placement in typed:
        if placement.line_index in section_starts:
            by_section[placement.line_index] = placement
    return by_section


def align_placements_to_sections(
    body: str,
    placements: list,
) -> dict[int, list]:
    """Legacy: section-level map (PDF 호환). 항목 배치를 섹션 start에 모음."""
    from backend.models.schemas import ImagePlacement

    sections = parse_export_sections(body)
    by_item = align_placements_to_items(body, placements)
    by_section: dict[int, list[ImagePlacement]] = {
        section.start_line_index: [] for section in sections
    }

    for section in sections:
        for item in parse_section_items(section):
            placement = by_item.get(item.start_line_index)
            if placement and isinstance(placement, ImagePlacement):
                by_section[section.start_line_index].append(placement)

    return by_section
