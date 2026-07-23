/**
 * 사건 유형 pill 선택 (UploadPage).
 */
import type { DocType } from "../../api/client";
import { DOC_TYPE_OPTIONS } from "../../api/client";

interface DocTypePillsProps {
  active: DocType;
  disabled?: boolean;
  onChange: (value: Exclude<DocType, "unknown">) => void;
}

export function DocTypePills({ active, disabled, onChange }: DocTypePillsProps) {
  const activeType = active !== "unknown" ? active : null;

  return (
    <div className="flex flex-wrap gap-2 px-4 py-2 border-b border-coolgray-20 bg-coolgray-10">
      <span className="text-xs text-coolgray-60 self-center mr-1">사건 유형</span>
      {DOC_TYPE_OPTIONS.map(({ value, label }) => (
        <button
          key={value}
          type="button"
          disabled={disabled}
          onClick={() => onChange(value)}
          className={`px-3 py-1 text-xs rounded-full border transition-colors ${
            activeType === value
              ? "bg-primary-60 text-white border-primary-60"
              : "bg-white text-coolgray-60 border-coolgray-30 hover:bg-coolgray-10"
          } disabled:opacity-50`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
