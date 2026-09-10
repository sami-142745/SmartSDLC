from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MONGODB_URI: str = "mongodb://mongo:27017/smart_sdlc"

    JWT_SECRET: str = "change_me"
    JWT_EXPIRES_SECONDS: int = 3600
    OAUTH_STATE_TTL_SECONDS: int = 600

    GITHUB_CLIENT_ID: str = "change_me"
    GITHUB_CLIENT_SECRET: str = "change_me"
    GITHUB_OAUTH_CALLBACK_URL: str = "http://localhost:8000/auth/github/callback"

    GEMINI_API_KEY: str = "change_me"
    GEMINI_MODEL: str = "gemini-2.5-flash"

    SEVERITY_HEURISTIC_SEC_WEIGHT: float = 0.6
    SEVERITY_HEURISTIC_COMPLEXITY_WEIGHT: float = 0.3
    SEVERITY_HISTORY_WEIGHT: float = 0.1

    REVIEW_MAX_FILES: int = 30
    REVIEW_MAX_FILE_CHARS: int = 20000
    REVIEW_MAX_DIFF_CHARS: int = 150000

    CORS_ORIGINS: str = "http://localhost:5173"

    GITHUB_WEBHOOK_SECRET: str = "change_me"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()

