/**
 * Word(.docx) blob 미리보기 — 서버 Word export 결과를 브라우저에 렌더.
 */
import { useEffect, useRef } from "react";
import { renderAsync } from "docx-preview";

interface DocxPreviewPanelProps {
  blob: Blob | null;
  onReady?: () => void;
  onError?: (message: string) => void;
}

export function DocxPreviewPanel({ blob, onReady, onError }: DocxPreviewPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !blob) return;

    let cancelled = false;
    container.innerHTML = "";

    renderAsync(blob, container, undefined, {
      className: "docx",
      inWrapper: true,
      ignoreWidth: false,
      ignoreHeight: false,
      breakPages: true,
    })
      .then(() => {
        if (!cancelled) onReady?.();
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          onError?.(err instanceof Error ? err.message : "Word 미리보기 렌더 실패");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [blob, onError, onReady]);

  return (
    <div
      id="export-print-area"
      ref={containerRef}
      className="export-docx-preview h-full w-full overflow-auto bg-[#e8e8e8] p-4 print:p-0 print:bg-white"
    />
  );
}
