"""FastAPI 앱 진입점.

역할: Easy-Read 판결문 API 서버를 생성하고 라우터·미들웨어·정적 파일을 등록한다.
주요 기능: DB 초기화(lifespan), CORS, Vercel 경로 복원, /api/documents 라우터 마운트,
          SPA 빌드·이미지 정적 서빙, 헬스체크.
관계: config(설정), database(init_db), routers/documents(문서 API).
      api/index.py(Vercel)에서 이 app 객체를 import한다.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.config import BACKEND_DIR, IMAGES_DIR, IS_VERCEL, settings
from backend.database import init_db
from backend.routers import chat, documents

STATIC_DIR = BACKEND_DIR / "static"

# --- Vercel 경로 복원 미들웨어 ---


class VercelPathMiddleware(BaseHTTPMiddleware):
    """Restore the browser URL path when Vercel rewrites to /api/index.py."""

    async def dispatch(self, request: Request, call_next):
        original = (
            request.headers.get("x-vercel-original-url")
            or request.headers.get("x-forwarded-uri")
            or request.headers.get("x-invoke-path")
        )
        if original:
            value = original if original.startswith("/") else urlparse(original).path
            parsed = urlparse(value)
            if parsed.path:
                request.scope["path"] = parsed.path
                request.scope["raw_path"] = parsed.path.encode()
                if parsed.query:
                    request.scope["query_string"] = parsed.query.encode()
        return await call_next(request)


# --- 앱 생성 및 미들웨어 ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Easy-Read 판결문 작성 보조 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(VercelPathMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

app.include_router(documents.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

# --- 헬스체크 ---


@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok", "mock_mode": settings.use_mock}

# --- SPA 정적 파일 서빙 ---


def _static_file(relative: str) -> Path | None:
    candidate = (STATIC_DIR / relative).resolve()
    static_root = STATIC_DIR.resolve()
    if not str(candidate).startswith(str(static_root)):
        return None
    return candidate if candidate.is_file() else None


@app.get("/")
async def serve_root():
    index = _static_file("index.html")
    if index:
        return FileResponse(index, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    raise HTTPException(status_code=404, detail="SPA build not found")


@app.get("/assets/{asset_path:path}")
async def serve_assets(asset_path: str):
    asset = _static_file(f"assets/{asset_path}")
    if asset:
        return FileResponse(asset, headers={"Cache-Control": "public, max-age=31536000, immutable"})
    raise HTTPException(status_code=404, detail="Asset not found")


@app.get("/favicon.svg")
async def serve_favicon():
    icon = _static_file("favicon.svg")
    if icon:
        return FileResponse(icon)
    raise HTTPException(status_code=404, detail="Favicon not found")


@app.get("/documents/{rest:path}")
async def serve_spa_routes(rest: str):
    index = _static_file("index.html")
    if index:
        return FileResponse(index, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    raise HTTPException(status_code=404, detail="SPA build not found")
