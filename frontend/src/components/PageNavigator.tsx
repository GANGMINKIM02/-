/**
 * 다중 페이지 OCR 텍스트 페이지 이동 UI (Figma 스타일).
 */
import { IconChevronLeft, IconChevronRight } from "./ui/icons";

interface PageNavigatorProps {
  current: number;
  total: number;
  onChange: (page: number) => void;
}

export function PageNavigator({ current, total, onChange }: PageNavigatorProps) {
  if (total <= 1) return null;
  return (
    <div className="flex items-center justify-center gap-2 py-2 text-base">
      <button
        type="button"
        disabled={current <= 1}
        onClick={() => onChange(current - 1)}
        className="inline-flex items-center gap-1 px-2 py-1 text-coolgray-60 disabled:opacity-40 hover:text-primary-60"
      >
        <IconChevronLeft className="size-5" />
      </button>
      <span className="font-medium text-coolgray-90">
        {current} / {total}
      </span>
      <button
        type="button"
        disabled={current >= total}
        onClick={() => onChange(current + 1)}
        className="inline-flex items-center gap-1 px-2 py-1 text-coolgray-60 disabled:opacity-40 hover:text-primary-60"
      >
        <IconChevronRight className="size-5" />
      </button>
    </div>
  );
}
