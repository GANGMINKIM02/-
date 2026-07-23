import { formatHeadingDisplay, isSectionHeading } from "../utils/translationSections";
import { hasStyleMarkers, parseStyledParts } from "../utils/richText";

export function StyledText({ text, className }: { text: string; className?: string }) {
  return (
    <span className={className}>
      {parseStyledParts(text).map((part, i) => {
        const style = part.sizePt !== 12 ? { fontSize: `${part.sizePt}px` } : undefined;
        if (part.bold) {
          return (
            <strong key={i} className="font-bold" style={style}>
              {part.text}
            </strong>
          );
        }
        return (
          <span key={i} style={style}>
            {part.text}
          </span>
        );
      })}
    </span>
  );
}

/** 본문·소제목 줄 — 서식 마커 없는 소제목은 17pt 굵게 기본 표시 */
export function StyledLine({ text, heading = false }: { text: string; heading?: boolean }) {
  const display = heading ? formatHeadingDisplay(text) : text;
  if ((heading || isSectionHeading(text)) && !hasStyleMarkers(text)) {
    return (
      <span className="text-[17px] font-bold text-coolgray-90 leading-snug">{display}</span>
    );
  }
  return <StyledText text={heading ? text.replace(/^#+\s*/, "").trim() : text} />;
}

/** @deprecated StyledLine / StyledText 사용 */
export function BoldText({ text, className }: { text: string; className?: string }) {
  return <StyledText text={text} className={className} />;
}
