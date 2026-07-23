/**
 * 문서 업로드 페이지 (워크플로 1단계) — Figma 업로드 80% ERAI UI.
 */
import { useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { type DocType, uploadDocument, updateDocType } from "../api/client";
import { ExistingProjectsTable } from "../components/ui/ExistingProjectsTable";
import { ChatbotWidget } from "../components/ui/ChatbotWidget";
import { IconUploadCloud } from "../components/ui/icons";
import { StepIndicator } from "../components/ui/StepIndicator";
import { UploadCaseTypeModal } from "../components/ui/UploadCaseTypeModal";
import { cacheUpload, getCachedUpload, getLastDocId } from "../utils/docCache";
import { guessDocTypeFromFilename } from "../utils/guessDocType";
import { saveSourceFile } from "../utils/sourceStore";
import { isAdminUser } from "../utils/auth";

export function UploadPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const lastDocId = getLastDocId();
  const [docType, setDocType] = useState<Exclude<DocType, "unknown">>("criminal");
  const [docTypeTouched, setDocTypeTouched] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [caseTypeModalOpen, setCaseTypeModalOpen] = useState(false);

  const filenameLabel = useMemo(() => {
    if (pendingFile?.name) return pendingFile.name;
    if (lastDocId) {
      const cached = getCachedUpload(lastDocId);
      if (cached?.filename) return cached.filename;
    }
    return "파일명";
  }, [pendingFile, lastDocId]);

  async function handleUpload(file: File) {
    setLoading(true);
    setError("");
    try {
      const result = await uploadDocument(file);
      const finalDocType = docTypeTouched ? docType : result.doc_type;
      if (finalDocType !== result.doc_type) {
        await updateDocType(result.id, finalDocType);
      }
      if (result.pages?.length && result.full_text) {
        cacheUpload({
          ...result,
          doc_type: finalDocType,
          pages: result.pages,
          full_text: result.full_text,
          source_blob_url: URL.createObjectURL(file),
          source_filename: file.name,
          source_mime_type: file.type || undefined,
        });
        void saveSourceFile(result.id, file);
      }
      setCaseTypeModalOpen(false);
      navigate(`/documents/${result.id}/summary`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "업로드 실패");
    } finally {
      setLoading(false);
    }
  }

  function selectFile(file: File) {
    setError("");
    setPendingFile(file);
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) selectFile(file);
    e.target.value = "";
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) selectFile(file);
  }

  function handleDone() {
    if (pendingFile && !loading) {
      setDocTypeTouched(false);
      setDocType(guessDocTypeFromFilename(pendingFile.name));
      setCaseTypeModalOpen(true);
    }
  }

  function handleDocTypeChange(value: Exclude<DocType, "unknown">) {
    setDocType(value);
    setDocTypeTouched(true);
  }

  function closeCaseTypeModal() {
    if (!loading) setCaseTypeModalOpen(false);
  }

  function confirmUploadWithCaseType() {
    if (pendingFile && !loading) {
      void handleUpload(pendingFile);
    }
  }

  return (
    <div className="h-screen overflow-hidden bg-coolgray-10 flex flex-col">
      <header className="px-6 pt-4 pb-0 shrink-0">
        <div className="flex items-start justify-between gap-6 mb-3">
          <h1 className="text-[32px] font-bold leading-tight text-coolgray-90 tracking-tight">
            ER<span className="text-primary-60">AI</span>
          </h1>
          <div className="flex flex-col items-end gap-1 shrink-0 pt-1">
            <span className="text-primary-60 font-medium text-base tracking-wide truncate max-w-[40vw]">
              {filenameLabel}
            </span>
            {isAdminUser() && (
              <Link
                to="/admin/storage"
                className="text-sm font-medium text-coolgray-60 hover:text-primary-60"
              >
                저장소 관리
              </Link>
            )}
          </div>
        </div>
      </header>

      <div className="flex-1 flex flex-col mx-6 mb-4 min-h-0 bg-white border border-coolgray-20 overflow-hidden">
        <StepIndicator current="upload" docId={lastDocId ?? undefined} />

        <div className="flex-1 min-h-0 overflow-y-auto">
          <section className="mx-5 mt-4">
            <h2 className="text-lg font-bold text-coolgray-90 mb-3">새 프로젝트</h2>

            <div className="rounded-xl border border-[#e6e7ea] bg-coolgray-10 p-6">
              <div
                className={`mx-auto max-w-[649px] rounded-lg border border-dashed p-8 flex flex-col items-center gap-3 transition-colors ${
                  dragOver
                    ? "border-primary-60 bg-blue-50"
                    : "border-primary-60 bg-coolgray-20"
                }`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
              >
                <IconUploadCloud className="size-8 text-primary-60" />
                <div className="text-center">
                  <p className="text-base font-medium text-coolgray-90">
                    {pendingFile ? pendingFile.name : "Drop file or browse"}
                  </p>
                  <p className="text-sm text-coolgray-60 mt-1">
                    Format: PDF, PNG, JPG, TXT, DOC, DOCX, HWP · Max 25 MB
                  </p>
                </div>
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => inputRef.current?.click()}
                  className="px-4 py-1 text-sm font-semibold text-white bg-[#6794e5] border border-white rounded-lg shadow-sm hover:bg-primary-60 disabled:opacity-50"
                >
                  Browse Files
                </button>
                <input
                  ref={inputRef}
                  type="file"
                  className="hidden"
                  accept=".pdf,.png,.jpg,.jpeg,.txt,.doc,.docx,.hwp,.hwpx"
                  disabled={loading}
                  onChange={onInputChange}
                />
              </div>

              <div className="mx-auto max-w-[538px] mt-4">
                <button
                  type="button"
                  disabled={loading || !pendingFile}
                  onClick={handleDone}
                  className="w-full py-2.5 text-base font-semibold text-white bg-primary-60 border border-white rounded-lg shadow-sm hover:bg-primary-90 disabled:opacity-50 transition-colors"
                >
                  {loading ? "업로드 중..." : "업로드"}
                </button>
              </div>

              {error && (
                <p className="mt-3 text-sm text-alert text-center">{error}</p>
              )}
            </div>
          </section>

          <ExistingProjectsTable />
        </div>
      </div>

      <ChatbotWidget />

      <UploadCaseTypeModal
        open={caseTypeModalOpen}
        active={docType}
        filename={pendingFile?.name}
        loading={loading}
        onChange={handleDocTypeChange}
        onConfirm={confirmUploadWithCaseType}
        onCancel={closeCaseTypeModal}
      />
    </div>
  );
}
