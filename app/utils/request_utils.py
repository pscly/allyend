"""
请求与网络辅助工具（统一入口）。

目标：
- 统一从 Request 中提取“尽可能可靠”的客户端 IP（兼容反向代理、多级代理、直连）。
- 统一处理逗号分隔的 IP/CIDR 白名单字符串，供 API Key / 文件令牌等功能复用。

说明：
- 本项目在 `app/main.py` 中启用了 ProxyHeadersMiddleware，正常情况下 `request.client`
  已经是“可信代理解析后”的地址；但在直连开发环境或代理未正确设置头部时，仍需要兜底。
- 任何来自 Header 的值都可能被伪造；最终是否可信取决于上游代理是否被正确限制
  （例如 `.env` 中的 `FORWARDED_TRUSTED_IPS`）。
"""

from __future__ import annotations

import ipaddress
import re
from typing import Optional

from fastapi import Request

_FORWARDED_FOR_RE = re.compile(r"for=(?P<value>[^;]+)", flags=re.IGNORECASE)


def _strip_quotes(value: str) -> str:
    v = (value or "").strip()
    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        return v[1:-1].strip()
    return v


def _normalize_ip_candidate(raw: str) -> str:
    """
    将各种 header 里常见的 IP 表达归一化为可解析的 IP 字符串。

    支持示例：
    - "1.2.3.4"
    - "1.2.3.4, 5.6.7.8"（取首个）
    - "1.2.3.4:12345"（剥离端口）
    - "[2001:db8::1]:12345"（剥离方括号与端口）
    - Forwarded: for=1.2.3.4;proto=https 或 for="[2001:db8::1]:1234"
    """
    if not raw:
        return ""
    text = str(raw).strip()

    # X-Forwarded-For 多值：取最左侧真实客户端
    if "," in text:
        text = text.split(",", 1)[0].strip()

    # Forwarded: for=...
    m = _FORWARDED_FOR_RE.search(text)
    if m:
        text = m.group("value").strip()

    text = _strip_quotes(text)

    # IPv6 + 端口："[ip]:port"
    if text.startswith("[") and "]" in text:
        text = text[1 : text.index("]")].strip()

    # IPv4 + 端口："ip:port"（IPv6 不在此分支处理）
    if text.count(":") == 1:
        left, right = text.rsplit(":", 1)
        if right.isdigit():
            text = left.strip()

    return text.strip()


def _is_valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def get_client_ip(request: Request) -> Optional[str]:
    """
    获取客户端 IP（字符串）。

    优先级：
    1) 常见代理/网关头部（取首个值）
    2) request.client.host 兜底（在 ProxyHeadersMiddleware 正常配置时通常最可靠）
    """
    header_candidates = (
        "CF-Connecting-IP",
        "X-Real-IP",
        "X-client_ip",
        "X-Forwarded-For",
        "Forwarded",
    )
    for header in header_candidates:
        raw = request.headers.get(header)
        if not raw:
            continue
        normalized = _normalize_ip_candidate(raw)
        if normalized and _is_valid_ip(normalized):
            return normalized

    if request.client and request.client.host and _is_valid_ip(request.client.host):
        return request.client.host
    return request.client.host if request.client else None


def split_csv(value: Optional[str]) -> list[str]:
    """
    将逗号分隔字符串拆分为列表，自动忽略空项，并兼容换行符。
    """
    if not value:
        return []
    normalized = str(value).replace("\r", ",").replace("\n", ",")
    items = [item.strip() for item in normalized.split(",")]
    return [item for item in items if item]


def ip_in_allowlist(client_ip: Optional[str], allowlist: Optional[str]) -> bool:
    """
    判断 client_ip 是否命中 allowlist（逗号分隔），支持 IP 与 CIDR 混写。

    规则：
    - allowlist 为空/None：视为不限制（True）
    - client_ip 为空且 allowlist 非空：视为不允许（False）
    - allowlist 中的非法项会被忽略（不影响其他合法项判断）
    """
    entries = split_csv(allowlist)
    if not entries:
        return True
    if not client_ip:
        return False

    try:
        ip_obj = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    for entry in entries:
        token = entry.strip()
        if not token:
            continue
        if token in {"*", "all", "ANY"}:
            return True
        try:
            # CIDR
            if "/" in token:
                if ip_obj in ipaddress.ip_network(token, strict=False):
                    return True
                continue
            # 精确 IP
            if ip_obj == ipaddress.ip_address(token):
                return True
        except ValueError:
            continue
    return False


__all__ = ["get_client_ip", "split_csv", "ip_in_allowlist"]

