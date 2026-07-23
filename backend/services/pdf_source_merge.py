from __future__ import annotations

"""PDF 원본(pdf2docx) 레이아웃 유지 + 「이유」 직후 이지리드 삽입."""

import io
import logging
import tempfile
from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from pdf2docx import Converter

from backend.models.schemas import DocumentResponse
from backend.services import word_export

logger = logging.getLogger(__name__)


def _insert_document_after(anchor_paragraph, insert_doc: Document) -> None:
    anchor = anchor_paragraph._element
    for block in insert_doc.element.body:
        if block.tag == qn("w:sectPr"):
            continue
        new_el = deepcopy(block)
        anchor.addnext(new_el)
        anchor = new_el


def merge_pdf_with_easy_read_insert(pdf_path: Path, doc: DocumentResponse) -> bytes | None:
    """PDF→DOCX 변환본에 이지리드 고지·본문만 끼워 넣는다. 실패 시 None."""
    if pdf_path.suffix.lower() != ".pdf" or not pdf_path.is_file():
        return None

    easy_body = word_export.collect_body_text(doc)
    if not easy_body:
        return None

    try:
        with tempfile.TemporaryDirectory() as tmp:
            converted = Path(tmp) / "source.docx"
            converter = Converter(str(pdf_path))
            try:
                converter.convert(str(converted), start=0, end=None)
            finally:
                converter.close()

            base = Document(str(converted))
            anchor = word_export.prepare_reason_insert_anchor(base)
            if anchor is None:
                logger.info("pdf merge: 「이유」 문단을 찾지 못함 — OCR 병합으로 폴백")
                return None

            font_profile = word_export.EASY_READ_FONT_PROFILE
            insert_doc = word_export.build_easy_read_insert_document(
                doc,
                font_profile=font_profile,
            )
            _insert_document_after(anchor, insert_doc)

            buffer = io.BytesIO()
            base.save(buffer)
            return buffer.getvalue()
    except Exception:
        logger.exception("pdf2docx merge failed")
        return None
