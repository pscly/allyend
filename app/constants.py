"""
全局常量定义模块。
- 日志等级映射
- 主题预设配置
"""
from __future__ import annotations

from typing import Dict


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
