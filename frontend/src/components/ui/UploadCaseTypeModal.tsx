/**
 * 업로드 전 사건 유형 선택 팝업 (민사·형사·가정·행정).
 */
import type { DocType } from "../../api/client";

export const UPLOAD_CASE_TYPE_OPTIONS: {
  value: Exclude<DocType, "unknown">;
  label: string;
}[] = [
  { value: "civil", label: "민사" },
  { value: "criminal", label: "형사" },
  { value: "family", label: "가정" },
  { value: "administrative", label: "행정" },
];

interface UploadCaseTypeModalProps {
  open: boolean;
  active: Exclude<DocType, "unknown">;
  filename?: string;
  loading?: boolean;
  onChange: (value: Exclude<DocType, "unknown">) => void;
  onConfirm: () => void;
  onCancel: () => void;
}

export function UploadCaseTypeModal({
  open,
  active,
  filename,
  loading = false,
  onChange,
  onConfirm,
  onCancel,
}: UploadCaseTypeModalProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-case-type-title"
      onClick={() => {
        if (!loading) onCancel();
      }}
    >
      <div
        className="w-full max-w-md rounded-xl border border-coolgray-20 bg-white p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="upload-case-type-title" className="text-lg font-bold text-coolgray-90">
          사건 유형 선택
        </h2>
        {filename && (
          <p className="mt-2 text-sm text-coolgray-60 truncate" title={filename}>
            {filename}
          </p>
        )}
        <p className="mt-3 text-sm text-coolgray-60">
          요약·번역에 사용할 판결 유형을 선택한 뒤 업로드를 진행합니다.
        </p>

        <div className="mt-5 flex flex-wrap gap-2.5">
          {UPLOAD_CASE_TYPE_OPTIONS.map(({ value, label }) => {
            const selected = active === value;
            return (
              <button
                key={value}
                type="button"
                disabled={loading}
                onClick={() => onChange(value)}
                className={`h-10 min-w-[72px] flex-1 rounded-full px-4 text-base transition-colors disabled:opacity-50 ${
                  selected
                    ? "bg-primary-60 text-white border border-primary-60"
                    : "bg-white text-coolgray-90 border border-coolgray-30 hover:bg-coolgray-10"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>

        <div className="mt-6 flex gap-3">
          <button
            type="button"
            disabled={loading}
            onClick={onCancel}
            className="flex-1 rounded-lg border border-coolgray-30 py-2.5 text-base font-medium text-coolgray-70 hover:bg-coolgray-10 disabled:opacity-50"
          >
            취소
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={onConfirm}
            className="flex-1 rounded-lg bg-primary-60 py-2.5 text-base font-semibold text-white hover:bg-primary-90 disabled:opacity-50"
          >
            {loading ? "업로드 중..." : "업로드"}
          </button>
        </div>
      </div>
    </div>
  );
}
