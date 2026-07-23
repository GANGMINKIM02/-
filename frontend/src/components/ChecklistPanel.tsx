/**
 * 이지리드 품질 체크리스트 패널 (Figma 스타일).
 */
import type { ChecklistReport } from "../api/client";

const STATUS_STYLE: Record<string, string> = {
  pass: "text-success bg-green-50 border-green-200",
  warn: "text-amber-800 bg-amber-50 border-amber-200",
  fail: "text-alert bg-red-50 border-red-200",
  manual: "text-coolgray-60 bg-coolgray-10 border-coolgray-20",
};

const STATUS_LABEL: Record<string, string> = {
  pass: "통과",
  warn: "주의",
  fail: "수정 필요",
  manual: "수동 확인",
};

interface Props {
  checklist: ChecklistReport | null | undefined;
  onRecheck?: () => void;
  loading?: boolean;
}

export function ChecklistPanel({ checklist, onRecheck, loading }: Props) {
  if (!checklist) {
    return (
      <div className="text-xs text-coolgray-60 border border-coolgray-20 rounded-lg p-3 bg-white">
        {loading ? "체크리스트 검사 중..." : "번역 후 체크리스트가 자동 실행됩니다."}
      </div>
    );
  }

  const { overall, summary, items } = checklist;

  return (
    <div className="border border-coolgray-20 rounded-lg bg-white overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-coolgray-20 bg-coolgray-10">
        <div>
          <h3 className="text-sm font-medium text-coolgray-90">이지리드 체크리스트</h3>
          <p className="text-xs text-coolgray-60">
            통과 {summary.pass} · 주의 {summary.warn} · 수정 {summary.fail} · 수동{" "}
            {summary.manual}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-xs px-2 py-0.5 rounded border font-medium ${STATUS_STYLE[overall]}`}
          >
            {overall === "pass" ? "출력 가능" : overall === "warn" ? "검토 권장" : "수정 필요"}
          </span>
          {onRecheck && (
            <button
              type="button"
              onClick={onRecheck}
              disabled={loading}
              className="text-xs px-2 py-1 border border-coolgray-30 rounded hover:bg-white disabled:opacity-50"
            >
              재검사
            </button>
          )}
        </div>
      </div>
      <ul className="max-h-40 overflow-auto divide-y divide-coolgray-20 text-xs">
        {items.map((item) => (
          <li key={item.id} className="px-4 py-2 flex gap-2 items-start">
            <span
              className={`shrink-0 px-1.5 py-0.5 rounded border ${STATUS_STYLE[item.status]}`}
            >
              {STATUS_LABEL[item.status]}
            </span>
            <div>
              <p className="text-coolgray-90">{item.label}</p>
              {item.detail && <p className="text-coolgray-60 mt-0.5">{item.detail}</p>}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
