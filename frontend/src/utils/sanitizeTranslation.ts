/**
 * AI 번역 텍스트 후처리 유틸.
 *
 * 역할: LLM이 붙인 수정 사항 메타 헤더·문서 표지 제목을 제거하고 결론 섹션을 앞으로 정렬한다.
 * 주요 기능: sanitizeTranslationText, filterPreviewLines.
 * 연관 파일: components/TranslationSegment.tsx, pages/TranslatePage.tsx
 */

const META_SECTION_START = /^###\s*수정\s*사항/;
const IMAGE_PLACEHOLDER = /^\[image\]\s*$/i;
const DOC_TITLE_LINE =
  /^#?\s*<[^>]*(?:형사|민사|가사|행정)판결\s*이지리드/i;
const DOC_TITLE_EASY_READ = /^#?\s*<[^>]*이지리드\s*[—\-–]/i;
const DOC_META_HEADING = /^#?\s*<[^>]*(?:작성\s*요점|작성요점)[^>]*>/i;

function isSectionHeading(line: string): boolean {
  const stripped = line.trim().replace(/^#+\s*/, "");
  if (stripped.startsWith("<") && stripped.endsWith(">")) return true;
  return stripped.startsWith("■");
}

function isConclusionHeading(line: string): boolean {
  const text = line.trim();
  if (
    text.includes("원하는 것과 이 판결의 결론") ||
    text.includes("요구하는 것과 이 판결의 결론")
  ) {
    return true;
  }
  return text.includes("판결의 결론");
}

function isClaimHeading(line: string): boolean {
  const text = line.trim();
  if (isConclusionHeading(text)) return false;
  return (
    text.includes("요구하는 것") ||
    text.includes("원하는 것") ||
    text.includes("청구취지")
  );
}

function stripDocTitleLines(text: string): string {
  return text
    .split("\n")
    .filter((line) => {
      const stripped = line.trim();
      return (
        !DOC_TITLE_LINE.test(stripped) &&
        !DOC_TITLE_EASY_READ.test(stripped) &&
        !DOC_META_HEADING.test(stripped)
      );
    })
    .join("\n");
}

type Section = { heading: string | null; body: string[] };

function parseSections(text: string): Section[] {
  const sections: Section[] = [];
  let currentHeading: string | null = null;
  let currentLines: string[] = [];

  for (const line of text.split("\n")) {
    if (isSectionHeading(line)) {
      if (currentHeading !== null || currentLines.length > 0) {
        sections.push({ heading: currentHeading, body: currentLines });
      }
      currentHeading = line.trim();
      currentLines = [];
      continue;
    }
    currentLines.push(line);
  }

  if (currentHeading !== null || currentLines.length > 0) {
    sections.push({ heading: currentHeading, body: currentLines });
  }
  return sections;
}

function sectionsToText(sections: Section[]): string {
  const blocks: string[] = [];
  for (const { heading, body } of sections) {
    if (heading) blocks.push(heading);
    const bodyText = body.join("\n").replace(/\n+$/, "");
    if (bodyText.trim()) blocks.push(bodyText);
  }
  return blocks.join("\n\n").trim();
}

function reorderConclusionBeforeClaim(text: string): string {
  const sections = parseSections(text);
  if (sections.length < 2) return text;

  let conclusionIdx: number | null = null;
  let claimIdx: number | null = null;

  sections.forEach(({ heading }, i) => {
    if (!heading) return;
    if (conclusionIdx === null && isConclusionHeading(heading)) {
      conclusionIdx = i;
    }
    if (claimIdx === null && isClaimHeading(heading)) {
      claimIdx = i;
    }
  });

  if (
    conclusionIdx === null ||
    claimIdx === null ||
    conclusionIdx >= claimIdx
  ) {
    return text;
  }

  const next = [...sections];
  [next[conclusionIdx], next[claimIdx]] = [next[claimIdx], next[conclusionIdx]];
  return sectionsToText(next);
}

export function sanitizeTranslationText(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let inMeta = false;

  for (const line of lines) {
    const stripped = line.trim();
    if (stripped === "## 수정된 이지리드 번역본") {
      continue;
    }
    if (META_SECTION_START.test(stripped)) {
      inMeta = true;
      continue;
    }
    if (inMeta) {
      continue;
    }
    if (IMAGE_PLACEHOLDER.test(stripped)) {
      continue;
    }
    out.push(line);
  }

  let cleaned = out.join("\n").replace(/\n{3,}/g, "\n\n").trim();
  cleaned = stripDocTitleLines(cleaned);
  cleaned = reorderConclusionBeforeClaim(cleaned);
  return cleaned.trim();
}

export function filterPreviewLines(text: string): string[] {
  return sanitizeTranslationText(text)
    .split("\n")
    .filter((line) => line.trim() && !line.trim().startsWith("---"));
}
