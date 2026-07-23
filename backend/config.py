"""애플리케이션 설정 및 경로 상수.

역할: .env 기반 Settings, 데이터·업로드·DB·이미지·프롬프트 디렉터리 경로를 정의한다.
주요 기능: Upstage API 키·mock 모드, Vercel/로컬 환경별 DATA_DIR 분기, 디렉터리 자동 생성.
관계: database, services, routers가 settings와 경로 상수를 import한다.
"""

from pathlib import Path
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
IS_VERCEL = os.getenv("VERCEL") == "1"

if IS_VERCEL:
    DATA_DIR = Path("/tmp/easyread")
else:
    DATA_DIR = ROOT_DIR / "data"

UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "app.db"
IMAGES_DIR = ROOT_DIR / "images"
PROMPTS_DIR = BACKEND_DIR / "prompts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    upstage_api_key: str = ""
    mock_upstage: bool = True
    backend_host: str = "0.0.0.0"
    backend_port: int = 8001
    convertapi_secret: str = ""
    admin_emails: str = ""  # comma-separated login emails for storage admin

    upstage_ocr_url: str = "https://api.upstage.ai/v1/document-digitization"
    upstage_chat_url: str = "https://api.upstage.ai/v1/solar/chat/completions"
    solar_model: str = "solar-pro"

    @property
    def use_mock(self) -> bool:
        if not self.upstage_api_key.strip():
            return True
        return self.mock_upstage


settings = Settings()

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
