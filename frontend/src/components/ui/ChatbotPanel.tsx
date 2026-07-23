/**
 * 챗봇 대화 패널 — Solar API + DB/웹 검색 연동.
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type { ChatMessage } from "../../api/client";
import { sendChatMessage } from "../../api/client";
import { IconChatSolid } from "./icons";

interface ChatbotPanelProps {
  open: boolean;
  onClose: () => void;
  docId?: string;
  pageContext?: string;
}

function renderBoldText(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /\*\*([\s\S]+?)\*\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      const plain = text.slice(lastIndex, match.index).replace(/\*\*/g, "");
      nodes.push(
        <span key={`plain-${lastIndex}`}>{plain}</span>,
      );
    }
    nodes.push(<strong key={`bold-${match.index}`}>{match[1]}</strong>);
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    nodes.push(<span key={`tail-${lastIndex}`}>{text.slice(lastIndex).replace(/\*\*/g, "")}</span>);
  }

  if (!nodes.length) {
    return [<span key="plain-0">{text.replace(/\*\*/g, "")}</span>];
  }

  return nodes;
}

export function ChatbotPanel({ open, onClose, docId, pageContext }: ChatbotPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    const nextHistory = [...messages, userMsg];
    setMessages(nextHistory);
    setInput("");
    setLoading(true);
    setError("");

    try {
      const res = await sendChatMessage(text, messages, docId, pageContext);
      setMessages([...nextHistory, { role: "assistant", content: res.reply }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "챗봇 응답 실패");
      setMessages(messages);
    } finally {
      setLoading(false);
    }
  }, [docId, input, loading, messages, pageContext]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-end p-4 sm:p-6 pointer-events-none"
      aria-hidden={!open}
    >
      <button
        type="button"
        className="absolute inset-0 bg-black/20 pointer-events-auto"
        aria-label="챗봇 닫기"
        onClick={onClose}
      />

      <div className="relative w-full max-w-[420px] h-[min(640px,calc(100vh-6rem))] bg-white border border-coolgray-20 shadow-2xl flex flex-col pointer-events-auto rounded-lg overflow-hidden">
        <header className="flex items-center gap-3 px-4 py-3 border-b border-coolgray-20 bg-coolgray-10 shrink-0">
          <div className="size-10 rounded-full bg-primary-60 flex items-center justify-center shrink-0">
            <IconChatSolid className="size-6" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-coolgray-90">ERAI 챗봇</p>
            <p className="text-xs text-coolgray-60 truncate">
              {pageContext ? "현재 화면 맥락 포함" : docId ? "현재 문서 맥락 포함" : "DB · 웹 검색 지원"}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-coolgray-60 hover:text-coolgray-90 text-xl leading-none px-1"
            aria-label="닫기"
          >
            ×
          </button>
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
          {messages.length === 0 && !loading && (
            <p className="text-sm text-coolgray-60 text-center py-8 leading-relaxed">
              판결문·이지리드·서비스 사용법을 물어보세요.
              <br />
              DB에서 먼저 찾고, 필요하면 웹 검색으로 답합니다.
            </p>
          )}

          {messages.map((msg, i) => (
            <div
              key={`${msg.role}-${i}`}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === "user"
                    ? "bg-primary-60 text-white"
                    : "bg-coolgray-10 text-coolgray-90 border border-coolgray-20"
                }`}
              >
                {msg.role === "assistant" ? renderBoldText(msg.content.replace(/\*\*/g, "")) : msg.content}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-coolgray-10 border border-coolgray-20 rounded-lg px-3 py-2 text-sm text-coolgray-60">
                답변 생성 중...
              </div>
            </div>
          )}
        </div>

        {error && (
          <p className="px-4 py-2 text-xs text-alert border-t border-coolgray-20 shrink-0">{error}</p>
        )}

        <footer className="p-3 border-t border-coolgray-20 shrink-0">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="메시지를 입력하세요"
              disabled={loading}
              className="flex-1 h-10 px-3 bg-coolgray-10 border-b border-coolgray-30 text-sm outline-none focus:border-primary-60 disabled:opacity-60"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            <button
              type="button"
              onClick={send}
              disabled={loading || !input.trim()}
              className="px-4 h-10 bg-primary-60 text-white text-sm font-medium disabled:opacity-50 hover:bg-primary-90 transition-colors shrink-0"
            >
              전송
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
