"""
操作审计工具函数（统一在此落库，便于跨路由复用）

注意：仅记录必要信息，避免写入敏感字段（例如 API Key 明文）。
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models import OperationAuditLog, User, APIKey, CrawlerGroup


def _actor_name(user: Optional[User]) -> Optional[str]:
    if not user:
        return None
    return (user.display_name or user.username or "").strip() or None


def summarize_api_key(key: APIKey) -> dict[str, Any]:
    """提炼 API Key 关键字段（不含敏感明文 key）。"""
    return {
        "id": key.id,
        "local_id": key.local_id,
        "name": key.name,
        "description": key.description,
        "active": key.active,
        "is_public": key.is_public,
        "group_id": key.group_id,
        "group_slug": key.group.slug if getattr(key, "group", None) else None,
        "allowed_ips": key.allowed_ips,
        "last_used_at": key.last_used_at,
        "last_used_ip": key.last_used_ip,
    }


def summarize_group(group: CrawlerGroup) -> dict[str, Any]:
    return {
        "id": group.id,
        "name": group.name,
        "slug": group.slug,
        "description": group.description,
        "color": group.color,
    }


def record_operation(
    db: Session,
    *,
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    actor: Optional[User] = None,
    actor_ip: Optional[str] = None,
) -> OperationAuditLog:
    """写入操作审计记录（由调用方控制事务提交时机）。"""
    rec = OperationAuditLog(
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_name=target_name,
        before=before or None,
        after=after or None,
        actor=actor,
        actor_name=_actor_name(actor),
        actor_ip=actor_ip,
    )
    db.add(rec)
    # 不在这里 commit，交由上层路由统一提交
    return rec

