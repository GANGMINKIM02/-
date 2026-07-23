/**
 * 서버에서 생성한 최종 PDF(inline) 미리보기 — docx-preview 대신 PDF 그대로 표시.
 */
import { useEffect, useState } from "react";

interface ExportPdfPreviewPanelProps {
  blob: Blob | null;
  onReady?: () => void;
}

export function ExportPdfPreviewPanel({ blob, onReady }: ExportPdfPreviewPanelProps) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!blob) {
      setObjectUrl(null);
      return;
    }
    const url = URL.createObjectURL(blob);
    setObjectUrl(url);
    onReady?.();
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [blob, onReady]);

  if (!objectUrl) return null;

  return (
    <iframe
      title="추출 PDF 미리보기"
      src={objectUrl}
      className="h-full min-h-[480px] w-full border-0 bg-white"
    />
  );
}
