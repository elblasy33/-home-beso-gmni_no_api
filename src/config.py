from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False

    HEADLESS: bool = True
    BROWSER_PROFILE_DIR: str = str(BASE_DIR / "data" / "browser_profile")
    ARTIFACTS_DIR: str = str(BASE_DIR / "data" / "artifacts")
    UPLOADS_DIR: str = str(BASE_DIR / "data" / "uploads")
    CONFIGS_DIR: str = str(BASE_DIR / "configs")

    DEFAULT_PAGE_TIMEOUT: int = 60
    DEFAULT_RESPONSE_TIMEOUT: int = 180
    ENABLE_TRACING: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def ensure_directories(self):
        """Ensure all required runtime data directories exist."""
        for path_str in [
            self.BROWSER_PROFILE_DIR,
            self.ARTIFACTS_DIR,
            self.UPLOADS_DIR,
            self.CONFIGS_DIR,
        ]:
            Path(path_str).mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_directories()
