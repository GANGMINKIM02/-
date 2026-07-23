/**
 * Vercel 배포용 정적 파일 준비 스크립트.
 *
 * 역할: vite build 결과물을 backend/static으로 복사하고 images/를 dist에 동기화한다.
 * 연관 파일: frontend/vite.config.ts, frontend/dist, backend/static
 */
import { cpSync, copyFileSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { join } from "node:path";

const dist = join("frontend", "dist");
const staticDir = join("backend", "static");

if (!existsSync(join(dist, "index.html"))) {
  console.error("frontend/dist/index.html not found. Run vite build first.");
  process.exit(1);
}

mkdirSync(staticDir, { recursive: true });
copyFileSync(join(dist, "index.html"), join(staticDir, "index.html"));

if (existsSync(join(dist, "assets"))) {
  cpSync(join(dist, "assets"), join(staticDir, "assets"), { recursive: true });
}

for (const file of ["favicon.svg", "icons.svg"]) {
  const src = join("frontend", "public", file);
  if (existsSync(src)) {
    copyFileSync(src, join(staticDir, file));
  }
}

mkdirSync(join(dist, "images"), { recursive: true });
if (existsSync("images")) {
  cpSync("images", join(dist, "images"), { recursive: true });
}
const pngCount = existsSync(join(dist, "images"))
  ? readdirSync(join(dist, "images")).filter((f) => f.endsWith(".png")).length
  : 0;
console.log(`Prepared backend/static; dist/images has ${pngCount} PNG files`);
if (pngCount === 0) {
  console.warn("WARN: dist/images is empty — images will be served via /api fallback");
}
