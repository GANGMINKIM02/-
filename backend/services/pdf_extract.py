from __future__ import annotations

"""로컬 PDF 텍스트 추출 (OCR API 미사용 시 폴백).

역할: PyMuPDF(fitz)로 PDF에서 페이지별 텍스트를 추출한다.
주요 기능: extract_pdf_pages (텍스트 부족 시 None 반환).
관계: upstage.extract_text_from_file(PDF 처리 시 1차 시도).
"""

from pathlib import Path


def extract_pdf_pages(file_path: Path) -> tuple[list[str], str] | None:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None

    try:
        doc = fitz.open(file_path)
    except Exception:
        return None

    pages: list[str] = []
    for i in range(doc.page_count):
        text = doc[i].get_text("text").strip()
        pages.append(text if text else f"(페이지 {i + 1} — 추출된 텍스트 없음)")
    doc.close()

    full = "\n\n".join(pages).strip()
    if len(full.replace("— 추출된 텍스트 없음", "")) < 30:
        return None
    return pages, full
