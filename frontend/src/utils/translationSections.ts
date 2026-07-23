/**
 * 이지리드 번역문을 소제목·번호 항목 단위로 분해 (작성양식 PDF 구조).
 */
import type { ImagePlacement } from "../api/client";
import { filterPreviewLines } from "./sanitizeTranslation";

export interface TranslationSection {
  heading: string | null;
  bodyLines: string[];
  /** image_placements.line_index 와 매칭 (섹션 제목 또는 항목 시작) */
  startLineIndex: number;
}

/** 양식: 1., 2. 등 번호 항목 — 각각 (삽화 | 글) 2단 */
export interface TranslationItem {
  lines: string[];
  startLineIndex: number;
}

export const STANDARD_CLOSING =
  "더 궁금한 것이 있으면 **소송구조 변호사**님에게 문의해 주세요.";

const NUMBERED_ITEM = /^\s*\d+[\).]\s/;
const ORDINAL_START = /^\s*(?:첫째|둘째|셋째|넷째|다섯째|여섯째)\b/;
const CLOSING_CONTACT = /더\s*궁금한\s*것이\s*있으면.*문의/;

function lineForItemDetection(line: string): string {
  return line.trim().replace(/\*+/g, "").trim();
}

function closingPlain(line: string): string {
  return line.replace(/\*+/g, "").trim();
}

export function isStandardClosingLine(line: string): boolean {
  return closingPlain(line) === closingPlain(STANDARD_CLOSING);
}

/** export·미리보기: 마무리 문장은 2단(그림) 레이아웃 밖 */
export function splitStandardClosing(text: string): { body: string; closing: string | null } {
  const lines = text.split("\n");
  while (lines.length && !lines[lines.length - 1]?.trim()) {
    lines.pop();
  }
  if (!lines.length) {
    return { body: "", closing: null };
  }

  const last = lines[lines.length - 1].trim();
  if (isStandardClosingLine(last) || CLOSING_CONTACT.test(last)) {
    lines.pop();
    while (lines.length && !lines[lines.length - 1]?.trim()) {
      lines.pop();
    }
    return { body: lines.join("\n"), closing: last };
  }

  return { body: text, closing: null };
}

export function mergeWithStandardClosing(body: string, closing: string | null): string {
  const trimmed = body.replace(/\s+$/, "");
  if (!closing) return trimmed;
  if (!trimmed) return closing;
  return `${trimmed}\n\n${closing}`;
}

export function isSectionHeading(line: string): boolean {
  const s = line.trim();
  return (
    (s.startsWith("<") && s.endsWith(">")) ||
    s.startsWith("■") ||
    s.startsWith("#")
  );
}

export function isNumberedItemLine(line: string): boolean {
  const stripped = lineForItemDetection(line);
  return NUMBERED_ITEM.test(stripped) || ORDINAL_START.test(stripped);
}

export function splitItemLinesIntoBlocks(lines: string[]): string[][] {
  if (lines.length === 0) return [];
  const blocks: string[][] = [];
  let current: string[] = [];
  lines.forEach((line, i) => {
    if (i > 0 && isNumberedItemLine(line)) {
      if (current.length) blocks.push(current);
      current = [line];
    } else {
      current.push(line);
    }
  });
  if (current.length) blocks.push(current);
  return blocks.length > 1 ? blocks : [lines];
}

export function parseSectionItems(section: TranslationSection): TranslationItem[] {
  const body = section.bodyLines;
  if (body.length === 0) return [];

  const bodyStart = section.startLineIndex + (section.heading ? 1 : 0);
  const hasNumbered = body.some(isNumberedItemLine);

  if (!hasNumbered) {
    return [{ lines: [...body], startLineIndex: bodyStart }];
  }

  const items: TranslationItem[] = [];
  let current: string[] = [];
  let currentStart = bodyStart;

  body.forEach((line, offset) => {
    const globalIdx = bodyStart + offset;
    if (isNumberedItemLine(line)) {
      if (current.length) {
        items.push({ lines: current, startLineIndex: currentStart });
      }
      current = [line];
      currentStart = globalIdx;
    } else {
      if (!current.length) currentStart = globalIdx;
      current.push(line);
    }
  });

  if (current.length) {
    items.push({ lines: current, startLineIndex: currentStart });
  }

  return items;
}

export function parseTranslationSections(text: string): TranslationSection[] {
  const lines = filterPreviewLines(text);
  if (lines.length === 0) return [];

  const sections: TranslationSection[] = [];
  let i = 0;

  while (i < lines.length) {
    if (isSectionHeading(lines[i])) {
      const heading = lines[i];
      const startLineIndex = i;
      i += 1;
      const bodyLines: string[] = [];
      while (i < lines.length && !isSectionHeading(lines[i])) {
        bodyLines.push(lines[i]);
        i += 1;
      }
      sections.push({ heading, bodyLines, startLineIndex });
    } else {
      const startLineIndex = i;
      const bodyLines: string[] = [];
      while (i < lines.length && !isSectionHeading(lines[i])) {
        bodyLines.push(lines[i]);
        i += 1;
      }
      sections.push({ heading: null, bodyLines, startLineIndex });
    }
  }

  return sections;
}

export function sectionsToTranslationText(sections: TranslationSection[]): string {
  const lines: string[] = [];
  for (const section of sections) {
    if (section.heading) lines.push(section.heading);
    lines.push(...section.bodyLines);
  }
  return lines.join("\n");
}

export function formatHeadingDisplay(line: string): string {
  return line.replace(/^#+\s*/, "").trim();
}

export function normalizeSectionHeading(text: string): string {
  return text.trim().replace(/^#+\s*/, "").trim();
}

export function findSectionForLineIndex(
  text: string,
  lineIndex: number,
): TranslationSection | undefined {
  return parseTranslationSections(text).find((section) => {
    if (section.startLineIndex === lineIndex) return true;
    const bodyStart = section.startLineIndex + (section.heading ? 1 : 0);
    const bodyEnd = bodyStart + section.bodyLines.length;
    return lineIndex >= bodyStart && lineIndex < bodyEnd;
  });
}

/** 그림 탭·추출 — 항목 startLineIndex 기준 (저장 line_index 불일치 시 정렬). */
export function alignPlacementsToItems(
  text: string,
  placements: ImagePlacement[],
): Map<number, ImagePlacement> {
  const { body } = splitStandardClosing(text);
  const sections = parseTranslationSections(body);
  const itemRefs: { section: TranslationSection; item: TranslationItem }[] = [];
  for (const section of sections) {
    for (const item of parseSectionItems(section)) {
      itemRefs.push({ section, item });
    }
  }
  if (!itemRefs.length || !placements.length) {
    return new Map();
  }

  const enriched = enrichPlacementsWithHeadings(body, placements);
  const byItem = new Map<number, ImagePlacement>();
  const used = new Set<string>();

  for (const placement of enriched) {
    if (used.has(placement.id)) continue;
    let assigned = false;

    for (const { item } of itemRefs) {
      if (placement.line_index === item.startLineIndex) {
        byItem.set(item.startLineIndex, placement);
        used.add(placement.id);
        assigned = true;
        break;
      }
    }
    if (assigned) continue;

    if (placement.section_heading) {
      const headingKey = normalizeSectionHeading(placement.section_heading);
      for (const { section, item } of itemRefs) {
        if (!section.heading) continue;
        if (normalizeSectionHeading(section.heading) !== headingKey) continue;
        const first = parseSectionItems(section)[0];
        if (!first || first.startLineIndex !== item.startLineIndex) continue;
        if (byItem.has(item.startLineIndex)) continue;
        byItem.set(item.startLineIndex, { ...placement, line_index: item.startLineIndex });
        used.add(placement.id);
        assigned = true;
        break;
      }
    }
    if (assigned) continue;

    const nearest = itemRefs.reduce((best, ref) =>
      Math.abs(ref.item.startLineIndex - placement.line_index) <
      Math.abs(best.item.startLineIndex - placement.line_index)
        ? ref
        : best,
    );
    if (!byItem.has(nearest.item.startLineIndex)) {
      byItem.set(nearest.item.startLineIndex, {
        ...placement,
        line_index: nearest.item.startLineIndex,
      });
      used.add(placement.id);
    }
  }

  return byItem;
}

/** 소제목(섹션)마다 첫 항목에만 대표 삽화 1장 — 추출·미리보기용. */
export function alignPlacementsOnePerSection(
  text: string,
  placements: ImagePlacement[],
): Map<number, ImagePlacement> {
  const { body } = splitStandardClosing(text);
  const byItem = alignPlacementsToItems(body, placements);
  const sections = parseTranslationSections(body);
  const result = new Map<number, ImagePlacement>();

  for (const section of sections) {
    const items = parseSectionItems(section);
    if (!items.length) continue;
    const firstIdx = items[0].startLineIndex;
    let chosen = byItem.get(firstIdx);
    if (!chosen) {
      for (const item of items) {
        const p = byItem.get(item.startLineIndex);
        if (p) {
          chosen = p;
          break;
        }
      }
    }
    if (!chosen) continue;
    result.set(
      firstIdx,
      chosen.line_index === firstIdx ? chosen : { ...chosen, line_index: firstIdx },
    );
  }

  return result;
}

export function resolvePlacementForItem(
  text: string,
  placements: ImagePlacement[],
  item: TranslationItem,
): ImagePlacement | undefined {
  return alignPlacementsToItems(text, placements).get(item.startLineIndex);
}

/** @deprecated 섹션 대표 그림은 해당 섹션 첫 항목 line_index에 배치 */
export function resolvePlacementForSectionHeading(
  text: string,
  placements: ImagePlacement[],
  section: TranslationSection,
): ImagePlacement | undefined {
  const items = parseSectionItems(section);
  if (!items.length) return undefined;
  return resolvePlacementForItem(text, placements, items[0]);
}

/** @deprecated 섹션 단위 — resolvePlacementForSectionHeading 사용 */
export function resolvePlacementForSection(
  text: string,
  placements: ImagePlacement[],
  section: TranslationSection,
): ImagePlacement | undefined {
  return resolvePlacementForSectionHeading(text, placements, section);
}

/** 추출용 — line_index별 배치 유지·정렬. */
export function filterPlacementsForExport(
  text: string,
  placements: ImagePlacement[],
): ImagePlacement[] {
  if (!placements.length) return [];
  const { body } = splitStandardClosing(text);
  const aligned = alignPlacementsToItems(body, placements);
  return Array.from(aligned.values()).sort((a, b) => a.line_index - b.line_index);
}

export function enrichPlacementsWithHeadings(
  text: string,
  placements: ImagePlacement[],
): ImagePlacement[] {
  if (!placements.length) return placements;
  return placements.map((p) => {
    if (p.section_heading) return p;
    const section = findSectionForLineIndex(text, p.line_index);
    if (section?.heading) return { ...p, section_heading: section.heading };
    return p;
  });
}
