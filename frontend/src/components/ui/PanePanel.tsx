/**
 * Figma 2-pane 패널 (원문/요약문 등).
 */
import type { ReactNode } from "react";

interface PanePanelProps {
  title: string;
  children: ReactNode;
  className?: string;
}

export function PanePanel({ title, children, className = "" }: PanePanelProps) {
  return (
    <section
      className={`flex flex-col min-h-0 border border-black/80 bg-white ${className}`}
    >
      <div className="px-12 pt-3 pb-2 border-b border-coolgray-20">
        <h2 className="text-center text-lg font-bold text-coolgray-90">{title}</h2>
      </div>
      <div className="flex-1 min-h-0 flex flex-col p-4 overflow-hidden">{children}</div>
    </section>
  );
}
