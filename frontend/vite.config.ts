/**
 * Vite 빌드·개발 서버 설정.
 *
 * 역할: React·Tailwind 플러그인, API/이미지 프록시, 법률 일러스트 dist 복사.
 * 연관 파일: frontend/src/main.tsx, build-vercel.mjs, backend (8001 포트)
 */
import { cpSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

/** Copy LEGAL_DB illustrations into dist so Vercel static CDN can serve /images/*. */
function copyLegalImages() {
  return {
    name: "copy-legal-images",
    closeBundle() {
      try {
        const projectRoot = resolve(__dirname, "..");
        const src = join(projectRoot, "images");
        const dest = join(projectRoot, "frontend", "dist", "images");
        if (!existsSync(src)) {
          console.warn("[copy-legal-images] images/ not found — skip");
          return;
        }
        mkdirSync(dest, { recursive: true });
        cpSync(src, dest, { recursive: true });
        const count = readdirSync(dest).filter((f) => f.endsWith(".png")).length;
        console.log(`[copy-legal-images] copied ${count} PNG files to dist/images`);
        if (count === 0) {
          console.warn("[copy-legal-images] no PNG files copied");
        }
      } catch (err) {
        console.warn("[copy-legal-images] copy failed — continuing build:", err);
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), copyLegalImages()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
      "/images": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
    },
  },
});
