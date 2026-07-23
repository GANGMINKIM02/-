/**
 * Figma 워크플로 공통 레이아웃 (헤더 + stepper + 콘텐츠 카드).
 */
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChatbotWidget } from "./ChatbotWidget";
import { StepIndicator, type WorkflowStep } from "./StepIndicator";

/** 2단 grid — 중앙선 기준 1:1, 좌·우 바깥 여백 동일(px-5) */
export function WorkflowTwoPaneGrid({ children }: { children: ReactNode }) {
  return (
    <div className="flex-1 grid min-h-0 grid-cols-2 gap-5 overflow-hidden px-5 pt-4 pb-5">
      {children}
    </div>
  );
}

export function WorkflowTwoPaneColumn({
  children,
  className = "",
  side = "left",
}: {
  children: ReactNode;
  className?: string;
  /** right: FAB·프롬프트 여백만 오른쪽 열에 적용 */
  side?: "left" | "right";
}) {
  const sideClass =
    side === "right" ? "gap-3 overflow-hidden pb-24 min-w-0 w-full" : "overflow-hidden min-w-0";
  return (
    <div
      className={`flex min-h-0 flex-col ${sideClass} ${className}`.trim()}
    >
      {children}
    </div>
  );
}

interface WorkflowLayoutProps {
  step: WorkflowStep;
  docId?: string;
  filename?: string;
  projectTitle?: ReactNode;
  headerVariant?: "default" | "compact";
  prevNav?: { label: string; to: string };
  nextNav?: { label: string; to: string };
  error?: string;
  children: ReactNode;
  footerExtra?: ReactNode;
}

export function WorkflowLayout({
  step,
  docId,
  filename,
  projectTitle = "Easy-Read 판결문 작성 보조",
  headerVariant = "default",
  prevNav,
  nextNav,
  error,
  children,
  footerExtra,
}: WorkflowLayoutProps) {
  const compact = headerVariant === "compact";

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-coolgray-10">
      <div className={`px-6 ${compact ? "pt-4 pb-0" : "pt-6 pb-0"}`}>
        <div
          className={`flex items-start justify-between gap-6 ${compact ? "mb-3" : "mb-6"}`}
        >
          <h1
            className={`font-bold leading-tight tracking-tight text-coolgray-90 ${
              compact ? "text-[32px]" : "text-[42px]"
            }`}
          >
            {projectTitle}
          </h1>
          {filename && (
            <span
              className={`shrink-0 text-base font-medium tracking-wide text-primary-60 ${
                compact ? "pt-1" : "pt-2"
              } max-w-[min(48vw,640px)] truncate text-right`}
            >
              {filename}
            </span>
          )}
        </div>
      </div>

      <div
        className={`mx-6 flex min-h-0 flex-1 flex-col overflow-hidden border border-coolgray-20 bg-white ${
          compact ? "mb-4" : "mb-6"
        }`}
      >
        <StepIndicator current={step} docId={docId} />

        {(prevNav || nextNav) && (
          <div className="flex items-center justify-between border-b border-coolgray-20 px-4 py-2">
            {prevNav ? (
              <Link
                to={prevNav.to}
                className="inline-flex items-center gap-1 text-base font-medium text-coolgray-60 hover:text-primary-60"
              >
                <span className="text-lg leading-none">‹</span>
                {prevNav.label}
              </Link>
            ) : (
              <span />
            )}
            {nextNav ? (
              <Link
                to={nextNav.to}
                className="inline-flex items-center gap-1 text-base font-medium text-primary-60 hover:underline"
              >
                {nextNav.label}
                <span className="text-lg leading-none">›</span>
              </Link>
            ) : (
              <span />
            )}
          </div>
        )}

        {error && (
          <div className="mx-4 mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="flex min-h-0 flex-1 flex-col">{children}</div>

        {footerExtra}
      </div>

      <ChatbotWidget docId={docId} />
    </div>
  );
}
