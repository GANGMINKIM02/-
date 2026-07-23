/**
 * Figma Group 6 — 플로팅 챗봇 FAB (3187:7301).
 * heroicons Solid chat 아이콘 + Primary/60 pill 버튼.
 */
import { IconChatSolid } from "./icons";

interface ChatbotFabProps {
  onClick?: () => void;
  className?: string;
}

export function ChatbotFab({ onClick, className = "" }: ChatbotFabProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`fixed bottom-6 right-6 z-50 w-16 h-[62px] rounded-full bg-primary-60 border-2 border-primary-60 flex items-center justify-center hover:opacity-90 transition-opacity ${className}`}
      aria-label="챗봇"
      title="챗봇 열기"
    >
      <IconChatSolid className="size-10" />
    </button>
  );
}
