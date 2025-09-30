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
    # 是否启用应用层访问日志兜底（当 Uvicorn 未开启 --access-log 时仍记录访问日志）
    APP_ACCESS_LOG: bool = True

    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_USE_TLS: bool = True
    ALERT_EMAIL_SENDER: str | None = None
    ALERT_WEBHOOK_TIMEOUT: float = 5.0

    FRONTEND_ORIGINS: list[str] = ["http://localhost:3000"]
    # 反向代理可信地址（用于解析 X-Forwarded-*），逗号分隔
    FORWARDED_TRUSTED_IPS: list[str] = ["127.0.0.1", "::1"]

    # 日志查询频控（每账号每秒最大请求数）
    LOG_QUERY_RATE_PER_SECOND: int = 5

    # 日志配额与清理策略（可在 .env 覆盖）
    # 每个用户的日志总配额（字节），默认 300MB；设为 -1 表示无限制
    DEFAULT_USER_LOG_QUOTA_BYTES: int = 300 * 1024 * 1024
    # 单个爬虫的日志上限：行数与字节（默认 100 万行或 100MB）；设为 <=0 则采用默认
    DEFAULT_CRAWLER_LOG_MAX_LINES: int = 1_000_000
    DEFAULT_CRAWLER_LOG_MAX_BYTES: int = 100 * 1024 * 1024
    # 超限时滚动清理的批次（每次删除的行数）
    LOG_TRIM_CHUNK_LINES: int = 10_000

    # 趋势统计缓存 TTL（秒）
    STATS_CACHE_TTL_SECONDS: int = 60

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

    @field_validator("FORWARDED_TRUSTED_IPS", mode="before")
    @classmethod
    def _normalize_trusted_ips(cls, value):
        """支持逗号分隔或 JSON 数组形式的 IP/CIDR 列表"""
        if value in (None, "", []):
            return ["127.0.0.1", "::1"]
        if isinstance(value, str):
            items = [item.strip() for item in value.split(',') if item.strip()]
            return items or ["127.0.0.1", "::1"]
        if isinstance(value, (tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return list(value)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
