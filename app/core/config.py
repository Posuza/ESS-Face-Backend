"""
Application configuration settings for PBAC system.
"""

# Ensure .env file is loaded before settings are read
from dotenv import load_dotenv

load_dotenv()

from datetime import timedelta
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


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

    # JWT Security
    SECRET_KEY: str = Field(default="change-this-in-production")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    # Email / frontend
    SMTP_HOST: str = Field(default="smtp.gmail.com")
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: str = Field(default="")
    SMTP_PASS: str = Field(default="")
    EMAIL_FROM: str = Field(default="")
    FRONTEND_URL: str = Field(default="http://localhost:5173")
    RESET_EXPIRE_MINUTES: int = Field(default=15)

    # MFA
    MFA_ISSUER_NAME: str = Field(default="PBAC-System")

    @property
    def access_token_expire_timedelta(self) -> timedelta:
        return timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    # Note: To use MySQL, set DB_ENGINE to 'mysql' and provide DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, and DB_NAME in your environment or .env file.


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
