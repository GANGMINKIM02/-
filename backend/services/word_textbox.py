from __future__ import annotations

"""이지리드 삽입 블록 — 테두리 표(행마다 cantSplit → 소제목 블록 페이지 이월)."""

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

EASY_READ_BOX_FILL = "FFFFFF"
EASY_READ_BOX_BORDER = "B8B0A4"
EASY_READ_BOX_PAD_TWIPS = 180  # ~0.125"
# word_export PAGE_MARGIN 0.6in → 본문 폭(8.5in 기준)
EASY_READ_BOX_WIDTH_TWIPS = int((8.5 - 0.6 * 2) * 1440)


def _set_table_width_dxa(table, width_twips: int) -> None:
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    for child in list(tbl_pr):
        if child.tag == qn("w:tblW"):
            tbl_pr.remove(child)
    tbl_w = OxmlElement("w:tblW")
    tbl_w.set(qn("w:w"), str(width_twips))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_pr.insert(0, tbl_w)


def _set_table_layout_fixed(table) -> None:
    tbl_pr = table._tbl.tblPr
    for tag in ("w:tblLayout", "w:tblCellSpacing", "w:tblInd", "w:tblLook"):
        for child in list(tbl_pr):
            if child.tag == qn(tag):
                tbl_pr.remove(child)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)
    spacing = OxmlElement("w:tblCellSpacing")
    spacing.set(qn("w:w"), "0")
    spacing.set(qn("w:type"), "dxa")
    tbl_pr.append(spacing)
    tbl_ind = OxmlElement("w:tblInd")
    tbl_ind.set(qn("w:w"), "0")
    tbl_ind.set(qn("w:type"), "dxa")
    tbl_pr.append(tbl_ind)
    look = OxmlElement("w:tblLook")
    look.set(qn("w:val"), "0000")
    look.set(qn("w:firstRow"), "0")
    look.set(qn("w:lastRow"), "0")
    look.set(qn("w:firstColumn"), "0")
    look.set(qn("w:lastColumn"), "0")
    look.set(qn("w:noHBand"), "1")
    look.set(qn("w:noVBand"), "1")
    tbl_pr.append(look)


def _set_table_outer_borders(table, *, color: str = EASY_READ_BOX_BORDER, size: str = "8") -> None:
    tbl_pr = table._tbl.tblPr
    for child in list(tbl_pr):
        if child.tag == qn("w:tblBorders"):
            tbl_pr.remove(child)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:color"), color)
        borders.append(element)
    for edge in ("insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "nil")
        borders.append(element)
    tbl_pr.append(borders)


def _set_cell_borders_nil(cell) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    for child in list(tc_pr):
        if child.tag == qn("w:tcBorders"):
            tc_pr.remove(child)
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "nil")
        borders.append(element)
    tc_pr.append(borders)


def _set_cell_shading(cell, fill_hex: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    for child in list(tc_pr):
        if child.tag == qn("w:shd"):
            tc_pr.remove(child)
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill_hex)
    shading.set(qn("w:val"), "clear")
    tc_pr.append(shading)


def _set_cell_margins(cell, *, top: int = 0, bottom: int = 0, left: int = 0, right: int = 0) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    for child in list(tc_pr):
        if child.tag == qn("w:tcMar"):
            tc_pr.remove(child)
    tc_mar = OxmlElement("w:tcMar")
    for edge, value in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        node = OxmlElement(f"w:{edge}")
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")
        tc_mar.append(node)
    tc_pr.append(tc_mar)


def _set_row_cant_split(row) -> None:
    tr = row._tr
    tr_pr = tr.get_or_add_trPr()
    for child in list(tr_pr):
        if child.tag == qn("w:cantSplit"):
            tr_pr.remove(child)
    tr_pr.append(OxmlElement("w:cantSplit"))


def _prepare_easy_read_row_cell(cell) -> None:
    _set_cell_borders_nil(cell)
    _set_cell_shading(cell, EASY_READ_BOX_FILL)
    pad = EASY_READ_BOX_PAD_TWIPS
    _set_cell_margins(cell, top=pad, bottom=pad, left=pad, right=pad)


def begin_easy_read_outer_table(host: Document):
    """이지리드 전체를 감싸는 테두리 표 — 첫 행(고지 등)용 셀 반환."""
    table = host.add_table(rows=1, cols=1)
    table.autofit = False
    _set_table_width_dxa(table, EASY_READ_BOX_WIDTH_TWIPS)
    _set_table_layout_fixed(table)
    _set_table_outer_borders(table)
    row = table.rows[0]
    _set_row_cant_split(row)
    cell = row.cells[0]
    _prepare_easy_read_row_cell(cell)
    return table, cell


def append_easy_read_section_row(table):
    """소제목+본문 한 덩어리 — 남은 페이지에 안 들어가면 다음 페이지부터 시작."""
    row = table.add_row()
    _set_row_cant_split(row)
    cell = row.cells[0]
    _prepare_easy_read_row_cell(cell)
    return cell


def finish_easy_read_outer_table(host: Document) -> None:
    spacer = host.add_paragraph()
    spacer.paragraph_format.space_after = Pt(2)
