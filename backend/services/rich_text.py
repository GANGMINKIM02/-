"""이지리드 **강조**·<N>크기</N> 마크다운 파싱 (Word/PDF export 공통)."""

from __future__ import annotations

import re

STYLE_TOKEN = re.compile(r"\*\*(.+?)\*\*|<(\d+)>(.+?)</\2>")


def has_style_markers(text: str) -> bool:
    return bool(re.search(r"\*\*.+?\*\*", text)) or bool(re.search(r"<\d+>.+?</\d+>", text))


def iter_bold_runs(line: str) -> list[tuple[str, bool]]:
    """Return (text, is_bold) segments preserving order."""
    runs: list[tuple[str, bool]] = []
    for text, is_bold, _size in iter_styled_runs(line):
        runs.append((text, is_bold))
    return runs


def iter_styled_runs(line: str, *, default_pt: float = 12.0) -> list[tuple[str, bool, float]]:
    """Return (text, is_bold, size_pt) segments preserving order."""
    runs: list[tuple[str, bool, float]] = []
    pos = 0
    for match in STYLE_TOKEN.finditer(line):
        if match.start() > pos:
            plain = line[pos : match.start()]
            if plain:
                runs.append((plain, False, default_pt))
        if match.group(1) is not None:
            inner = match.group(1)
            for text, _, size_pt in iter_styled_runs(inner, default_pt=default_pt):
                runs.append((text, True, size_pt))
        else:
            size_pt = float(match.group(2))
            inner = match.group(3)
            runs.extend(iter_styled_runs(inner, default_pt=size_pt))
        pos = match.end()
    if pos < len(line):
        tail = line[pos:]
        if tail:
            runs.append((tail, False, default_pt))
    return runs
