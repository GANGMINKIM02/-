/** 이지리드 서식(**굵게**, <14>크기</14>) 편집·렌더 유틸 */

import {
  isSectionHeading,
  parseSectionItems,
  parseTranslationSections,
} from "./translationSections";

/** Word 글꼴 크기 프리셋 */
export const FONT_SIZE_PRESETS = [
  8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72,
] as const;

export type FontSizePt = number;

export const DEFAULT_FONT_SIZE = 12;
export const MIN_FONT_SIZE = 8;
export const MAX_FONT_SIZE = 72;

/** @deprecated FONT_SIZE_PRESETS 사용 */
export const FONT_SIZE_OPTIONS = [12, 14, 17] as const;

const STYLE_TOKEN = /(\*\*(?:\\.|[^*])+\*\*|<(\d+)>(?:\\.|[^<])+<\/\2>)/g;

const BOLD_INNER = /^\*\*(.+)\*\*$/;
const SIZE_INNER = /^<(\d+)>(.+)<\/\1>$/;

export function clampFontSize(value: number): FontSizePt {
  if (!Number.isFinite(value)) return DEFAULT_FONT_SIZE;
  return Math.min(MAX_FONT_SIZE, Math.max(MIN_FONT_SIZE, Math.round(value)));
}

export function hasStyleMarkers(text: string): boolean {
  return /\*\*.+?\*\*/.test(text) || /<\d+>.+?<\/\d+>/.test(text);
}

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export type StyledPart = {
  text: string;
  bold: boolean;
  sizePt: FontSizePt;
};

export function parseStyledParts(text: string, defaultSize: FontSizePt = DEFAULT_FONT_SIZE): StyledPart[] {
  const parts: StyledPart[] = [];
  let last = 0;
  let match: RegExpExecArray | null;

  const re = new RegExp(STYLE_TOKEN.source, "g");
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      const plain = text.slice(last, match.index);
      if (plain) parts.push({ text: plain, bold: false, sizePt: defaultSize });
    }
    const token = match[0];
    const boldMatch = token.match(BOLD_INNER);
    if (boldMatch) {
      parts.push(...parseStyledParts(boldMatch[1], defaultSize).map((p) => ({ ...p, bold: true })));
    } else {
      const sizeMatch = token.match(SIZE_INNER);
      if (sizeMatch) {
        const sizePt = clampFontSize(Number(sizeMatch[1]));
        parts.push(...parseStyledParts(sizeMatch[2], sizePt));
      }
    }
    last = match.index + token.length;
  }

  if (last < text.length) {
    const tail = text.slice(last);
    if (tail) parts.push({ text: tail, bold: false, sizePt: defaultSize });
  }
  return parts;
}

function markersLineToHtmlDiv(line: string): string {
  if (!line) return "<div><br></div>";
  if (isSectionHeading(line) && !hasStyleMarkers(line)) {
    const inner = escapeHtml(line.replace(/^#+\s*/, "").trim());
    return `<div data-er-heading="1" style="font-size:17px;font-weight:bold;margin-top:8px">${inner}</div>`;
  }
  const html = parseStyledParts(line)
    .map(({ text: chunk, bold, sizePt }) => {
      let inner = escapeHtml(chunk);
      if (bold) inner = `<strong>${inner}</strong>`;
      if (sizePt !== DEFAULT_FONT_SIZE) {
        inner = `<span data-font-pt="${sizePt}" style="font-size:${sizePt}px">${inner}</span>`;
      }
      return inner;
    })
    .join("");
  return `<div>${html || "<br>"}</div>`;
}

const EXPORT_PREVIEW_IMAGE_SLOT =
  '<div contenteditable="false" class="er-export-img-slot"><span>그림 영역<br>(그림·추출과 동일)</span></div>';

/** 번역 탭 export-preview — 소제목 전체 너비, 항목마다 왼쪽 그림 영역 */
export function exportPreviewBodyToHtml(body: string): string {
  if (!body.trim()) return "";

  const sections = parseTranslationSections(body);
  const parts: string[] = [];

  for (const section of sections) {
    if (section.heading) {
      parts.push(markersLineToHtmlDiv(section.heading));
    }
    for (const item of parseSectionItems(section)) {
      const itemHtml = item.lines.map((line) => markersLineToHtmlDiv(line)).join("");
      parts.push(
        `<div class="er-export-item-row" data-er-item-row="1">${EXPORT_PREVIEW_IMAGE_SLOT}<div class="er-export-item-body min-w-0">${itemHtml}</div></div>`,
      );
    }
  }

  return parts.join("");
}

function markersFromLineElement(el: HTMLElement): string {
  return Array.from(el.childNodes)
    .map((n) => nodeToMarkers(n, { bold: false, sizePt: DEFAULT_FONT_SIZE }))
    .join("");
}

/** export-preview 편집 DOM → 저장 형식 */
export function htmlToMarkersExportPreview(html: string): string {
  const doc = new DOMParser().parseFromString(`<body>${html}</body>`, "text/html");
  const lines: string[] = [];

  for (const child of Array.from(doc.body.children)) {
    const el = child as HTMLElement;
    if (el.dataset.erHeading === "1") {
      lines.push(markersFromLineElement(el));
      continue;
    }
    if (el.dataset.erItemRow === "1") {
      const bodyEl = el.querySelector(".er-export-item-body");
      if (bodyEl) {
        for (const lineEl of Array.from(bodyEl.children)) {
          if (lineEl instanceof HTMLElement && lineEl.tagName === "DIV") {
            lines.push(markersFromLineElement(lineEl));
          }
        }
      }
      continue;
    }
    if (el.tagName === "DIV") {
      lines.push(markersFromLineElement(el));
    }
  }

  return lines.join("\n").replace(/\n+$/, "");
}

/** 저장 형식 → WYSIWYG HTML */
export function markersToHtml(text: string): string {
  if (!text) return "";
  return text.split("\n").map((line) => markersLineToHtmlDiv(line)).join("");
}

function parseFontPt(el: HTMLElement): FontSizePt | null {
  const data = el.dataset.fontPt;
  if (data && /^\d+$/.test(data)) {
    return clampFontSize(Number(data));
  }
  const px = el.style.fontSize;
  if (px.endsWith("px")) {
    return clampFontSize(Math.round(Number(px.replace("px", ""))));
  }
  return null;
}

function nodeToMarkers(node: Node, ctx: { bold: boolean; sizePt: FontSizePt }): string {
  if (node.nodeType === Node.TEXT_NODE) {
    const raw = node.textContent ?? "";
    if (!raw) return "";
    let out = raw;
    if (ctx.bold) out = `**${out}**`;
    if (ctx.sizePt !== DEFAULT_FONT_SIZE) out = `<${ctx.sizePt}>${out}</${ctx.sizePt}>`;
    return out;
  }

  if (node.nodeType !== Node.ELEMENT_NODE) return "";

  const el = node as HTMLElement;
  if (el.tagName === "BR") return "\n";

  const nextCtx = { ...ctx };
  if (el.tagName === "STRONG" || el.tagName === "B") nextCtx.bold = true;
  const fontPt = parseFontPt(el);
  if (fontPt) nextCtx.sizePt = fontPt;

  if (el.tagName === "DIV" || el.tagName === "P") {
    const inner = Array.from(el.childNodes).map((child) => nodeToMarkers(child, ctx)).join("");
    return inner + "\n";
  }

  return Array.from(el.childNodes).map((child) => nodeToMarkers(child, nextCtx)).join("");
}

/** WYSIWYG HTML → 저장 형식 */
export function htmlToMarkers(html: string): string {
  const doc = new DOMParser().parseFromString(`<body>${html}</body>`, "text/html");
  const body = doc.body;
  const lines: string[] = [];

  for (const child of Array.from(body.childNodes)) {
    if (child.nodeType === Node.ELEMENT_NODE && (child as HTMLElement).tagName === "DIV") {
      const line = Array.from(child.childNodes)
        .map((n) => nodeToMarkers(n, { bold: false, sizePt: DEFAULT_FONT_SIZE }))
        .join("");
      lines.push(line);
    } else {
      const chunk = nodeToMarkers(child, { bold: false, sizePt: DEFAULT_FONT_SIZE });
      if (chunk.endsWith("\n")) lines.push(chunk.slice(0, -1));
      else if (chunk) lines.push(chunk);
    }
  }

  return lines.join("\n").replace(/\n+$/, "");
}

export function hasBoldMarkers(text: string): boolean {
  return /\*\*.+?\*\*/.test(text);
}
