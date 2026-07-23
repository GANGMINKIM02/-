/** Figma jam-icons 스타일 UI 아이콘 (inline SVG) */

export function IconChevronLeft({ className = "size-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M14 6L8 12L14 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconChevronRight({ className = "size-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M10 6L16 12L10 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconCheck({ className = "size-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M5 12.5L9.5 17L19 7" stroke="#25A249" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconCircle({ className = "size-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="#C1C7CD" strokeWidth="2" />
    </svg>
  );
}

export function IconActiveStep({ className = "size-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="#21272A" strokeWidth="2" />
      <path d="M12 7V12L15 14" stroke="#21272A" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function IconArrowRight({ className = "size-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M5 12H19M19 12L13 6M19 12L13 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconSpinner({ className = "size-5" }: { className?: string }) {
  return (
    <svg className={`${className} animate-spin`} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" className="opacity-25" />
      <path
        d="M12 3a9 9 0 0 1 9 9"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconUploadCloud({ className = "size-8" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" aria-hidden>
      <path
        d="M16 4V20M16 4L10 10M16 4L22 10M6 22H26C27.1 22 28 22.9 28 24V26C28 27.1 27.1 28 26 28H6C4.9 28 4 27.1 4 26V24C4 22.9 4.9 22 6 22Z"
        stroke="#0F62FE"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Figma 3187:7301 — heroicons Solid chat (흰 말풍선 + 파란 점 3개) */
export function IconChatSolid({ className = "size-10" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 32 28"
      fill="none"
      aria-hidden
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M32 14C32 21.732 24.8366 28 16 28C13.0167 28 10.2242 27.2856 7.83354 26.0416L0 28L2.67661 21.7546C0.985602 19.5346 0 16.868 0 14C0 6.26801 7.16344 0 16 0C24.8366 0 32 6.26801 32 14ZM10 12H6V16H10V12ZM26 12H22V16H26V12ZM14 12H18V16H14V12Z"
        fill="white"
      />
    </svg>
  );
}

/** @deprecated IconChatSolid 사용 */
export function IconChat({ className = "size-10" }: { className?: string }) {
  return <IconChatSolid className={className} />;
}
