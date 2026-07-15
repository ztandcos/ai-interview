from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Interview Copilot"
    PROJECT_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "ai_interview"

    JWT_SECRET_KEY: str = "change-this-secret-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    VERIFICATION_CODE_TTL_SECONDS: int = 300
    VERIFICATION_SEND_COOLDOWN_SECONDS: int = 60

    UPLOAD_DIR: str = "uploads/resumes"
    MAX_RESUME_FILE_SIZE_BYTES: int = 5 * 1024 * 1024
    RESUME_CHUNK_SIZE: int = 800
    RESUME_CHUNK_OVERLAP: int = 120
    RESUME_SEARCH_DEFAULT_TOP_K: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            "mysql+aiomysql://"
            f"{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )

    @property
    def REDIS_URL(self) -> str:
        password = ""
        if self.REDIS_PASSWORD:
            password = f":{quote(self.REDIS_PASSWORD, safe='')}@"
        return f"redis://{password}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


settings = Settings()
