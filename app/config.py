"""
应用配置加载模块
- 所有配置从 .env 加载（UTF-8）
- 通过 pydantic-settings 提供类型安全的设置对象
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置（.env）"""

    SECRET_KEY: str = "please_change_me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    ALGORITHM: str = "HS256"

    DATABASE_URL: str = "sqlite:///./data/app.db"

    HOST: str = "0.0.0.0"
    PORT: int = 9093
    SITE_ICP: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
