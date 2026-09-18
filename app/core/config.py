"""Application configuration settings for the GUTSESS backend."""

from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings


BACKEND_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_ROOT / ".env"

# Load the backend's environment file regardless of the process working directory.
load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DB_ENGINE: str = Field(default="mysql")  # Set to 'mysql' for MySQL usage
    DB_HOST: str = Field(default="localhost")  # MySQL host
    DB_PORT: int = Field(default=3306)  # MySQL port
    DB_USER: str = Field(default="root")  # MySQL user
    DB_PASSWORD: str = Field(default="")  # MySQL password
    DB_NAME: str = Field(default="pbac_db")  # MySQL database name
    SQLITE_PATH: str = Field(default="pbac.db")  # Only used if DB_ENGINE is 'sqlite'

    # JWT security
    SECRET_KEY: str = Field(default="change-this-in-production")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)

    # Email and frontend
    SMTP_HOST: str = Field(default="smtp.gmail.com")
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: str = Field(default="")
    SMTP_PASS: str = Field(default="")
    EMAIL_FROM: str = Field(default="")
    FRONTEND_URL: str = Field(default="http://localhost:5173")
    RESET_EXPIRE_MINUTES: int = Field(default=15)

    # MFA
    MFA_ISSUER_NAME: str = Field(default="PBAC-System")

    # Media storage. Relative paths are resolved from the backend project root.
    MEDIA_STORAGE_PATH: Path = Field(default=Path("storage/development"))

    @property
    def access_token_expire_timedelta(self) -> timedelta:
        return timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)

    class Config:
        env_file = ENV_FILE
        env_file_encoding = "utf-8"
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
