/**
 * Figma 5단계 워크플로 stepper (업로드→요약→번역→그림→추출).
 */
import { Link } from "react-router-dom";
import { IconActiveStep, IconCheck, IconCircle } from "./icons";

export type WorkflowStep = "upload" | "summary" | "translate" | "images" | "export";

const STEPS: { id: WorkflowStep; label: string }[] = [
  { id: "upload", label: "1. 업로드" },
  { id: "summary", label: "2. 요약" },
  { id: "translate", label: "3. 번역" },
  { id: "images", label: "4. 그림" },
  { id: "export", label: "5. 추출" },
];

function stepIndex(step: WorkflowStep): number {
  return STEPS.findIndex((s) => s.id === step);
}

export function stepPath(step: WorkflowStep, docId?: string): string | null {
  switch (step) {
    case "upload":
      return "/";
    case "summary":
      return docId ? `/documents/${docId}/summary` : null;
    case "translate":
      return docId ? `/documents/${docId}/translate` : null;
    case "images":
      return docId ? `/documents/${docId}/images` : null;
    case "export":
      return docId ? `/documents/${docId}/export` : null;
    default:
      return null;
  }
}

interface StepIndicatorProps {
  current: WorkflowStep;
  docId?: string;
}

export function StepIndicator({ current, docId }: StepIndicatorProps) {
  const currentIdx = stepIndex(current);

  return (
    <div className="flex border-b border-coolgray-20 bg-white">
      {STEPS.map((step, idx) => {
        const done = idx < currentIdx;
        const active = idx === currentIdx;
        const pending = idx > currentIdx;
        const to = stepPath(step.id, docId);

        let borderClass = "border-t-[3px] border-coolgray-30";
        let bgClass = "bg-white";
        if (done) {
          borderClass = "border-t-[3px] border-primary-90 bg-coolgray-10";
        } else if (active) {
          borderClass =
            step.id === "upload"
              ? "border-t-[3px] border-primary-90 bg-white"
              : "border-t-[3px] border-coolgray-90 bg-white";
        }

        const content = (
          <>
            <div className="pt-3 shrink-0">
              {done ? (
                <IconCheck className="size-6" />
              ) : active ? (
                <IconActiveStep className="size-6" />
              ) : (
                <IconCircle className="size-6" />
              )}
            </div>
            <div className="py-4 min-w-0 flex-1 text-left">
              <p
                className={`text-sm font-medium leading-tight ${
                  pending ? "text-coolgray-40" : "text-coolgray-90"
                }`}
              >
                {step.label}
              </p>
              {active && (
                <p className="text-xs text-alert mt-0.5 truncate">진행중</p>
              )}
              {done && (
                <p className="text-xs text-coolgray-60 mt-0.5 truncate">완료</p>
              )}
              {pending && (
                <p className="text-xs text-coolgray-40 mt-0.5 truncate">이전 단계 완료 후</p>
              )}
            </div>
          </>
        );

        const className = `flex flex-1 gap-2 px-2 min-w-0 ${borderClass} ${bgClass}`;

        if (to) {
          return (
            <Link
              key={step.id}
              to={to}
              className={`${className} relative z-10 hover:opacity-90 transition-opacity cursor-pointer no-underline text-inherit`}
            >
              {content}
            </Link>
          );
        }

        return (
          <div
            key={step.id}
            className={`${className} opacity-60 cursor-not-allowed`}
            aria-disabled
            title="문서 업로드 후 이동할 수 있습니다"
          >
            {content}
          </div>
        );
      })}
    </div>
  );
}
