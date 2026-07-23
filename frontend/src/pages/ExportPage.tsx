/**
 * PDF 추출 페이지 (워크플로 5단계) — Figma 추출 80% ERAI UI.
 */
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { TranslationSegment } from "../api/client";
import { downloadDocx, downloadPdf, fetchExportDocx, fetchExportPdf, attachSourcePdfForExport } from "../api/client";
import { DocxPreviewPanel } from "../components/DocxPreviewPanel";
import { ExportPdfPreviewPanel } from "../components/ExportPdfPreviewPanel";
import { IconArrowRight } from "../components/ui/icons";
import { WorkflowLayout } from "../components/ui/WorkflowLayout";
import { getCachedUpload } from "../utils/docCache";
import { enrichSegmentsForExport } from "../utils/exportImages";
import { EASY_READ_COURT_FONT_CLASS } from "../utils/exportTypography";
import { loadDocumentWithRecovery } from "../utils/documentLoader";
import {
  getWorkflowSnapshot,
  resolveSummary,
  resolveTranslationSegments,
  saveWorkflowSnapshot,
} from "../utils/workflowCache";

type PreviewMode = "pdf" | "docx";

export function ExportPage() {
  const { id } = useParams<{ id: string }>();
  const [filename, setFilename] = useState("");
  const [summary, setSummary] = useState("");
  const [segments, setSegments] = useState<TranslationSegment[]>([]);
  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null);
  const [previewMode, setPreviewMode] = useState<PreviewMode>("pdf");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewReady, setPreviewReady] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");

  const [fullText, setFullText] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    setError("");
    try {
      const doc = await loadDocumentWithRecovery(id);
      setFilename(doc.filename);
      setSummary(resolveSummary(id, doc.summary));
      setFullText(doc.full_text ?? "");
      const segs = resolveTranslationSegments(id, doc.translation_segments);
      setSegments(segs);
      if (segs.length) {
        saveWorkflowSnapshot(id, { translation_segments: segs, filename: doc.filename });
      }
    } catch (err) {
      const workflow = getWorkflowSnapshot(id);
      const cached = getCachedUpload(id);
      const segs = resolveTranslationSegments(id, workflow?.translation_segments ?? []);
      if (segs.length) {
        setFilename(workflow?.filename ?? cached?.filename ?? "");
        setSummary(resolveSummary(id, workflow?.summary));
        setFullText(cached?.full_text ?? "");
        setSegments(segs);
        return;
      }
      setError(err instanceof Error ? err.message : "문서를 불러오지 못했습니다");
    }
  }, [id]);

  useEffect(() => {
    load().catch(console.error);
  }, [load]);

  const buildExportPayload = useCallback(async () => {
    if (!id) {
      throw new Error("문서 ID가 없습니다.");
    }
    const cached = id ? getCachedUpload(id) : null;
    const mergedSegments = id ? resolveTranslationSegments(id, segments) : segments;
    const exportSegments = await enrichSegmentsForExport(mergedSegments);
    const mergedFullText = fullText || cached?.full_text || "";
    return attachSourcePdfForExport(id, filename, {
      segments: exportSegments,
      translation_text: exportSegments.map((s) => s.easy_text).filter(Boolean).join("\n\n"),
      summary,
      filename,
      doc_type: cached?.doc_type,
      full_text: mergedFullText,
      pages: cached?.pages,
    });
  }, [id, segments, summary, filename, fullText]);

  useEffect(() => {
    if (!id || segments.length === 0) {
      setPreviewBlob(null);
      setPreviewReady(false);
      return;
    }

    let cancelled = false;
    setPreviewLoading(true);
    setPreviewReady(false);
    setError("");

    void (async () => {
      try {
        const payload = await buildExportPayload();
        try {
          const pdfBlob = await fetchExportPdf(id, payload);
          if (cancelled) return;
          setPreviewMode("pdf");
          setPreviewBlob(pdfBlob);
          return;
        } catch {
          const docxBlob = await fetchExportDocx(id, payload);
          if (cancelled) return;
          setPreviewMode("docx");
          setPreviewBlob(docxBlob);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "미리보기 생성 실패");
        }
      } finally {
        if (!cancelled) setPreviewLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [id, segments, buildExportPayload]);

  async function handleExportDocx() {
    if (!id || segments.length === 0) return;
    setExporting(true);
    setError("");
    try {
      const payload = await buildExportPayload();
      await downloadDocx(id, payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Word 추출 실패");
    } finally {
      setExporting(false);
    }
  }

  async function handleExportPdf() {
    if (!id || segments.length === 0 || !previewReady) return;
    setExporting(true);
    setError("");
    try {
      if (previewMode === "pdf" && previewBlob) {
        const url = URL.createObjectURL(previewBlob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `easyread_${id.slice(0, 8)}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        return;
      }

      const payload = await buildExportPayload();
      try {
        await downloadPdf(id, payload);
        return;
      } catch {
        window.print();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF 추출 실패");
    } finally {
      setExporting(false);
    }
  }

  return (
    <WorkflowLayout
      step="export"
      docId={id}
      headerVariant="compact"
      projectTitle={
        <>
          ER<span className="text-primary-60">AI</span>
        </>
      }
      filename={filename || "파일명"}
      error={error || undefined}
    >
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden px-5 pt-4 pb-5">
        <div className="flex-1 flex flex-col items-center gap-4 min-h-0 overflow-hidden w-full max-w-[916px] mx-auto">
          <div className="w-full flex-1 min-h-0 flex flex-col border border-coolgray-30 overflow-hidden rounded-sm shadow-inner bg-[#e8e8e8]">
            {previewLoading ? (
              <div className="flex flex-1 items-center justify-center text-coolgray-60 text-base">
                최종 PDF 생성 중…
              </div>
            ) : previewBlob && previewMode === "pdf" ? (
              <div className="flex-1 min-h-0">
                <ExportPdfPreviewPanel blob={previewBlob} onReady={() => setPreviewReady(true)} />
              </div>
            ) : previewBlob && previewMode === "docx" ? (
              <div className={`flex-1 min-h-0 ${EASY_READ_COURT_FONT_CLASS}`}>
                <DocxPreviewPanel
                  blob={previewBlob}
                  onReady={() => setPreviewReady(true)}
                  onError={(message) => setError(message)}
                />
              </div>
            ) : (
              <div className="flex flex-1 items-center justify-center text-coolgray-60 text-base px-6 text-center">
                {segments.length === 0
                  ? "번역 내용이 없어 미리보기를 생성할 수 없습니다."
                  : "미리보기를 불러올 수 없습니다."}
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-center gap-4 shrink-0 w-full max-w-[900px]">
            <button
              type="button"
              onClick={handleExportPdf}
              disabled={exporting || previewLoading || !previewReady || segments.length === 0}
              className="inline-flex h-14 min-w-[200px] flex-1 items-center justify-center gap-2 bg-primary-60 border-2 border-primary-60 px-4 text-white text-xl font-medium tracking-wide hover:bg-primary-90 disabled:opacity-50 transition-colors"
            >
              {exporting ? "추출 중..." : "PDF 추출하기"}
              <IconArrowRight className="size-6 text-white" />
            </button>
            <button
              type="button"
              onClick={handleExportDocx}
              disabled={exporting || previewLoading || segments.length === 0}
              className="inline-flex h-14 min-w-[200px] flex-1 items-center justify-center gap-2 border-2 border-primary-60 bg-white px-4 text-primary-60 text-xl font-medium tracking-wide hover:bg-primary-60/5 disabled:opacity-50 transition-colors"
            >
              Word 추출하기
            </button>
            <Link
              to="/"
              className="inline-flex h-14 min-w-[200px] flex-1 items-center justify-center border-2 border-coolgray-40 px-4 text-coolgray-70 text-xl font-medium tracking-wide hover:bg-coolgray-10 transition-colors text-center"
            >
              업로드 화면으로 돌아가기
            </Link>
          </div>
        </div>
      </div>
    </WorkflowLayout>
  );
}
