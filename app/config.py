"""
应用配置加载模块
- 所有配置从 .env 加载（UTF-8）
- 通过 pydantic-settings 提供类型安全的设置对象
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置（.env）"""

    SITE_NAME: str = "AllYend"

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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
