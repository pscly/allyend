"""
全局常量定义模块。
- 日志等级映射
- 主题预设配置
- 功能/角色常量
"""
from __future__ import annotations

from typing import Dict, List


LOG_LEVEL_CODE_TO_NAME: Dict[int, str] = {
    0: "TRACE",
    10: "DEBUG",
    20: "INFO",
    30: "WARNING",
    40: "ERROR",
    50: "CRITICAL",
}

LOG_LEVEL_NAME_TO_CODE: Dict[str, int] = {name: code for code, name in LOG_LEVEL_CODE_TO_NAME.items()}

LOG_LEVEL_OPTIONS = [
    {"code": code, "name": name}
    for code, name in sorted(LOG_LEVEL_CODE_TO_NAME.items(), key=lambda item: item[0])
]

THEME_PRESETS = {
    "classic": {
        "label": "经典蓝绿",
        "primary": "#10b981",
        "secondary": "#1f2937",
        "background": "#f9fafb",
        "text": "#111827",
    },
    "ocean": {
        "label": "海湾蓝",
        "primary": "#06b6d4",
        "secondary": "#0f172a",
        "background": "#e0f2fe",
        "text": "#082f49",
    },
    "sunset": {
        "label": "日落橙",
        "primary": "#f97316",
        "secondary": "#7c2d12",
        "background": "#fff7ed",
        "text": "#431407",
    },
}

DEFAULT_THEME_KEY = "classic"

# ---- 角色与功能 ----
ROLE_USER = "user"
ROLE_ADMIN = "admin"
ROLE_SUPERADMIN = "superadmin"

FEATURE_CRAWLERS = "crawlers"
FEATURE_FILES = "files"

DEFAULT_GROUP_BLUEPRINTS: List[dict] = [
    {
        "name": "默认用户组",
        "slug": "general",
        "description": "普通用户组，默认仅开放文件服务",
        "is_default": True,
        "enable_crawlers": False,
        "enable_files": True,
    },
    {
        "name": "管理员组",
        "slug": "admins",
        "description": "具备全部功能的管理员组",
        "is_default": False,
        "enable_crawlers": True,
        "enable_files": True,
    },
]

# ---- 其他常量 ----
MIN_QUICK_LINK_LENGTH = 6
FILE_STORAGE_DIR = "data/files"
ANONYMOUS_FILE_PREFIX = "anon"
