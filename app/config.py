"""
应用配置加载模块
- 所有配置从 .env 加载（UTF-8）
- 通过 pydantic-settings 提供类型安全的设置对象
"""
from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置（.env）"""

    SITE_NAME: str = "AllYend"
    TIMEZONE: str | None = "Asia/Shanghai"

    SECRET_KEY: str = "please_change_me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    ALGORITHM: str = "HS256"

    DATABASE_URL: str = "sqlite:///./data/app.db"

    HOST: str = "0.0.0.0"
    PORT: int = 9093
    SITE_ICP: str = ""

    ROOT_ADMIN_USERNAME: str = "root"
    ROOT_ADMIN_INVITE_CODE: str = "ALLYEND-ROOT"
    ROOT_ADMIN_PASSWORD: str | None = None
    DEFAULT_ADMIN_INVITE_CODE: str = "ALLYEND-ADMIN"
    DEFAULT_USER_INVITE_CODE: str | None = None
    ALLOW_DIRECT_SIGNUP: bool = True

    FILE_STORAGE_DIR: str = "data/files"
    LOG_DIR: str = "logs"

    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_USE_TLS: bool = True
    ALERT_EMAIL_SENDER: str | None = None
    ALERT_WEBHOOK_TIMEOUT: float = 5.0

    FRONTEND_ORIGINS: list[str] = ["http://localhost:3000"]

    # Cookie 会话配置
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"  # 可选："lax" | "strict" | "none"
    COOKIE_DOMAIN: str | None = None
    COOKIE_PATH: str = "/"

    @field_validator("FRONTEND_ORIGINS", mode="before")
    @classmethod
    def _normalize_frontend_origins(cls, value):
        """支持逗号分隔或 JSON 数组形式的域名配置"""
        if value in (None, "", []):
            return ["http://localhost:3000"]
        if isinstance(value, str):
            items = [item.strip() for item in value.split(',') if item.strip()]
            return items or ["http://localhost:3000"]
        if isinstance(value, (tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return list(value)

    @field_validator("COOKIE_SAMESITE", mode="before")
    @classmethod
    def _normalize_cookie_samesite(cls, value: str) -> str:
        if value is None:
            return "lax"
        v = str(value).strip().lower()
        if v not in {"lax", "strict", "none"}:
            return "lax"
        return v

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
