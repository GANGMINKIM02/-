from __future__ import annotations

"""이지리드 export 기본 글꼴 — 휴먼명조 (Word/PDF 공통)."""

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

BODY_PT_DEFAULT = 12.0

HUMAN_MYUNGJO_EAST = "휴먼명조"
HUMAN_MYUNGJO_ASCII = "Human Myeongjo"
HUMAN_MYUNGJO_CSS = "휴먼명조"

NANUM_MYUNGJO_REGULAR = FONT_DIR / "NanumMyeongjo-Regular.ttf"
NANUM_MYUNGJO_BOLD = FONT_DIR / "NanumMyeongjo-Bold.ttf"

# PyMuPDF HTML 폴백: 휴먼명조 TTF가 없을 때 나눔명조로 @font-face 대체
STORY_FALLBACK_TTF = NANUM_MYUNGJO_REGULAR
STORY_FALLBACK_BOLD = NANUM_MYUNGJO_BOLD

_WINDOWS_HUMAN_TTF_NAMES = (
    "H2MJR.TTF",
    "H2MJM.TTF",
    "H2MJB.TTF",
    "HMJRE.TTF",
    "HMJME.TTF",
    "HMJBE.TTF",
)


@dataclass(frozen=True)
class ExportFontProfile:
    ascii: str = HUMAN_MYUNGJO_ASCII
    h_ansi: str = HUMAN_MYUNGJO_ASCII
    east_asia: str = HUMAN_MYUNGJO_EAST
    body_pt: float = BODY_PT_DEFAULT


def bundled_court_font_profile() -> ExportFontProfile:
    return ExportFontProfile(
        ascii=HUMAN_MYUNGJO_ASCII,
        h_ansi=HUMAN_MYUNGJO_ASCII,
        east_asia=HUMAN_MYUNGJO_EAST,
        body_pt=BODY_PT_DEFAULT,
    )


def _windows_human_myeongjo_files() -> list[Path]:
    if sys.platform != "win32":
        return []
    fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    found: list[Path] = []
    for name in _WINDOWS_HUMAN_TTF_NAMES:
        path = fonts_dir / name
        if path.is_file():
            found.append(path)
    return found


def bundled_font_files() -> list[Path]:
    files = _windows_human_myeongjo_files()
    if STORY_FALLBACK_TTF.is_file():
        files.append(STORY_FALLBACK_TTF)
    if STORY_FALLBACK_BOLD.is_file():
        files.append(STORY_FALLBACK_BOLD)
    return files


def css_font_family_stack() -> str:
    return f'"{HUMAN_MYUNGJO_CSS}", "Human Myeongjo", "Nanum Myeongjo", "Batang", serif'


def story_font_face_css() -> str:
    """PyMuPDF: family 이름은 휴먼명조, TTF는 Windows 휴먼명조 또는 나눔명조."""
    human = _windows_human_myeongjo_files()
    regular = human[0] if human else STORY_FALLBACK_TTF
    bold = None
    for path in human:
        if "B" in path.stem.upper() or path.name.upper().startswith("H2MJB"):
            bold = path
            break
    if bold is None and STORY_FALLBACK_BOLD.is_file():
        bold = STORY_FALLBACK_BOLD

    if not regular.is_file():
        return ""

    family = HUMAN_MYUNGJO_CSS
    lines = [
        f"""
    @font-face {{
      font-family: "{family}";
      src: url("{regular.name}");
      font-weight: normal;
    }}"""
    ]
    if bold and bold.is_file():
        lines.append(
            f"""
    @font-face {{
      font-family: "{family}";
      src: url("{bold.name}");
      font-weight: bold;
    }}"""
        )
    return "".join(lines)


def enable_word_font_embedding(document: Document) -> None:
    root = document.settings.element
    for child in list(root):
        if child.tag in (qn("w:embedTrueTypeFonts"), qn("w:embedSystemFonts")):
            root.remove(child)
    embed_tt = OxmlElement("w:embedTrueTypeFonts")
    embed_tt.set(qn("w:val"), "true")
    embed_sys = OxmlElement("w:embedSystemFonts")
    embed_sys.set(qn("w:val"), "false")
    root.append(embed_tt)
    root.append(embed_sys)


def is_known_export_font_name(name: str) -> bool:
    key = (name or "").strip().lower()
    if not key:
        return False
    known = (
        "휴먼명조",
        "human myeongjo",
        "humanmyeongjo",
        "h2mjr",
        "nanum myeongjo",
        "나눔명조",
        "kopub",
        "courtbt",
        "바탕",
        "batang",
    )
    return any(k in key for k in known)


def register_bundled_fonts_for_process() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        import shutil

        gdi32 = ctypes.WinDLL("gdi32")
        add = gdi32.AddFontResourceExW
        add.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p]
        add.restype = ctypes.c_int
        FR_PRIVATE = 0x10

        story_dir = FONT_DIR
        story_dir.mkdir(parents=True, exist_ok=True)

        for src in bundled_font_files():
            path = src
            if src.parent != story_dir and src.name not in {p.name for p in story_dir.glob("*.ttf")}:
                dest = story_dir / src.name
                if not dest.exists():
                    try:
                        shutil.copy2(src, dest)
                    except OSError:
                        pass
                path = dest if dest.is_file() else src
            added = add(str(path.resolve()), FR_PRIVATE, None)
            if added:
                logger.info("registered export font: %s", path.name)
    except Exception:
        logger.exception("font registration failed")
