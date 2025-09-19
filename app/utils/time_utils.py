"""时间与时区工具
- 支持通过 .env 配置自定义时区
- 默认回退到系统本地时间
"""
from __future__ import annotations

import logging
from datetime import datetime
from functools import lru_cache

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]
    ZoneInfoNotFoundError = Exception  # type: ignore[assignment]

from ..config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_app_timezone() -> ZoneInfo | None:
    """加载应用配置的时区"""
    tz_name = settings.TIMEZONE
    if not tz_name:
        return None
    if ZoneInfo is None:
        logger.warning("当前运行环境缺少 zoneinfo，已回退到系统时区")
        return None
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("无法加载时区 %s，已回退到系统时区", tz_name)
        return None


def aware_now() -> datetime:
    """返回带时区信息的当前时间"""
    tz = get_app_timezone()
    if tz is not None:
        return datetime.now(tz)
    return datetime.now().astimezone()


def now() -> datetime:
    """返回适合现有数据库的本地时间（去除 tzinfo）"""
    current = aware_now()
    if current.tzinfo is not None:
        return current.replace(tzinfo=None)
    return current


__all__ = ["aware_now", "now", "get_app_timezone"]
