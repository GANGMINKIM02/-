/**
 * PDF·이미지·텍스트 원문/산출물 인앱 미리보기 (새 탭·팝업 불필요).
 */
import { useEffect } from "react";
import type { InlinePreviewMode } from "../../utils/sourcePreview";

export interface FilePreviewState {
  url: string;
  title: string;
  filename: string;
  mode: InlinePreviewMode;
  textContent?: string;
}

interface FilePreviewModalProps {
  preview: FilePreviewState | null;
  onClose: () => void;
}

export function FilePreviewModal({ preview, onClose }: FilePreviewModalProps) {
  useEffect(() => {
    if (!preview) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [preview, onClose]);

  if (!preview) return null;

  const mode = preview.mode;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/45 p-3 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="file-preview-title"
      onClick={onClose}
    >
      <div
        className="flex h-[min(92vh,900px)] w-full max-w-6xl flex-col overflow-hidden rounded-xl bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-coolgray-20 px-4 py-3">
          <div className="min-w-0">
            <h3 id="file-preview-title" className="text-base font-bold text-coolgray-90 truncate">
              {preview.title}
            </h3>
            <p className="text-xs text-coolgray-60 truncate">{preview.filename}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <a
              href={preview.url}
              download={preview.filename}
              className="rounded border border-coolgray-30 px-2 py-1 text-xs font-medium text-coolgray-90 hover:bg-coolgray-10"
            >
              다운로드
            </a>
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-coolgray-30 px-2 py-1 text-xs text-coolgray-90 hover:bg-coolgray-10"
            >
              닫기
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 bg-coolgray-10">
          {mode === "iframe" && (
            <iframe
              title={preview.title}
              src={preview.url}
              className="h-full w-full border-0 bg-white"
            />
          )}
          {mode === "image" && (
            <div className="flex h-full items-center justify-center overflow-auto p-4">
              <img
                src={preview.url}
                alt={preview.filename}
                className="max-h-full max-w-full object-contain"
              />
            </div>
          )}
          {mode === "text" && (
            <pre className="h-full overflow-auto whitespace-pre-wrap p-4 text-sm text-coolgray-90">
              {preview.textContent ?? ""}
            </pre>
          )}
          {mode === "download" && (
            <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
              <p className="text-sm text-coolgray-70">
                이 형식은 브라우저에서 바로 미리보기하기 어렵습니다.
              </p>
              <a
                href={preview.url}
                download={preview.filename}
                className="rounded-lg bg-primary-60 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-90"
              >
                파일 다운로드
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
