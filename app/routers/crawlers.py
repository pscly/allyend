"""
爬虫接入与监控 API：
- 统一归属到 /pa 路径
- 支持快捷访问链接、来源 IP 记录
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import re
import math
from typing import List, Optional, Sequence

import json
import logging
import secrets
import smtplib
import ssl
from email.message import EmailMessage

import requests
import time
import threading

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from ..constants import (
    LOG_LEVEL_CODE_TO_NAME,
    LOG_LEVEL_NAME_TO_CODE,
    LOG_LEVEL_OPTIONS,
    MIN_QUICK_LINK_LENGTH,
    ROLE_ADMIN,
    ROLE_SUPERADMIN,
    THEME_PRESETS,
)
from ..config import settings
from ..dependencies import get_current_user, get_db
from ..models import (
    APIKey,
    Crawler,
    CrawlerAccessLink,
    CrawlerAlertEvent,
    CrawlerAlertRule,
    CrawlerAlertState,
    CrawlerCommand,
    CrawlerConfigAssignment,
    CrawlerConfigTemplate,
    CrawlerGroup,
    CrawlerHeartbeat,
    CrawlerRun,
    LogEntry,
    User,
)
from ..schemas import (
    AlertChannelConfig,
    CrawlerAlertEventOut,
    CrawlerAlertRuleCreate,
    CrawlerAlertRuleOut,
    CrawlerAlertRuleUpdate,
    CrawlerCommandAck,
    CrawlerCommandCreate,
    CrawlerCommandOut,
    CrawlerConfigAssignmentCreate,
    CrawlerConfigAssignmentOut,
    CrawlerConfigAssignmentUpdate,
    CrawlerConfigFetchOut,
    CrawlerConfigTemplateCreate,
    CrawlerConfigTemplateOut,
    CrawlerConfigTemplateUpdate,
    CrawlerGroupCreate,
    CrawlerGroupOut,
    CrawlerGroupUpdate,
    CrawlerHeartbeatOut,
    CrawlerOut,
    CrawlerRegisterRequest,
    CrawlerUpdate,
    HeartbeatPayload,
    LogCreate,
    LogOut,
    LogUsageOut,
    UserLogUsageOut,
    QuickLinkCreate,
    QuickLinkUpdate,
    QuickLinkOut,
    RunOut,
    RunStartResponse,
)
from ..utils.time_utils import now
from ..utils.audit import record_operation, summarize_group


api_router = APIRouter(prefix="/pa/api", tags=["pa-crawlers"])
public_router = APIRouter(prefix="/pa", tags=["pa-public"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
templates.env.globals.update(
    site_icp=settings.SITE_ICP,
    theme_presets=THEME_PRESETS,
    log_levels=LOG_LEVEL_OPTIONS,
    site_name=settings.SITE_NAME,
)

LEVEL_CODES = sorted(LOG_LEVEL_CODE_TO_NAME.keys())
LEVEL_ALIASES = {"WARN": "WARNING", "ERR": "ERROR", "FATAL": "CRITICAL"}

HEARTBEAT_ONLINE_SECONDS = 5 * 60
HEARTBEAT_WARN_SECONDS = 15 * 60
COMMAND_FETCH_BATCH = 5
MAX_REGEX_SCAN = 5000  # 后端正则筛选的最大扫描条数（保护数据库与内存）
TRIM_CHUNK = max(1000, int(getattr(settings, "LOG_TRIM_CHUNK_LINES", 10_000) or 10_000))
STATS_CACHE_TTL = max(0, int(getattr(settings, "STATS_CACHE_TTL_SECONDS", 60) or 60))
_PUBLIC_STATS_CACHE: dict[tuple, tuple[float, dict]] = {}
_PRIVATE_STATS_CACHE: dict[tuple, tuple[float, dict]] = {}

# 简易内存频控：每账号每秒最大查询次数（多实例部署建议换成 Redis 实现）
_LOG_RATE_BUCKETS: dict[int, list[float]] = {}
_LOG_RATE_LOCK = threading.Lock()


def _enforce_log_rate_limit(user_id: int) -> None:
    limit = max(1, int(getattr(settings, "LOG_QUERY_RATE_PER_SECOND", 5) or 5))
    now = time.time()
    window_begin = now - 1.0
    with _LOG_RATE_LOCK:
        arr = _LOG_RATE_BUCKETS.get(user_id) or []
        # 清理过期时间戳
        arr = [ts for ts in arr if ts >= window_begin]
        if len(arr) >= limit:
            raise HTTPException(status_code=429, detail="查询过于频繁，请稍后再试")
        arr.append(now)
        _LOG_RATE_BUCKETS[user_id] = arr


def _normalize_level_code(code: int) -> int:
    return min(LEVEL_CODES, key=lambda x: abs(x - code))


def _resolve_log_level(payload: LogCreate) -> tuple[str, int]:
    if payload.level_code is not None:
        normalized = _normalize_level_code(payload.level_code)
        name = LOG_LEVEL_CODE_TO_NAME.get(normalized, "INFO")
        return name, normalized
    level_name = (payload.level or "INFO").upper()
    canonical = LEVEL_ALIASES.get(level_name, level_name)
    if canonical in LOG_LEVEL_NAME_TO_CODE:
        return canonical, LOG_LEVEL_NAME_TO_CODE[canonical]
    return "INFO", LOG_LEVEL_NAME_TO_CODE["INFO"]


# ---------- 日志配额与清理辅助 ----------

def _effective_crawler_limits(crawler: Crawler) -> tuple[int | None, int | None]:
    """返回爬虫的有效日志上限（行/字节）。

    - None 表示不限制对应维度
    - 读取 crawler.log_max_*，若为空或 <=0 则回退为系统默认；为负值表示不限制
    """
    max_lines: int | None
    max_bytes: int | None
    if crawler.log_max_lines is None:
        max_lines = int(getattr(settings, "DEFAULT_CRAWLER_LOG_MAX_LINES", 1_000_000) or 1_000_000)
    else:
        max_lines = None if int(crawler.log_max_lines) <= 0 else int(crawler.log_max_lines)
    if crawler.log_max_bytes is None:
        max_bytes = int(getattr(settings, "DEFAULT_CRAWLER_LOG_MAX_BYTES", 100 * 1024 * 1024) or (100 * 1024 * 1024))
    else:
        max_bytes = None if int(crawler.log_max_bytes) <= 0 else int(crawler.log_max_bytes)
    return max_lines, max_bytes


def _effective_user_quota(user: User) -> int | None:
    """返回用户日志总配额（字节）。None 表示无限制。"""
    if user.log_quota_bytes is None:
        return int(getattr(settings, "DEFAULT_USER_LOG_QUOTA_BYTES", 300 * 1024 * 1024) or (300 * 1024 * 1024))
    v = int(user.log_quota_bytes)
    return None if v <= 0 else v


def _measure_crawler_usage(db: Session, crawler_id: int) -> tuple[int, int]:
    """统计某爬虫日志行数与字节数。"""
    lines = db.query(func.count(LogEntry.id)).filter(LogEntry.crawler_id == crawler_id).scalar() or 0
    # 以数据库 length(Text) 近似表示字节占用（SQLite 返回字符数，足够近似）
    bytes_ = (
        db.query(func.coalesce(func.sum(func.length(LogEntry.message)), 0))
        .filter(LogEntry.crawler_id == crawler_id)
        .scalar()
        or 0
    )
    return int(lines), int(bytes_)


def _measure_user_usage(db: Session, user_id: int) -> tuple[int, int]:
    """统计用户所有爬虫的日志占用（行/字节）。"""
    lines = (
        db.query(func.count(LogEntry.id))
        .join(Crawler)
        .filter(Crawler.user_id == user_id)
        .scalar()
        or 0
    )
    bytes_ = (
        db.query(func.coalesce(func.sum(func.length(LogEntry.message)), 0))
        .join(Crawler)
        .filter(Crawler.user_id == user_id)
        .scalar()
        or 0
    )
    return int(lines), int(bytes_)


def _delete_oldest_crawler_logs(db: Session, crawler_id: int, n: int) -> int:
    """删除指定爬虫最旧的 n 条日志，返回删除数量。"""
    n = max(0, int(n or 0))
    if n <= 0:
        return 0
    ids = [
        r[0]
        for r in (
            db.query(LogEntry.id)
            .filter(LogEntry.crawler_id == crawler_id)
            .order_by(LogEntry.id.asc())
            .limit(n)
            .all()
        )
    ]
    if not ids:
        return 0
    deleted = db.query(LogEntry).filter(LogEntry.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return int(deleted or 0)


def _delete_oldest_user_logs(db: Session, user_id: int, n: int) -> int:
    """删除某用户最旧的 n 条日志（跨所有爬虫），返回删除数量。"""
    n = max(0, int(n or 0))
    if n <= 0:
        return 0
    ids = [
        r[0]
        for r in (
            db.query(LogEntry.id)
            .join(Crawler)
            .filter(Crawler.user_id == user_id)
            .order_by(LogEntry.id.asc())
            .limit(n)
            .all()
        )
    ]
    if not ids:
        return 0
    deleted = db.query(LogEntry).filter(LogEntry.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return int(deleted or 0)


def _enforce_crawler_limits(db: Session, crawler: Crawler) -> dict:
    """在单爬虫范围内执行配额清理：超限则每次删除 TRIM_CHUNK 条最旧日志。"""
    max_lines, max_bytes = _effective_crawler_limits(crawler)
    lines, bytes_ = _measure_crawler_usage(db, crawler.id)
    deleted_total = 0
    loop_guard = 0
    while True:
        need_delete = 0
        if max_lines is not None and lines > max_lines:
            need_delete = max(need_delete, min(TRIM_CHUNK, lines - max_lines))
        if max_bytes is not None and bytes_ > max_bytes:
            # 无法准确估算条->字节的映射，采用固定批量删除并循环校正
            need_delete = max(need_delete, TRIM_CHUNK)
        if need_delete <= 0:
            break
        deleted = _delete_oldest_crawler_logs(db, crawler.id, need_delete)
        deleted_total += deleted
        # 重新测量，避免长时间占用事务
        lines, bytes_ = _measure_crawler_usage(db, crawler.id)
        loop_guard += 1
        if loop_guard >= 20:  # 安全阈值，避免极端情况下循环过久
            break
    return {"deleted": deleted_total, "lines": lines, "bytes": bytes_}


def _enforce_user_quota(db: Session, user: User) -> dict:
    """在用户总量范围内执行配额清理。"""
    quota = _effective_user_quota(user)
    lines, bytes_ = _measure_user_usage(db, user.id)
    deleted_total = 0
    if quota is None:
        return {"deleted": 0, "lines": lines, "bytes": bytes_, "quota": None}
    loop_guard = 0
    while bytes_ > quota:
        deleted = _delete_oldest_user_logs(db, user.id, TRIM_CHUNK)
        if deleted <= 0:
            break
        deleted_total += deleted
        lines, bytes_ = _measure_user_usage(db, user.id)
        loop_guard += 1
        if loop_guard >= 50:
            break
    return {"deleted": deleted_total, "lines": lines, "bytes": bytes_, "quota": quota}


def _parse_id_list(raw: Optional[str]) -> List[int]:
    if not raw:
        return []
    ids: List[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.append(int(chunk))
        except ValueError:
            continue
    return ids



def _parse_group_filters(raw: Optional[str]) -> tuple[list[int], bool]:
    """解析分组过滤参数，支持 `none` 表示未分组。"""
    if not raw:
        return [], False
    ids: list[int] = []
    include_none = False
    for chunk in raw.split(','):
        chunk = chunk.strip()
        if not chunk:
            continue
        lowered = chunk.lower()
        if lowered in {"none", "null", "0"}:
            include_none = True
            continue
        try:
            ids.append(int(chunk))
        except ValueError:
            continue
    return ids, include_none


def _apply_log_filters(query, start: Optional[date], end: Optional[date], min_level: int, max_level: int):
    if start:
        start_dt = datetime.combine(start, time.min)
        query = query.filter(LogEntry.ts >= start_dt)
    if end:
        end_dt = datetime.combine(end, time.max)
        query = query.filter(LogEntry.ts <= end_dt)
    query = query.filter(LogEntry.level_code >= min_level)
    query = query.filter(LogEntry.level_code <= max_level)
    return query


def _ensure_quick_slug(db: Session, slug: Optional[str] = None) -> str:
    base = slug.strip() if slug else ""
    if base and len(base) < MIN_QUICK_LINK_LENGTH:
        raise HTTPException(status_code=400, detail=f"快捷链接长度至少 {MIN_QUICK_LINK_LENGTH} 位")
    while True:
        candidate = base or secrets.token_urlsafe(6)[:12].lower()
        if len(candidate) < MIN_QUICK_LINK_LENGTH:
            candidate = f"{candidate}{secrets.token_hex(3)}"
        exists = db.query(CrawlerAccessLink).filter(CrawlerAccessLink.slug == candidate).first()
        if not exists:
            return candidate
        base = ""


def _get_client_ip(request: Request) -> Optional[str]:
    if request.client:
        return request.headers.get("X-Real-IP")
    return None


def _compute_status(last_heartbeat: Optional[datetime]) -> str:
    if not last_heartbeat:
        return "offline"
    delta = (now() - last_heartbeat).total_seconds()
    if delta <= HEARTBEAT_ONLINE_SECONDS:
        return "online"
    if delta <= HEARTBEAT_WARN_SECONDS:
        return "warning"
    return "offline"


def _ensure_crawler_feature(user: User) -> None:
    if user.role in {ROLE_ADMIN, ROLE_SUPERADMIN}:
        return
    if user.group and not user.group.enable_crawlers:
        raise HTTPException(status_code=403, detail="当前分组未启用爬虫功能")




def _build_assignment_map(
    db: Session,
    user_id: int,
    crawler_ids: list[int],
    api_key_ids: list[int],
    group_ids: list[int],
) -> dict[str, dict[int, CrawlerConfigAssignment]]:
    assignments: dict[str, dict[int, CrawlerConfigAssignment]] = {
        "crawler": {},
        "api_key": {},
        "group": {},
    }
    conditions = []
    if crawler_ids:
        conditions.append(
            and_(
                CrawlerConfigAssignment.target_type == "crawler",
                CrawlerConfigAssignment.target_id.in_(crawler_ids),
            )
        )
    if api_key_ids:
        conditions.append(
            and_(
                CrawlerConfigAssignment.target_type == "api_key",
                CrawlerConfigAssignment.target_id.in_(api_key_ids),
            )
        )
    if group_ids:
        conditions.append(
            and_(
                CrawlerConfigAssignment.target_type == "group",
                CrawlerConfigAssignment.target_id.in_(group_ids),
            )
        )
    if not conditions:
        return assignments
    rows = (
        db.query(CrawlerConfigAssignment)
        .options(joinedload(CrawlerConfigAssignment.template))
        .filter(
            CrawlerConfigAssignment.user_id == user_id,
            CrawlerConfigAssignment.is_active == True,
        )
        .filter(or_(*conditions))
        .all()
    )
    for item in rows:
        bucket = assignments.setdefault(item.target_type, {})
        bucket[item.target_id] = item
    return assignments


def _resolve_assignment_from_map(
    assignments: dict[str, dict[int, CrawlerConfigAssignment]],
    crawler: Crawler,
) -> CrawlerConfigAssignment | None:
    assignment = assignments.get("crawler", {}).get(crawler.id)
    if assignment:
        return assignment
    if crawler.api_key_id:
        assignment = assignments.get("api_key", {}).get(crawler.api_key_id)
        if assignment:
            return assignment
    if crawler.group_id:
        assignment = assignments.get("group", {}).get(crawler.group_id)
        if assignment:
            return assignment
    return None


def _get_effective_assignment(
    db: Session,
    user_id: int,
    crawler: Crawler,
) -> CrawlerConfigAssignment | None:
    return _resolve_assignment_from_map(
        _build_assignment_map(
            db,
            user_id,
            [crawler.id],
            [crawler.api_key_id] if crawler.api_key_id else [],
            [crawler.group_id] if crawler.group_id else [],
        ),
        crawler,
    )


def _maybe_apply_message_search(query, q: Optional[str], use_regex: bool):
    """为日志查询附加消息筛选。

    - 关键字：使用 ilike 走数据库模糊查询。
    - 正则：返回编译后的模式，由调用方在取出记录后进行 Python 端过滤。
    返回值：(query, pattern)
    """
    if not q or not str(q).strip():
        return query, None
    text = str(q).strip()
    if not use_regex:
        return query.filter(LogEntry.message.ilike(f"%{text}%")), None
    try:
        pattern = re.compile(text)
    except re.error:
        # 无效正则时回退为包含匹配（数据库）
        return query.filter(LogEntry.message.ilike(f"%{text}%")), None
    return query, pattern


def _apply_assignment_metadata(
    crawler: Crawler,
    assignment: CrawlerConfigAssignment | None,
) -> None:
    crawler.config_assignment_id = assignment.id if assignment else None
    crawler.config_assignment_name = assignment.name if assignment else None
    crawler.config_assignment_version = assignment.version if assignment else None
    crawler.config_assignment_format = assignment.format if assignment else None


def _get_nested_payload_value(payload: dict | None, field_path: str | None):
    if not payload or not field_path:
        return None
    current = payload
    for part in field_path.split('.'):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _compare_threshold(value: float | int | None, threshold: float | None, comparator: str | None) -> bool:
    if threshold is None or comparator is None:
        return False
    try:
        numeric = float(value) if value is not None else None
    except (TypeError, ValueError):
        return False
    if numeric is None:
        return False
    if comparator == "gt":
        return numeric > threshold
    if comparator == "ge":
        return numeric >= threshold
    if comparator == "lt":
        return numeric < threshold
    if comparator == "le":
        return numeric <= threshold
    if comparator == "eq":
        return numeric == threshold
    if comparator == "ne":
        return numeric != threshold
    return False


def _match_alert_rule_target(rule: CrawlerAlertRule, crawler: Crawler) -> bool:
    targets = rule.target_ids or []
    if rule.target_type == "all" or not targets:
        return True
    if rule.target_type == "crawler":
        return crawler.id in targets
    if rule.target_type == "api_key":
        return crawler.api_key_id in targets
    if rule.target_type == "group":
        return (crawler.group_id or 0) in targets
    return False


def _get_or_create_alert_state(
    db: Session,
    rule: CrawlerAlertRule,
    crawler: Crawler,
) -> CrawlerAlertState:
    state = (
        db.query(CrawlerAlertState)
        .filter(
            CrawlerAlertState.rule_id == rule.id,
            CrawlerAlertState.crawler_id == crawler.id,
        )
        .first()
    )
    if not state:
        state = CrawlerAlertState(
            rule_id=rule.id,
            crawler_id=crawler.id,
            user_id=rule.user_id,
            consecutive_hits=0,
            context={},
        )
        db.add(state)
        db.flush()
    return state


def _in_cooldown(rule: CrawlerAlertRule, state: CrawlerAlertState) -> bool:
    cooldown = max(rule.cooldown_minutes or 0, 0)
    if cooldown <= 0 or not state.last_triggered_at:
        return False
    delta = now() - state.last_triggered_at
    return delta.total_seconds() < cooldown * 60


def _evaluate_status_rule(
    rule: CrawlerAlertRule,
    state: CrawlerAlertState,
    previous_status: str | None,
    current_status: str,
) -> tuple[bool, str, dict]:
    if current_status != "offline":
        state.consecutive_hits = 0
        state.last_status = current_status
        return False, "", {}
    if previous_status != "offline":
        state.consecutive_hits = 1
    else:
        state.consecutive_hits += 1
    state.last_status = current_status
    if state.consecutive_hits < max(rule.consecutive_failures or 1, 1):
        return False, "", {}
    message = f"status changed from {previous_status or 'unknown'} to offline"
    payload = {"previous_status": previous_status, "current_status": current_status}
    return True, message, payload


def _evaluate_payload_rule(
    rule: CrawlerAlertRule,
    state: CrawlerAlertState,
    payload: dict | None,
) -> tuple[bool, str, dict]:
    value = _get_nested_payload_value(payload or {}, rule.payload_field)
    state.last_value = float(value) if isinstance(value, (int, float)) else None
    state.context = state.context or {}
    state.context.update({"last_value": value})
    if not _compare_threshold(value, rule.threshold, rule.comparator):
        state.consecutive_hits = 0
        return False, "", {}
    state.consecutive_hits += 1
    if state.consecutive_hits < max(rule.consecutive_failures or 1, 1):
        return False, "", {}
    message = (
        f"heartbeat field {rule.payload_field} value {value} matched {rule.comparator or 'gt'} {rule.threshold}"
    )
    payload_data = {
        "field": rule.payload_field,
        "value": value,
        "threshold": rule.threshold,
        "comparator": rule.comparator,
    }
    return True, message, payload_data


def _dispatch_alert_event(
    rule: CrawlerAlertRule,
    event: CrawlerAlertEvent,
    crawler: Crawler,
    extra_payload: dict,
) -> None:
    channels = rule.channels or []
    results: list[dict] = []
    if not channels:
        results.append({"type": "none", "status": "skipped", "detail": "no channels"})
    for channel in channels:
        channel_type = channel.get("type")
        target = channel.get("target")
        enabled = channel.get("enabled", True)
        if not enabled:
            results.append({
                "type": channel_type,
                "target": target,
                "status": "skipped",
                "detail": "disabled",
            })
            continue
        if not target:
            results.append({
                "type": channel_type,
                "status": "failed",
                "detail": "missing target",
            })
            continue
        if channel_type == "email":
            results.append(_send_email_alert(rule, crawler, event, target, extra_payload))
        elif channel_type == "webhook":
            results.append(_send_webhook_alert(rule, crawler, event, target, extra_payload))
        else:
            results.append({
                "type": channel_type,
                "target": target,
                "status": "skipped",
                "detail": "unsupported",
            })
    event.channel_results = results
    if any(item.get("status") == "failed" for item in results):
        event.status = "failed"
        details = [item.get("detail") for item in results if item.get("status") == "failed" and item.get("detail")]
        if details:
            event.error = "; ".join(details)
    elif any(item.get("status") == "sent" for item in results):
        event.status = "sent"
    else:
        event.status = "skipped"


def _send_email_alert(
    rule: CrawlerAlertRule,
    crawler: Crawler,
    event: CrawlerAlertEvent,
    target: str,
    extra_payload: dict,
) -> dict:
    host = settings.SMTP_HOST
    if not host:
        return {
            "type": "email",
            "target": target,
            "status": "failed",
            "detail": "smtp not configured",
        }
    sender = settings.ALERT_EMAIL_SENDER or settings.SMTP_USERNAME or "allyend@noreply"
    message = EmailMessage()
    message["Subject"] = f"[Alert] crawler {crawler.name} offline"
    message["From"] = sender
    message["To"] = target
    lines = [
        f"rule: {rule.name}",
        f"crawler: {crawler.name}",
        f"local id: {crawler.local_id}",
        f"status: {crawler.status}",
        f"triggered_at: {event.triggered_at.isoformat()}",
    ]
    if extra_payload:
        lines.append(f"payload: {json.dumps(extra_payload, ensure_ascii=False)}")
    # 使用换行符拼接邮件正文内容
    message.set_content("\n".join(lines))
    try:
        if settings.SMTP_USE_TLS:
            context = ssl.create_default_context()
            with smtplib.SMTP(host, settings.SMTP_PORT) as server:
                server.starttls(context=context)
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, settings.SMTP_PORT) as server:
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(message)
        return {"type": "email", "target": target, "status": "sent"}
    except Exception as exc:
        logging.exception("send email alert failed", exc_info=exc)
        return {
            "type": "email",
            "target": target,
            "status": "failed",
            "detail": str(exc),
        }


def _send_webhook_alert(
    rule: CrawlerAlertRule,
    crawler: Crawler,
    event: CrawlerAlertEvent,
    target: str,
    extra_payload: dict,
) -> dict:
    timeout = settings.ALERT_WEBHOOK_TIMEOUT or 5.0
    body = {
        "rule": {
            "id": rule.id,
            "name": rule.name,
            "trigger_type": rule.trigger_type,
        },
        "crawler": {
            "id": crawler.id,
            "local_id": crawler.local_id,
            "name": crawler.name,
            "status": crawler.status,
        },
        "event": {
            "id": event.id,
            "triggered_at": event.triggered_at.isoformat(),
            "message": event.message,
        },
        "payload": extra_payload,
    }
    try:
        response = requests.post(target, json=body, timeout=timeout)
        if response.status_code >= 400:
            detail = f"HTTP {response.status_code}: {response.text[:200]}"
            return {
                "type": "webhook",
                "target": target,
                "status": "failed",
                "detail": detail,
            }
        return {"type": "webhook", "target": target, "status": "sent"}
    except Exception as exc:
        logging.exception("send webhook alert failed", exc_info=exc)
        return {
            "type": "webhook",
            "target": target,
            "status": "failed",
            "detail": str(exc),
        }


def _evaluate_alert_rules(
    db: Session,
    crawler: Crawler,
    previous_status: str | None,
) -> None:
    rules = (
        db.query(CrawlerAlertRule)
        .filter(
            CrawlerAlertRule.user_id == crawler.user_id,
            CrawlerAlertRule.is_active == True,
        )
        .all()
    )
    if not rules:
        return
    payload = crawler.heartbeat_payload or {}
    for rule in rules:
        if not _match_alert_rule_target(rule, crawler):
            continue
        state = _get_or_create_alert_state(db, rule, crawler)
        triggered = False
        message = ""
        extra_payload: dict = {}
        if rule.trigger_type == "status_offline":
            triggered, message, extra_payload = _evaluate_status_rule(rule, state, previous_status, crawler.status)
        elif rule.trigger_type == "payload_threshold":
            triggered, message, extra_payload = _evaluate_payload_rule(rule, state, payload)
        if not triggered or _in_cooldown(rule, state):
            continue
        event = CrawlerAlertEvent(
            rule_id=rule.id,
            crawler_id=crawler.id,
            user_id=rule.user_id,
            triggered_at=now(),
            status="pending",
            message=message,
            payload=extra_payload or {},
        )
        db.add(event)
        db.flush()
        try:
            _dispatch_alert_event(rule, event, crawler, extra_payload or {})
        except Exception as exc:
            logging.exception("dispatch alert event failed", exc_info=exc)
            event.status = "failed"
            event.error = str(exc)
        state.last_triggered_at = event.triggered_at
        rule.last_triggered_at = event.triggered_at
        state.consecutive_hits = 0


def _normalize_config_format(value: str | None) -> str:
    lowered = (value or "json").lower()
    return "yaml" if lowered == "yaml" else "json"


def _resolve_assignment_target(
    current_user: User,
    target_type: str,
    target_id: int,
    db: Session,
) -> tuple[str, int]:
    normalized = (target_type or "").lower()
    if normalized not in {"crawler", "api_key", "group"}:
        raise HTTPException(status_code=400, detail="target_type 仅支持 crawler/api_key/group")
    if normalized == "crawler":
        crawler = (
            db.query(Crawler)
            .filter(
                Crawler.user_id == current_user.id,
                or_(Crawler.id == target_id, Crawler.local_id == target_id),
            )
            .first()
        )
        if not crawler:
            raise HTTPException(status_code=404, detail="爬虫不存在或无权访问")
        return normalized, crawler.id
    if normalized == "api_key":
        api_key = (
            db.query(APIKey)
            .filter(
                APIKey.user_id == current_user.id,
                or_(APIKey.id == target_id, APIKey.local_id == target_id),
            )
            .first()
        )
        if not api_key:
            raise HTTPException(status_code=404, detail="API Key 不存在或无权访问")
        return normalized, api_key.id
    group = (
        db.query(CrawlerGroup)
        .filter(CrawlerGroup.user_id == current_user.id, CrawlerGroup.id == target_id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在或无权访问")
    return normalized, group.id


def _get_template_for_user(
    db: Session,
    current_user: User,
    template_id: int | None,
) -> CrawlerConfigTemplate | None:
    if template_id is None:
        return None
    template = (
        db.query(CrawlerConfigTemplate)
        .filter(
            CrawlerConfigTemplate.id == template_id,
            CrawlerConfigTemplate.user_id == current_user.id,
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="配置模板不存在")
    return template


def _validate_alert_targets(
    db: Session,
    current_user: User,
    target_type: str,
    target_ids: list[int] | None,
) -> list[int]:
    normalized = (target_type or "all").lower()
    if normalized == "all" or not target_ids:
        return []
    unique_ids = {int(value) for value in target_ids if isinstance(value, int) or str(value).isdigit()}
    if not unique_ids:
        return []
    if normalized == "crawler":
        rows = (
            db.query(Crawler.id)
            .filter(Crawler.user_id == current_user.id, Crawler.id.in_(unique_ids))
            .all()
        )
        found = {row[0] for row in rows}
        if found != unique_ids:
            raise HTTPException(status_code=400, detail="存在无效的爬虫 ID")
        return list(found)
    if normalized == "api_key":
        rows = (
            db.query(APIKey.id)
            .filter(APIKey.user_id == current_user.id, APIKey.id.in_(unique_ids))
            .all()
        )
        found = {row[0] for row in rows}
        if found != unique_ids:
            raise HTTPException(status_code=400, detail="存在无效的 API Key ID")
        return list(found)
    if normalized == "group":
        rows = (
            db.query(CrawlerGroup.id)
            .filter(CrawlerGroup.user_id == current_user.id, CrawlerGroup.id.in_(unique_ids))
            .all()
        )
        found = {row[0] for row in rows}
        if found != unique_ids:
            raise HTTPException(status_code=400, detail="存在无效的分组 ID")
        return list(found)
    raise HTTPException(status_code=400, detail="target_type 仅支持 all/crawler/api_key/group")

def _require_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> APIKey:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 X-API-Key")
    key = (
        db.query(APIKey)
        .options(joinedload(APIKey.crawler).joinedload(Crawler.group))
        .filter(APIKey.key == x_api_key, APIKey.active == True)
        .first()
    )
    if not key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key 无效")
    client_ip = _get_client_ip(request)
    if key.allowed_ips:
        allowed = {ip.strip() for ip in key.allowed_ips.split(",") if ip.strip()}
        if allowed and client_ip not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="来源 IP 不在白名单内")
    key.last_used_at = now()
    key.last_used_ip = client_ip
    db.commit()
    db.refresh(key)
    return key


def _get_or_bind_crawler(db: Session, api_key: APIKey, default_name: str) -> Crawler:
    if api_key.crawler:
        return api_key.crawler
    max_local = (
        db.query(func.max(Crawler.local_id))
        .filter(Crawler.user_id == api_key.user_id)
        .scalar()
        or 0
    )
    crawler = Crawler(
        name=default_name,
        user_id=api_key.user_id,
        local_id=max_local + 1,
        api_key=api_key,
        group_id=api_key.group_id,
        status="offline",
        status_changed_at=now(),
    )
    db.add(crawler)
    db.commit()
    db.refresh(crawler)
    return crawler


def _update_crawler_status(
    crawler: Crawler,
    heartbeat_time: Optional[datetime],
    source_ip: Optional[str],
    payload_status: Optional[str],
) -> None:
    if heartbeat_time:
        crawler.last_heartbeat = heartbeat_time
    if source_ip:
        crawler.last_source_ip = source_ip
    status = payload_status or _compute_status(crawler.last_heartbeat)
    if status != crawler.status:
        crawler.status = status
        crawler.status_changed_at = now()
    elif crawler.status != status:
        crawler.status_changed_at = now()


def _record_heartbeat(
    db: Session,
    crawler: Crawler,
    api_key: APIKey,
    status_value: str,
    payload: Optional[dict],
    client_ip: Optional[str],
    device_name: Optional[str] = None,
) -> None:
    event = CrawlerHeartbeat(
        crawler_id=crawler.id,
        api_key_id=api_key.id,
        status=status_value,
        payload=payload or {},
        source_ip=client_ip,
        device_name=device_name,
        created_at=now(),
    )
    db.add(event)


def _serialize_crawlers(records: Sequence[Crawler]) -> List[Crawler]:
    result: List[Crawler] = []
    for crawler in records:
        crawler.status = _compute_status(crawler.last_heartbeat)
        result.append(crawler)
    return result


@api_router.post("/register")
def register_crawler(
    payload: CrawlerRegisterRequest,
    request: Request,
    api_key: APIKey = Depends(_require_api_key),
    db: Session = Depends(get_db),
):
    name = payload.name.strip() if payload.name else f"crawler-{api_key.local_id}"
    crawler = _get_or_bind_crawler(db, api_key, name)
    crawler.name = name
    crawler.group_id = api_key.group_id
    crawler.last_source_ip = _get_client_ip(request) or crawler.last_source_ip
    db.commit()
    db.refresh(crawler)
    return {
        "id": crawler.id,
        "local_id": crawler.local_id,
        "name": crawler.name,
        "status": crawler.status,
    }


@api_router.post("/{crawler_id}/heartbeat")
def heartbeat(
    crawler_id: int,
    payload: HeartbeatPayload | None,
    request: Request,
    api_key: APIKey = Depends(_require_api_key),
    db: Session = Depends(get_db),
):
    crawler = (
        db.query(Crawler)
        .filter(Crawler.id == crawler_id, Crawler.user_id == api_key.user_id)
        .first()
    )
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    current_time = now()
    client_ip = _get_client_ip(request)
    previous_status = crawler.status
    status_hint = payload.status if payload else None
    _update_crawler_status(crawler, current_time, client_ip, status_hint)
    crawler.heartbeat_payload = (payload.payload if payload else None) or {}
    # 更新设备名
    device_name = payload.device_name if payload else None
    if device_name:
        crawler.last_device_name = device_name
    _record_heartbeat(db, crawler, api_key, crawler.status, crawler.heartbeat_payload, client_ip, device_name)
    run = (
        db.query(CrawlerRun)
        .filter(CrawlerRun.crawler_id == crawler_id, CrawlerRun.status == "running")
        .order_by(CrawlerRun.started_at.desc())
        .first()
    )
    if run:
        run.last_heartbeat = current_time
        run.source_ip = client_ip or run.source_ip
    _evaluate_alert_rules(db, crawler, previous_status)
    db.commit()
    return {
        "ok": True,
        "ts": current_time.isoformat(),
        "status": crawler.status,
    }



@api_router.get("/{crawler_id}/config", response_model=CrawlerConfigFetchOut)
def fetch_crawler_config(
    crawler_id: int,
    api_key: APIKey = Depends(_require_api_key),
    db: Session = Depends(get_db),
):
    crawler = (
        db.query(Crawler)
        .filter(Crawler.id == crawler_id, Crawler.user_id == api_key.user_id)
        .first()
    )
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    assignment = _get_effective_assignment(db, api_key.user_id, crawler)
    if not assignment or not assignment.is_active:
        return {
            "has_config": False,
            "assignment_id": None,
            "name": None,
            "format": None,
            "version": None,
            "content": None,
            "updated_at": None,
        }
    return {
        "has_config": True,
        "assignment_id": assignment.id,
        "name": assignment.name,
        "format": assignment.format,
        "version": assignment.version,
        "content": assignment.content,
        "updated_at": assignment.updated_at,
    }


@api_router.post("/{crawler_id}/runs/start", response_model=RunStartResponse)
def start_run(
    crawler_id: int,
    request: Request,
    api_key: APIKey = Depends(_require_api_key),
    db: Session = Depends(get_db),
):
    crawler = (
        db.query(Crawler)
        .filter(Crawler.id == crawler_id, Crawler.user_id == api_key.user_id)
        .first()
    )
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    run = CrawlerRun(
        crawler_id=crawler_id,
        status="running",
        started_at=now(),
        source_ip=_get_client_ip(request),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return RunStartResponse(id=run.id, status=run.status, started_at=run.started_at)


@api_router.post("/{crawler_id}/runs/{run_id}/finish")
def finish_run(
    crawler_id: int,
    run_id: int,
    status_: str = "success",
    api_key: APIKey = Depends(_require_api_key),
    db: Session = Depends(get_db),
):
    run = (
        db.query(CrawlerRun)
        .filter(
            CrawlerRun.id == run_id,
            CrawlerRun.crawler_id == crawler_id,
            CrawlerRun.crawler.has(user_id=api_key.user_id),
        )
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    run.status = status_
    run.ended_at = now()
    db.commit()
    return {"ok": True}


@api_router.post("/{crawler_id}/logs", response_model=LogOut, status_code=201)
def create_log(
    crawler_id: int,
    payload: LogCreate,
    request: Request,
    api_key: APIKey = Depends(_require_api_key),
    db: Session = Depends(get_db),
):
    """爬虫端上报一条日志（SDK 使用 X-API-Key 调用）。

    - 路径：POST /pa/api/{crawler_id}/logs
    - 认证：请求头 X-API-Key
    - 请求体：LogCreate(level/level_code/message/run_id)
    - 返回：LogOut
    """
    crawler = (
        db.query(Crawler)
        .filter(Crawler.id == crawler_id, Crawler.user_id == api_key.user_id)
        .first()
    )
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")

    level_name, level_code = _resolve_log_level(payload)
    client_ip = _get_client_ip(request)

    log = LogEntry(
        crawler_id=crawler.id,
        api_key_id=api_key.id,
        run_id=payload.run_id,
        level=level_name,
        level_code=level_code,
        message=payload.message,
        ts=now(),
        source_ip=client_ip,
        device_name=payload.device_name,
    )
    # 更新爬虫最近设备名
    if payload.device_name:
        crawler.last_device_name = payload.device_name
    db.add(log)
    db.commit()
    db.refresh(log)
    # 强制执行项目级与用户级配额（滚动清理）
    try:
        _enforce_crawler_limits(db, crawler)
    except Exception:
        pass
    try:
        _enforce_user_quota(db, api_key.user)
    except Exception:
        pass
    return log


@api_router.post("/{crawler_id}/commands/next", response_model=list[CrawlerCommandOut])
def fetch_commands(
    crawler_id: int,
    api_key: APIKey = Depends(_require_api_key),
    db: Session = Depends(get_db),
):
    crawler = (
        db.query(Crawler)
        .filter(Crawler.id == crawler_id, Crawler.user_id == api_key.user_id)
        .first()
    )
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    commands = (
        db.query(CrawlerCommand)
        .filter(
            CrawlerCommand.crawler_id == crawler_id,
            CrawlerCommand.status == "pending",
            or_(CrawlerCommand.expires_at == None, CrawlerCommand.expires_at >= now()),
        )
        .order_by(CrawlerCommand.created_at.asc())
        .limit(COMMAND_FETCH_BATCH)
        .all()
    )
    return commands


@api_router.post("/{crawler_id}/commands/{command_id}/ack")
def acknowledge_command(
    crawler_id: int,
    command_id: int,
    payload: CrawlerCommandAck,
    api_key: APIKey = Depends(_require_api_key),
    db: Session = Depends(get_db),
):
    command = (
        db.query(CrawlerCommand)
        .filter(
            CrawlerCommand.id == command_id,
            CrawlerCommand.crawler_id == crawler_id,
            CrawlerCommand.crawler.has(user_id=api_key.user_id),
        )
        .first()
    )
    if not command:
        raise HTTPException(status_code=404, detail="指令不存在")
    command.status = payload.status or "done"
    command.result = payload.result or {}
    command.processed_at = now()
    db.commit()
    db.refresh(command)
    return command


# ------- 管理端查询与操作 -------


@api_router.get("/groups", response_model=list[CrawlerGroupOut])
def list_groups(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_crawler_feature(current_user)
    groups = (
        db.query(CrawlerGroup)
        .filter(CrawlerGroup.user_id == current_user.id)
        .order_by(CrawlerGroup.created_at.asc())
        .all()
    )
    for group in groups:
        group.crawler_count = len(group.crawlers)
    return groups


@api_router.post("/groups", response_model=CrawlerGroupOut, status_code=201)
def create_group(
    payload: CrawlerGroupCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    slug = payload.slug.strip() if payload.slug else payload.name.strip().lower().replace(" ", "-")
    exists = (
        db.query(CrawlerGroup)
        .filter(CrawlerGroup.user_id == current_user.id, CrawlerGroup.slug == slug)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="分组标识已存在")
    group = CrawlerGroup(
        name=payload.name.strip(),
        slug=slug,
        description=payload.description,
        color=payload.color,
        user_id=current_user.id,
    )
    db.add(group)
    # 审计：分组创建
    # 先 flush 以获得自增 id
    db.flush()
    record_operation(
        db,
        action="group.create",
        target_type="group",
        target_id=group.id,
        target_name=group.name,
        before=None,
        after=summarize_group(group),
        actor=current_user,
        actor_ip=request.headers.get("X-Real-IP") if request.client else None,
    )
    db.commit()
    db.refresh(group)
    group.crawler_count = 0
    return group


@api_router.patch("/groups/{group_id}", response_model=CrawlerGroupOut)
def update_group(
    group_id: int,
    payload: CrawlerGroupUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    group = (
        db.query(CrawlerGroup)
        .filter(CrawlerGroup.id == group_id, CrawlerGroup.user_id == current_user.id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    before = summarize_group(group)
    if payload.name is not None:
        group.name = payload.name.strip()
    if payload.slug is not None:
        slug = payload.slug.strip()
        exists = (
            db.query(CrawlerGroup)
            .filter(
                CrawlerGroup.user_id == current_user.id,
                CrawlerGroup.slug == slug,
                CrawlerGroup.id != group.id,
            )
            .first()
        )
        if exists:
            raise HTTPException(status_code=400, detail="分组标识重复")
        group.slug = slug
    if payload.description is not None:
        group.description = payload.description
    if payload.color is not None:
        group.color = payload.color
    # 审计：分组更新
    record_operation(
        db,
        action="group.update",
        target_type="group",
        target_id=group.id,
        target_name=group.name,
        before=before,
        after=summarize_group(group),
        actor=current_user,
        actor_ip=request.headers.get("X-Real-IP") if request.client else None,
    )
    db.commit()
    db.refresh(group)
    group.crawler_count = len(group.crawlers)
    return group


@api_router.delete("/groups/{group_id}")
def delete_group(
    group_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    group = (
        db.query(CrawlerGroup)
        .filter(CrawlerGroup.id == group_id, CrawlerGroup.user_id == current_user.id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    before = summarize_group(group)
    for crawler in group.crawlers:
        crawler.group = None
    for api_key in group.api_keys:
        api_key.group = None
    db.delete(group)
    # 审计：分组删除
    record_operation(
        db,
        action="group.delete",
        target_type="group",
        target_id=group.id,
        target_name=group.name,
        before=before,
        after=None,
        actor=current_user,
        actor_ip=request.headers.get("X-Real-IP") if request.client else None,
    )
    db.commit()
    return {"ok": True}


@api_router.get("/me", response_model=list[CrawlerOut])
def my_crawlers(
    status_filter: Optional[str] = Query(None, description="online/warning/offline，可逗号分隔"),
    group_id: Optional[int] = Query(None),
    group_ids: Optional[str] = Query(None, description="逗号分隔的分组ID，支持 none 表示未分组"),
    api_key_id: Optional[int] = Query(None, description="API Key ID 或本地编号"),
    api_key_ids: Optional[str] = Query(None, description="逗号分隔的 API Key ID 或本地编号"),
    keyword: Optional[str] = Query(None, description="名称或本地编号模糊搜索"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    query = (
        db.query(Crawler)
        .options(joinedload(Crawler.api_key), joinedload(Crawler.group))
        .filter(Crawler.user_id == current_user.id)
        # 仅返回绑定了 API Key 的爬虫，清理掉历史脏数据的影响
        .filter(Crawler.api_key_id != None)
    )

    status_whitelist: set[str] = set()
    if status_filter:
        status_whitelist = {
            item.strip().lower()
            for item in status_filter.split(',')
            if item.strip()
        }
        status_whitelist = {
            item
            for item in status_whitelist
            if item in {"online", "warning", "offline"}
        }

    group_ids_values: list[int] = []
    include_none_group = False
    if group_ids:
        group_ids_values, include_none_group = _parse_group_filters(group_ids)

    if group_ids_values or include_none_group:
        conditions = []
        if group_ids_values:
            conditions.append(Crawler.group_id.in_(group_ids_values))
        if include_none_group:
            conditions.append(Crawler.group_id == None)
        if conditions:
            query = query.filter(or_(*conditions))
    elif group_id is not None:
        if group_id == 0:
            query = query.filter(Crawler.group_id == None)
        else:
            query = query.filter(Crawler.group_id == group_id)

    api_key_ids_values: list[int] = []
    if api_key_ids:
        api_key_ids_values = _parse_id_list(api_key_ids)

    if api_key_ids_values:
        query = query.filter(
            or_(
                Crawler.api_key_id.in_(api_key_ids_values),
                Crawler.api_key.has(APIKey.local_id.in_(api_key_ids_values)),
            )
        )
    elif api_key_id is not None:
        query = query.filter(
            or_(
                Crawler.api_key_id == api_key_id,
                Crawler.api_key.has(APIKey.local_id == api_key_id),
            )
        )

    if keyword:
        cleaned = keyword.strip()
        like = f"%{cleaned}%"
        conds = [
            Crawler.name.ilike(like),
            Crawler.last_source_ip.ilike(like),
            # 通过关联的 API Key 名称或 Key 明文模糊搜索（仅限本人资源）
            Crawler.api_key.has(APIKey.name.ilike(like)),
            Crawler.api_key.has(APIKey.key.ilike(like)),
        ]
        if cleaned.isdigit():
            # 支持按本地编号精确匹配（爬虫/Key）
            conds.append(Crawler.local_id == int(cleaned))
            conds.append(Crawler.api_key.has(APIKey.local_id == int(cleaned)))
        query = query.filter(or_(*conds))

    crawlers = query.order_by(Crawler.local_id.asc()).all()
    assignment_map = _build_assignment_map(
        db,
        current_user.id,
        [crawler.id for crawler in crawlers],
        [crawler.api_key_id for crawler in crawlers if crawler.api_key_id],
        [crawler.group_id for crawler in crawlers if crawler.group_id],
    )
    result = []
    for crawler in crawlers:
        raw_status = _compute_status(crawler.last_heartbeat)
        status_value = (raw_status or "offline").lower()
        if status_whitelist and status_value not in status_whitelist:
            continue
        crawler.status = status_value
        # 计算置顶布尔值，供前端展示
        crawler.pinned = bool(crawler.pinned_at)
        if crawler.api_key:
            crawler.api_key_name = crawler.api_key.name or crawler.api_key.key
            crawler.api_key_local_id = crawler.api_key.local_id
            crawler.api_key_active = crawler.api_key.active
        else:
            crawler.api_key_name = None
            crawler.api_key_local_id = None
            crawler.api_key_active = None
        if crawler.group:
            crawler.group.crawler_count = len(crawler.group.crawlers)
        assignment = _resolve_assignment_from_map(assignment_map, crawler)
        _apply_assignment_metadata(crawler, assignment)
        result.append(crawler)
    # 排序规则：置顶优先（按置顶时间降序），其次按最后心跳降序（空值最后），最后按本地编号
    def _sort_key(c: Crawler):
        pinned_rank = 0 if c.pinned_at else 1
        pinned_ts = -(c.pinned_at.timestamp()) if c.pinned_at else 0
        hb_rank = 0 if c.last_heartbeat else 1
        hb_ts = -(c.last_heartbeat.timestamp()) if c.last_heartbeat else 0
        local_id = c.local_id or 0
        return (pinned_rank, pinned_ts, hb_rank, hb_ts, local_id)

    result.sort(key=_sort_key)
    return result

@api_router.get("/me/{crawler_id}", response_model=CrawlerOut)
def my_crawler_detail(
    crawler_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    crawler = (
        db.query(Crawler)
        .options(joinedload(Crawler.api_key), joinedload(Crawler.group))
        .filter(Crawler.id == crawler_id, Crawler.user_id == current_user.id)
        .first()
    )
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    crawler.status = _compute_status(crawler.last_heartbeat)
    if crawler.api_key:
        crawler.api_key_name = crawler.api_key.name or crawler.api_key.key
        crawler.api_key_local_id = crawler.api_key.local_id
        crawler.api_key_active = crawler.api_key.active
    else:
        crawler.api_key_name = None
        crawler.api_key_local_id = None
        crawler.api_key_active = None
    if crawler.group:
        crawler.group.crawler_count = len(crawler.group.crawlers)
    assignment = _get_effective_assignment(db, current_user.id, crawler)
    _apply_assignment_metadata(crawler, assignment)
    return crawler




@api_router.patch("/me/{crawler_id}", response_model=CrawlerOut)
def update_my_crawler(
    crawler_id: int,
    payload: CrawlerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    crawler = (
        db.query(Crawler)
        .options(joinedload(Crawler.api_key), joinedload(Crawler.group))
        .filter(Crawler.id == crawler_id, Crawler.user_id == current_user.id)
        .first()
    )
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    if payload.name and payload.name.strip():
        crawler.name = payload.name.strip()
    if payload.is_public is not None:
        # 同步公开状态与快捷链接：开启公开时自动生成/启用快捷链接；关闭时停用对应链接
        crawler.is_public = payload.is_public
        if payload.is_public:
            # 若未设置 public_slug，则自动生成唯一 slug
            if not crawler.public_slug:
                crawler.public_slug = _ensure_quick_slug(db)
            # 确保存在以 public_slug 为路径、指向该爬虫的快捷链接
            link = (
                db.query(CrawlerAccessLink)
                .filter(
                    CrawlerAccessLink.slug == crawler.public_slug,
                    CrawlerAccessLink.target_type == "crawler",
                )
                .first()
            )
            if not link:
                link = CrawlerAccessLink(
                    slug=crawler.public_slug,
                    target_type="crawler",
                    description="自动创建：公开爬虫访问链接",
                    allow_logs=True,
                    crawler=crawler,
                    created_by=current_user,
                    is_active=True,
                )
                db.add(link)
            else:
                # 已存在同名链接时，指向当前爬虫并启用
                link.crawler = crawler
                link.api_key = None
                link.group = None
                link.is_active = True
        else:
            # 关闭公开：停用与 public_slug 匹配的链接（若存在），并清除 public_slug
            if crawler.public_slug:
                link = (
                    db.query(CrawlerAccessLink)
                    .filter(
                        CrawlerAccessLink.slug == crawler.public_slug,
                        CrawlerAccessLink.target_type == "crawler",
                    )
                    .first()
                )
                if link:
                    link.is_active = False
            crawler.public_slug = None
    # 置顶/取消置顶
    if payload.pinned is not None:
        crawler.pinned_at = now() if payload.pinned else None
    # 更新日志上限设置
    if payload.log_max_lines is not None:
        crawler.log_max_lines = int(payload.log_max_lines)
    if payload.log_max_bytes is not None:
        crawler.log_max_bytes = int(payload.log_max_bytes)
    db.commit()
    db.refresh(crawler)
    crawler.status = _compute_status(crawler.last_heartbeat)
    crawler.pinned = bool(crawler.pinned_at)
    assignment = _get_effective_assignment(db, current_user.id, crawler)
    _apply_assignment_metadata(crawler, assignment)
    return crawler


@api_router.get("/me/{crawler_id}/runs", response_model=list[RunOut])
def my_crawler_runs(
    crawler_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    c = (
        db.query(Crawler)
        .filter(Crawler.id == crawler_id, Crawler.user_id == current_user.id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    runs = (
        db.query(CrawlerRun)
        .filter(CrawlerRun.crawler_id == crawler_id)
        .order_by(CrawlerRun.started_at.desc())
        .all()
    )
    return runs


@api_router.get("/me/{crawler_id}/heartbeats", response_model=list[CrawlerHeartbeatOut])
def my_crawler_heartbeats(
    crawler_id: int,
    limit: int = Query(
        500,
        ge=1,
        le=5000,
        description="最大返回数量（未指定时间区间时生效）",
    ),
    start: Optional[datetime] = Query(
        None,
        description="起始时间（ISO8601），默认返回最近记录",
    ),
    end: Optional[datetime] = Query(
        None,
        description="结束时间（ISO8601）",
    ),
    max_points: int = Query(
        600,
        ge=50,
        le=6000,
        description="在返回前进行等距采样保留的最大点数",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    crawler = (
        db.query(Crawler)
        .filter(Crawler.id == crawler_id, Crawler.user_id == current_user.id)
        .first()
    )
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")

    start_dt = start
    end_dt = end
    if start_dt and end_dt and start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    query = db.query(CrawlerHeartbeat).filter(CrawlerHeartbeat.crawler_id == crawler_id)
    if start_dt:
        query = query.filter(CrawlerHeartbeat.created_at >= start_dt)
    if end_dt:
        query = query.filter(CrawlerHeartbeat.created_at <= end_dt)

    query = query.order_by(CrawlerHeartbeat.created_at.desc())

    if not start_dt and not end_dt and limit:
        query = query.limit(limit)
    elif limit:
        query = query.limit(limit)

    records = list(reversed(query.all()))
    total = len(records)
    if total > max_points:
        step = max(1, math.ceil(total / max_points))
        sampled = [records[i] for i in range(0, total, step)]
        if sampled[-1].id != records[-1].id:
            sampled.append(records[-1])
        records = sampled

    return records


@api_router.get("/me/{crawler_id}/commands", response_model=list[CrawlerCommandOut])
def my_crawler_commands(
    crawler_id: int,
    include_finished: bool = False,
    limit: int = Query(200, ge=1, le=500),
    order: str = Query("asc", description="返回顺序 asc/desc"),
    before_id: Optional[int] = Query(None, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    crawler = (
        db.query(Crawler)
        .filter(Crawler.id == crawler_id, Crawler.user_id == current_user.id)
        .first()
    )
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    normalized_order = (order or "asc").lower()
    if normalized_order not in {"asc", "desc"}:
        normalized_order = "asc"
    descending = normalized_order == "desc"
    query = db.query(CrawlerCommand).filter(CrawlerCommand.crawler_id == crawler_id)
    if not include_finished:
        query = query.filter(CrawlerCommand.status == "pending")
    if before_id:
        query = query.filter(CrawlerCommand.id < before_id)
    records = (
        query
        .order_by(CrawlerCommand.created_at.desc(), CrawlerCommand.id.desc())
        .limit(limit)
        .all()
    )
    if not descending:
        records = list(reversed(records))
    return records


@api_router.post("/me/{crawler_id}/commands", response_model=CrawlerCommandOut, status_code=201)
def create_crawler_command(
    crawler_id: int,
    payload: CrawlerCommandCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    crawler = (
        db.query(Crawler)
        .filter(Crawler.id == crawler_id, Crawler.user_id == current_user.id)
        .first()
    )
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    expires_at = None
    if payload.expires_in_seconds:
        expires_at = now() + timedelta(seconds=payload.expires_in_seconds)
    command = CrawlerCommand(
        crawler_id=crawler_id,
        command=payload.command,
        payload=payload.payload or {},
        status="pending",
        expires_at=expires_at,
        issued_by=current_user,
    )
    db.add(command)
    db.commit()
    db.refresh(command)
    return command


@api_router.get("/me/logs", response_model=list[LogOut])
def my_logs(
    crawler_ids: Optional[str] = Query(None, description="逗号分隔的爬虫ID列表"),
    start: Optional[date] = None,
    end: Optional[date] = None,
    min_level: int = Query(0, ge=0, le=50),
    max_level: int = Query(50, ge=0, le=50),
    limit: int = Query(200, ge=1, le=1000),
    q: Optional[str] = Query(None, description="消息关键字或正则"),
    regex: bool = Query(False, description="将 q 作为正则表达式进行匹配"),
    device: Optional[str] = Query(None, description="按设备名包含筛选"),
    ip: Optional[str] = Query(None, description="按来源 IP 包含筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    _enforce_log_rate_limit(current_user.id)
    ids = _parse_id_list(crawler_ids)
    min_level = _normalize_level_code(min_level)
    max_level = _normalize_level_code(max_level)
    if min_level > max_level:
        min_level, max_level = max_level, min_level
    query = (
        db.query(LogEntry)
        .join(Crawler)
        .filter(Crawler.user_id == current_user.id)
        .options(joinedload(LogEntry.crawler), joinedload(LogEntry.api_key))
    )
    if ids:
        query = query.filter(LogEntry.crawler_id.in_(ids))
    query = _apply_log_filters(query, start, end, min_level, max_level)
    if device and device.strip():
        query = query.filter(LogEntry.device_name.ilike(f"%{device.strip()}%"))
    if ip and ip.strip():
        query = query.filter(LogEntry.source_ip.ilike(f"%{ip.strip()}%"))
    query, pattern = _maybe_apply_message_search(query, q, regex)
    query = query.order_by(LogEntry.ts.desc())
    if pattern is not None:
        # 为保证结果质量，正则在 Python 端过滤；先放宽扫描范围再截断
        scan_limit = min(max(limit * 10, limit), MAX_REGEX_SCAN)
        records = query.limit(scan_limit).all()
        asc_records = list(reversed(records))
        filtered = [item for item in asc_records if pattern.search(item.message or "")]
        result = filtered[-limit:] if limit else filtered
        return _serialise_logs(result)
    else:
        if limit:
            query = query.limit(limit)
        logs = list(reversed(query.all()))
        return _serialise_logs(logs)


@api_router.get("/me/{crawler_id}/logs", response_model=list[LogOut])
def my_crawler_logs(
    crawler_id: int,
    limit: int = Query(100, ge=1, le=500),
    order: str = Query("asc", description="返回顺序 asc/desc"),
    before_id: Optional[int] = Query(None, ge=1),
    q: Optional[str] = Query(None, description="消息关键字或正则"),
    regex: bool = Query(False, description="将 q 作为正则表达式进行匹配"),
    device: Optional[str] = Query(None, description="按设备名包含筛选"),
    ip: Optional[str] = Query(None, description="按来源 IP 包含筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    _enforce_log_rate_limit(current_user.id)
    c = (
        db.query(Crawler)
        .filter(Crawler.id == crawler_id, Crawler.user_id == current_user.id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    normalized_order = (order or "asc").lower()
    if normalized_order not in {"asc", "desc"}:
        normalized_order = "asc"
    descending = normalized_order == "desc"
    query = (
        db.query(LogEntry)
        .filter(LogEntry.crawler_id == crawler_id)
        .order_by(LogEntry.ts.desc(), LogEntry.id.desc())
        .options(joinedload(LogEntry.crawler), joinedload(LogEntry.api_key))
    )
    if before_id:
        query = query.filter(LogEntry.id < before_id)
    if device and device.strip():
        query = query.filter(LogEntry.device_name.ilike(f"%{device.strip()}%"))
    if ip and ip.strip():
        query = query.filter(LogEntry.source_ip.ilike(f"%{ip.strip()}%"))
    query, pattern = _maybe_apply_message_search(query, q, regex)
    if pattern is not None:
        scan_limit = min(max(limit * 10, limit), MAX_REGEX_SCAN)
        records = query.limit(scan_limit).all()
        asc = list(reversed(records))
        filtered = [item for item in asc if pattern.search(item.message or "")]
        sliced = filtered[-limit:] if limit else filtered
        if descending:
            sliced = list(reversed(sliced))
        return _serialise_logs(sliced)
    else:
        records = query.limit(limit).all()
        if not descending:
            records = list(reversed(records))
        return _serialise_logs(records)


@api_router.get("/me/{crawler_id}/logs/stats")
def my_crawler_logs_stats(
    crawler_id: int,
    hours: int = Query(24, ge=1, le=168, description="统计窗口（小时）"),
    buckets: int = Query(24, ge=2, le=240, description="分桶数量"),
    min_level: int = Query(0, ge=0, le=50),
    max_level: int = Query(50, ge=0, le=50),
    q: Optional[str] = Query(None, description="消息关键字或正则"),
    regex: bool = Query(False, description="q 是否为正则"),
    granularity: Optional[str] = Query(None, description="聚合粒度：auto/day/week"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    c = (
        db.query(Crawler)
        .filter(Crawler.id == crawler_id, Crawler.user_id == current_user.id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    from_dt = now() - timedelta(hours=int(hours or 24))
    min_level = _normalize_level_code(min_level)
    max_level = _normalize_level_code(max_level)
    base = (
        db.query(LogEntry.id, LogEntry.ts, LogEntry.message)
        .filter(LogEntry.crawler_id == crawler_id)
        .filter(LogEntry.ts >= from_dt)
        .filter(LogEntry.level_code >= min_level)
        .filter(LogEntry.level_code <= max_level)
        .order_by(LogEntry.ts.asc())
    )
    text = (q or "").strip()
    use_regex = bool(regex)
    if text and not use_regex:
        base = base.filter(LogEntry.message.ilike(f"%{text}%"))
    rows = base.limit(20000).all()
    if text and use_regex:
        try:
            pattern = re.compile(text)
            rows = [r for r in rows if pattern.search(r[2] or "")]
        except re.error:
            pass
    scanned = len(rows)
    if not rows:
        end_dt = now()
        return {"start": from_dt.isoformat(), "end": end_dt.isoformat(), "buckets": [], "total": 0, "scanned": 0}
    start_dt = rows[0][1]
    end_dt = rows[-1][1]
    b = max(2, int(buckets or 24))
    edges = _make_edges(start_dt, end_dt, b, granularity)
    counts = [0] * (len(edges) - 1)
    j = 0
    for _id, ts, _msg in rows:
        while j < len(edges) - 2 and ts >= edges[j + 1]:
            j += 1
        counts[j] += 1
    bucket_list = [{"t": edges[i].isoformat(), "count": counts[i]} for i in range(len(edges) - 1)]
    result = {"start": start_dt.isoformat(), "end": end_dt.isoformat(), "buckets": bucket_list, "total": sum(counts), "scanned": scanned}
    key = (current_user.id, crawler_id, hours, b, min_level, max_level, text, bool(regex), (granularity or "auto").lower())
    cached = _stats_cache_get(_PRIVATE_STATS_CACHE, key)
    if cached is not None:
        return cached
    _stats_cache_set(_PRIVATE_STATS_CACHE, key, result)
    return result


@api_router.get("/me/{crawler_id}/logs/usage", response_model=LogUsageOut)
def my_crawler_logs_usage(
    crawler_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    crawler = (
        db.query(Crawler)
        .filter(Crawler.id == crawler_id, Crawler.user_id == current_user.id)
        .first()
    )
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    lines, bytes_ = _measure_crawler_usage(db, crawler.id)
    max_lines, max_bytes = _effective_crawler_limits(crawler)
    return {
        "lines": lines,
        "bytes": bytes_,
        "max_lines": max_lines,
        "max_bytes": max_bytes,
    }


@api_router.delete("/me/{crawler_id}/logs")
def clear_my_crawler_logs(
    crawler_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    crawler = (
        db.query(Crawler)
        .filter(Crawler.id == crawler_id, Crawler.user_id == current_user.id)
        .first()
    )
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    # 统计现有
    before_lines, before_bytes = _measure_crawler_usage(db, crawler.id)
    # 全量删除该爬虫日志
    deleted = (
        db.query(LogEntry)
        .filter(LogEntry.crawler_id == crawler.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {
        "ok": True,
        "deleted": int(deleted or 0),
        "before": {"lines": before_lines, "bytes": before_bytes},
        "after": {"lines": 0, "bytes": 0},
    }


@api_router.get("/me/logs/usage", response_model=UserLogUsageOut)
def my_logs_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    lines, bytes_ = _measure_user_usage(db, current_user.id)
    quota = _effective_user_quota(current_user)
    return {
        "total_lines": lines,
        "total_bytes": bytes_,
        "quota_bytes": quota,
    }


# ------- 快捷链接管理 -------


@api_router.get("/links", response_model=list[QuickLinkOut])
def list_quick_links(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    links = (
        db.query(CrawlerAccessLink)
        .options(joinedload(CrawlerAccessLink.crawler).joinedload(Crawler.group))
        .options(joinedload(CrawlerAccessLink.api_key).joinedload(APIKey.group))
        .options(joinedload(CrawlerAccessLink.group).joinedload(CrawlerGroup.crawlers))
        .filter(
            or_(
                CrawlerAccessLink.created_by_id == current_user.id,
                CrawlerAccessLink.crawler.has(Crawler.user_id == current_user.id),
                CrawlerAccessLink.api_key.has(APIKey.user_id == current_user.id),
                CrawlerAccessLink.group.has(CrawlerGroup.user_id == current_user.id),
            )
        )
        .order_by(CrawlerAccessLink.created_at.desc())
        .all()
    )
    return links


@api_router.post("/links", response_model=QuickLinkOut)
def create_quick_link(
    payload: QuickLinkCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    slug = _ensure_quick_slug(db, payload.slug or "")
    normalized_type = (payload.target_type or "").lower()
    if normalized_type not in {"crawler", "api_key", "group"}:
        raise HTTPException(status_code=400, detail="target_type 仅支持 crawler/api_key/group")

    crawler: Optional[Crawler] = None
    api_key: Optional[APIKey] = None
    group: Optional[CrawlerGroup] = None

    if normalized_type == "crawler":
        crawler = (
            db.query(Crawler)
            .filter(
                Crawler.user_id == current_user.id,
                or_(Crawler.local_id == payload.target_id, Crawler.id == payload.target_id),
            )
            .first()
        )
        if not crawler:
            raise HTTPException(status_code=404, detail="爬虫不存在或无权访问")
    elif normalized_type == "api_key":
        api_key = (
            db.query(APIKey)
            .filter(
                APIKey.user_id == current_user.id,
                or_(APIKey.local_id == payload.target_id, APIKey.id == payload.target_id),
            )
            .first()
        )
        if not api_key:
            raise HTTPException(status_code=404, detail="API Key 不存在或无权访问")
    else:
        group = (
            db.query(CrawlerGroup)
            .filter(CrawlerGroup.id == payload.target_id, CrawlerGroup.user_id == current_user.id)
            .first()
        )
        if not group:
            raise HTTPException(status_code=404, detail="分组不存在或无权访问")

    link = CrawlerAccessLink(
        slug=slug,
        target_type=normalized_type,
        description=payload.description,
        allow_logs=payload.allow_logs,
        crawler=crawler,
        api_key=api_key,
        group=group,
        created_by=current_user,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@api_router.patch("/links/{link_id}", response_model=QuickLinkOut)
def update_quick_link(
    link_id: int,
    payload: QuickLinkUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    link = (
        db.query(CrawlerAccessLink)
        .options(joinedload(CrawlerAccessLink.crawler), joinedload(CrawlerAccessLink.api_key), joinedload(CrawlerAccessLink.group))
        .filter(CrawlerAccessLink.id == link_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="快捷链接不存在")
    owner_ids = set()
    if link.crawler:
        owner_ids.add(link.crawler.user_id)
    if link.api_key:
        owner_ids.add(link.api_key.user_id)
    if link.group:
        owner_ids.add(link.group.user_id)
    if current_user.id not in owner_ids and current_user.role not in {ROLE_ADMIN, ROLE_SUPERADMIN}:
        raise HTTPException(status_code=403, detail="无权修改该链接")
    if payload.slug is not None:
        link.slug = _ensure_quick_slug(db, payload.slug or "")
    if payload.description is not None:
        link.description = payload.description
    if payload.allow_logs is not None:
        link.allow_logs = payload.allow_logs
    if payload.is_active is not None:
        link.is_active = payload.is_active
    db.commit()
    db.refresh(link)
    return link


@api_router.delete("/links/{link_id}")
def delete_quick_link(
    link_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    link = db.query(CrawlerAccessLink).filter(CrawlerAccessLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="快捷链接不存在")
    owner_ids = set()
    if link.crawler:
        owner_ids.add(link.crawler.user_id)
    if link.api_key:
        owner_ids.add(link.api_key.user_id)
    if link.group:
        owner_ids.add(link.group.user_id)
    if current_user.id not in owner_ids and current_user.role not in {ROLE_ADMIN, ROLE_SUPERADMIN}:
        raise HTTPException(status_code=403, detail="无权删除该链接")
    db.delete(link)
    db.commit()
    return {"ok": True}


# ------- 配置模板管理 -------


@api_router.get("/config/templates", response_model=list[CrawlerConfigTemplateOut])
def list_config_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    templates = (
        db.query(CrawlerConfigTemplate)
        .filter(CrawlerConfigTemplate.user_id == current_user.id)
        .order_by(CrawlerConfigTemplate.updated_at.desc())
        .all()
    )
    return templates


@api_router.post("/config/templates", response_model=CrawlerConfigTemplateOut)
def create_config_template(
    payload: CrawlerConfigTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="模板名称不能为空")
    exists = (
        db.query(CrawlerConfigTemplate)
        .filter(
            CrawlerConfigTemplate.user_id == current_user.id,
            CrawlerConfigTemplate.name == name,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="模板名称已存在")
    fmt = _normalize_config_format(payload.format)
    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="配置内容不能为空")
    template = CrawlerConfigTemplate(
        name=name,
        description=payload.description,
        format=fmt,
        content=content,
        is_active=payload.is_active,
        user=current_user,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@api_router.patch("/config/templates/{template_id}", response_model=CrawlerConfigTemplateOut)
def update_config_template(
    template_id: int,
    payload: CrawlerConfigTemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    template = (
        db.query(CrawlerConfigTemplate)
        .filter(
            CrawlerConfigTemplate.id == template_id,
            CrawlerConfigTemplate.user_id == current_user.id,
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="模板名称不能为空")
        if new_name != template.name:
            exists = (
                db.query(CrawlerConfigTemplate)
                .filter(
                    CrawlerConfigTemplate.user_id == current_user.id,
                    CrawlerConfigTemplate.name == new_name,
                    CrawlerConfigTemplate.id != template.id,
                )
                .first()
            )
            if exists:
                raise HTTPException(status_code=400, detail="模板名称已存在")
            template.name = new_name
    if payload.description is not None:
        template.description = payload.description
    if payload.format is not None:
        template.format = _normalize_config_format(payload.format)
    if payload.content is not None:
        cleaned = payload.content.strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="配置内容不能为空")
        template.content = cleaned
    if payload.is_active is not None:
        template.is_active = payload.is_active
    db.commit()
    db.refresh(template)
    return template


@api_router.delete("/config/templates/{template_id}")
def delete_config_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    template = (
        db.query(CrawlerConfigTemplate)
        .filter(
            CrawlerConfigTemplate.id == template_id,
            CrawlerConfigTemplate.user_id == current_user.id,
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    in_use = (
        db.query(CrawlerConfigAssignment)
        .filter(CrawlerConfigAssignment.template_id == template.id)
        .first()
    )
    if in_use:
        raise HTTPException(status_code=400, detail="仍有配置指派引用该模板")
    db.delete(template)
    db.commit()
    return {"ok": True}


# ------- 配置指派管理 -------


@api_router.get("/config/assignments", response_model=list[CrawlerConfigAssignmentOut])
def list_config_assignments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    assignments = (
        db.query(CrawlerConfigAssignment)
        .options(joinedload(CrawlerConfigAssignment.template))
        .filter(CrawlerConfigAssignment.user_id == current_user.id)
        .order_by(CrawlerConfigAssignment.updated_at.desc())
        .all()
    )
    for assignment in assignments:
        assignment.template_name = assignment.template.name if assignment.template else None
    return assignments


@api_router.post("/config/assignments", response_model=CrawlerConfigAssignmentOut)
def create_config_assignment(
    payload: CrawlerConfigAssignmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="指派名称不能为空")
    normalized_type, resolved_id = _resolve_assignment_target(current_user, payload.target_type, payload.target_id, db)
    existing = (
        db.query(CrawlerConfigAssignment)
        .filter(
            CrawlerConfigAssignment.user_id == current_user.id,
            CrawlerConfigAssignment.target_type == normalized_type,
            CrawlerConfigAssignment.target_id == resolved_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="该目标已存在配置指派")
    template = _get_template_for_user(db, current_user, payload.template_id)
    fmt = _normalize_config_format(payload.format or (template.format if template else "json"))
    content_source = payload.content if payload.content is not None else (template.content if template else "")
    content = (content_source or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="配置内容不能为空")
    assignment = CrawlerConfigAssignment(
        name=name,
        description=payload.description,
        target_type=normalized_type,
        target_id=resolved_id,
        format=fmt,
        content=content,
        version=1,
        is_active=payload.is_active,
        template=template,
        user=current_user,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    assignment.template_name = template.name if template else None
    return assignment


@api_router.patch("/config/assignments/{assignment_id}", response_model=CrawlerConfigAssignmentOut)
def update_config_assignment(
    assignment_id: int,
    payload: CrawlerConfigAssignmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    assignment = (
        db.query(CrawlerConfigAssignment)
        .options(joinedload(CrawlerConfigAssignment.template))
        .filter(
            CrawlerConfigAssignment.id == assignment_id,
            CrawlerConfigAssignment.user_id == current_user.id,
        )
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="配置指派不存在")
    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="指派名称不能为空")
        assignment.name = new_name
    if payload.description is not None:
        assignment.description = payload.description
    if payload.format is not None:
        assignment.format = _normalize_config_format(payload.format)
    if payload.content is not None:
        cleaned = payload.content.strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="配置内容不能为空")
        if cleaned != assignment.content:
            assignment.content = cleaned
            assignment.version += 1
    if payload.template_id is not None:
        if payload.template_id:
            template = _get_template_for_user(db, current_user, payload.template_id)
            assignment.template = template
        else:
            assignment.template = None
    if payload.is_active is not None:
        assignment.is_active = payload.is_active
    db.commit()
    db.refresh(assignment)
    assignment.template_name = assignment.template.name if assignment.template else None
    return assignment


@api_router.delete("/config/assignments/{assignment_id}")
def delete_config_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    assignment = (
        db.query(CrawlerConfigAssignment)
        .filter(
            CrawlerConfigAssignment.id == assignment_id,
            CrawlerConfigAssignment.user_id == current_user.id,
        )
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="配置指派不存在")
    db.delete(assignment)
    db.commit()
    return {"ok": True}


# ------- 告警规则与事件 -------


@api_router.get("/alerts/rules", response_model=list[CrawlerAlertRuleOut])
def list_alert_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    rules = (
        db.query(CrawlerAlertRule)
        .filter(CrawlerAlertRule.user_id == current_user.id)
        .order_by(CrawlerAlertRule.updated_at.desc())
        .all()
    )
    return rules


@api_router.post("/alerts/rules", response_model=CrawlerAlertRuleOut)
def create_alert_rule(
    payload: CrawlerAlertRuleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="规则名称不能为空")
    exists = (
        db.query(CrawlerAlertRule)
        .filter(
            CrawlerAlertRule.user_id == current_user.id,
            CrawlerAlertRule.name == name,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="规则名称已存在")
    normalized_trigger = payload.trigger_type
    target_ids = _validate_alert_targets(db, current_user, payload.target_type, payload.target_ids)
    channels_data = jsonable_encoder(payload.channels)
    comparator = payload.comparator if normalized_trigger == "payload_threshold" else None
    threshold = payload.threshold if normalized_trigger == "payload_threshold" else None
    field = payload.payload_field if normalized_trigger == "payload_threshold" else None
    rule = CrawlerAlertRule(
        name=name,
        description=payload.description,
        trigger_type=normalized_trigger,
        target_type=payload.target_type or "all",
        target_ids=target_ids,
        status_from=payload.status_from,
        status_to=payload.status_to,
        payload_field=field,
        comparator=comparator,
        threshold=threshold,
        consecutive_failures=payload.consecutive_failures,
        cooldown_minutes=payload.cooldown_minutes,
        channels=channels_data,
        is_active=payload.is_active,
        user=current_user,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@api_router.patch("/alerts/rules/{rule_id}", response_model=CrawlerAlertRuleOut)
def update_alert_rule(
    rule_id: int,
    payload: CrawlerAlertRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    rule = (
        db.query(CrawlerAlertRule)
        .filter(
            CrawlerAlertRule.id == rule_id,
            CrawlerAlertRule.user_id == current_user.id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="规则名称不能为空")
        if new_name != rule.name:
            exists = (
                db.query(CrawlerAlertRule)
                .filter(
                    CrawlerAlertRule.user_id == current_user.id,
                    CrawlerAlertRule.name == new_name,
                    CrawlerAlertRule.id != rule.id,
                )
                .first()
            )
            if exists:
                raise HTTPException(status_code=400, detail="规则名称已存在")
            rule.name = new_name
    if payload.description is not None:
        rule.description = payload.description
    if payload.trigger_type is not None and payload.trigger_type != rule.trigger_type:
        rule.trigger_type = payload.trigger_type
        if rule.trigger_type == "status_offline":
            rule.payload_field = None
            rule.comparator = None
            rule.threshold = None
    if payload.target_type is not None:
        rule.target_type = payload.target_type
    if payload.target_ids is not None:
        rule.target_ids = _validate_alert_targets(db, current_user, rule.target_type, payload.target_ids)
    else:
        rule.target_ids = _validate_alert_targets(db, current_user, rule.target_type, rule.target_ids)
    if rule.trigger_type == "payload_threshold":
        if payload.payload_field is not None:
            rule.payload_field = payload.payload_field
        if payload.comparator is not None:
            rule.comparator = payload.comparator
        if payload.threshold is not None:
            rule.threshold = payload.threshold
    else:
        rule.payload_field = None
        rule.comparator = None
        rule.threshold = None
    if payload.status_from is not None:
        rule.status_from = payload.status_from
    if payload.status_to is not None:
        rule.status_to = payload.status_to
    if payload.consecutive_failures is not None:
        rule.consecutive_failures = payload.consecutive_failures
    if payload.cooldown_minutes is not None:
        rule.cooldown_minutes = payload.cooldown_minutes
    if payload.channels is not None:
        rule.channels = jsonable_encoder(payload.channels)
    if payload.is_active is not None:
        rule.is_active = payload.is_active
    db.commit()
    db.refresh(rule)
    return rule


@api_router.delete("/alerts/rules/{rule_id}")
def delete_alert_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    rule = (
        db.query(CrawlerAlertRule)
        .filter(
            CrawlerAlertRule.id == rule_id,
            CrawlerAlertRule.user_id == current_user.id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    db.delete(rule)
    db.commit()
    return {"ok": True}


@api_router.get("/alerts/events", response_model=list[CrawlerAlertEventOut])
def list_alert_events(
    rule_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    query = (
        db.query(CrawlerAlertEvent)
        .options(joinedload(CrawlerAlertEvent.crawler))
        .filter(CrawlerAlertEvent.user_id == current_user.id)
        .order_by(CrawlerAlertEvent.triggered_at.desc())
    )
    if rule_id is not None:
        query = query.filter(CrawlerAlertEvent.rule_id == rule_id)
    if status_filter:
        query = query.filter(CrawlerAlertEvent.status == status_filter)
    events = query.limit(limit).all()
    for event in events:
        if event.crawler:
            event.crawler_name = event.crawler.name
            event.crawler_local_id = event.crawler.local_id
    return events



# ------- 公共访问 -------


"""
以下公共访问逻辑保持不变
"""

def _serialise_logs(logs: List[LogEntry]) -> List[LogEntry]:
    for log in logs:
        if not getattr(log, "crawler_name", None) and log.crawler:
            log.crawler_name = log.crawler.name
        if log.crawler:
            log.crawler_local_id = log.crawler.local_id
        if log.api_key:
            log.api_key_local_id = log.api_key.local_id
    return logs


def _resolve_link(db: Session, slug: str) -> CrawlerAccessLink:
    link = (
        db.query(CrawlerAccessLink)
        .options(joinedload(CrawlerAccessLink.crawler).joinedload(Crawler.user))
        .options(joinedload(CrawlerAccessLink.api_key).joinedload(APIKey.user))
        .options(joinedload(CrawlerAccessLink.group).joinedload(CrawlerGroup.user))
        .options(joinedload(CrawlerAccessLink.group).joinedload(CrawlerGroup.crawlers))
        .filter(CrawlerAccessLink.slug == slug, CrawlerAccessLink.is_active == True)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="快捷链接不存在或已停用")
    return link


def _build_link_summary(link: CrawlerAccessLink, slug: str) -> dict[str, object]:
    if link.target_type == "crawler" and link.crawler:
        crawler = link.crawler
        owner = getattr(crawler, "user", None)
        owner_name = None
        if owner:
            owner_name = owner.display_name or owner.username
        summary = {
            "type": "crawler",
            "slug": slug,
            "crawler_id": crawler.id,
            "local_id": crawler.local_id,
            "name": crawler.name,
            "last_heartbeat": crawler.last_heartbeat,
            "last_source_ip": crawler.last_source_ip,
            "status": _compute_status(crawler.last_heartbeat),
            "is_public": crawler.is_public,
            "owner_id": crawler.user_id,
            "owner_name": owner_name,
            "log_max_lines": crawler.log_max_lines,
            "log_max_bytes": crawler.log_max_bytes,
            "link_description": link.description,
            "link_created_at": link.created_at,
            "allow_logs": link.allow_logs,
        }
    elif link.target_type == "api_key" and link.api_key:
        api_key = link.api_key
        owner = getattr(api_key, "user", None)
        owner_name = None
        if owner:
            owner_name = owner.display_name or owner.username
        crawler = api_key.crawler
        summary = {
            "type": "api_key",
            "slug": slug,
            "api_key_id": api_key.id,
            "local_id": api_key.local_id,
            "name": api_key.name,
            "last_used_at": api_key.last_used_at,
            "last_used_ip": api_key.last_used_ip,
            "owner_id": api_key.user_id,
            "owner_name": owner_name,
            "crawler_name": crawler.name if crawler else None,
            "crawler_status": _compute_status(crawler.last_heartbeat) if crawler else None,
            "link_description": link.description,
            "link_created_at": link.created_at,
            "allow_logs": link.allow_logs,
        }
    elif link.target_type == "group" and link.group:
        group = link.group
        owner = getattr(group, "user", None)
        owner_name = None
        if owner:
            owner_name = owner.display_name or owner.username
        crawler_entries = []
        status_counts = {"online": 0, "warning": 0, "offline": 0}
        for crawler in sorted(group.crawlers, key=lambda item: (item.local_id or 0, item.id)):
            status = _compute_status(crawler.last_heartbeat)
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1
            crawler_entries.append({
                "id": crawler.id,
                "local_id": crawler.local_id,
                "name": crawler.name,
                "status": status,
                "last_heartbeat": crawler.last_heartbeat,
                "last_source_ip": crawler.last_source_ip,
            })
        summary = {
            "type": "group",
            "slug": slug,
            "group_id": group.id,
            "group_slug": group.slug,
            "group_name": group.name,
            "owner_id": group.user_id,
            "owner_name": owner_name,
            "crawler_total": len(crawler_entries),
            "status_breakdown": status_counts,
            "crawlers": crawler_entries,
            "link_description": link.description,
            "link_created_at": link.created_at,
            "allow_logs": link.allow_logs,
        }
    else:
        raise HTTPException(status_code=400, detail="链接目标不存在")

    return jsonable_encoder(summary)


@public_router.get("/{slug}", response_class=HTMLResponse)
def public_crawler_page(request: Request, slug: str, db: Session = Depends(get_db)):
    link = _resolve_link(db, slug)
    summary = _build_link_summary(link, slug)
    context = {
        "request": request,
        "slug": slug,
        "link_summary": summary,
        "logs_endpoint": f"/pa/{slug}/api/logs",
    }
    return templates.TemplateResponse("public_link.html", context)


@public_router.get("/{slug}/api")
def public_crawler_summary_api(slug: str, db: Session = Depends(get_db)):
    link = _resolve_link(db, slug)
    return _build_link_summary(link, slug)


@public_router.get("/{slug}/api/logs/usage")
def public_logs_usage(slug: str, db: Session = Depends(get_db)):
    link = _resolve_link(db, slug)
    # 计算目标日志用量
    if link.target_type == "crawler" and link.crawler:
        lines, bytes_ = _measure_crawler_usage(db, link.crawler.id)
        max_lines, max_bytes = _effective_crawler_limits(link.crawler)
        return {"lines": lines, "bytes": bytes_, "max_lines": max_lines, "max_bytes": max_bytes}
    elif link.target_type == "api_key" and link.api_key:
        lines = db.query(func.count(LogEntry.id)).filter(LogEntry.api_key_id == link.api_key.id).scalar() or 0
        bytes_ = (
            db.query(func.coalesce(func.sum(func.length(LogEntry.message)), 0))
            .filter(LogEntry.api_key_id == link.api_key.id)
            .scalar()
            or 0
        )
        return {"lines": int(lines), "bytes": int(bytes_), "max_lines": None, "max_bytes": None}
    elif link.target_type == "group" and link.group:
        gid = link.group.id
        lines = (
            db.query(func.count(LogEntry.id))
            .filter(
                or_(
                    LogEntry.crawler.has(Crawler.group_id == gid),
                    LogEntry.api_key.has(APIKey.group_id == gid),
                )
            )
            .scalar()
            or 0
        )
        bytes_ = (
            db.query(func.coalesce(func.sum(func.length(LogEntry.message)), 0))
            .filter(
                or_(
                    LogEntry.crawler.has(Crawler.group_id == gid),
                    LogEntry.api_key.has(APIKey.group_id == gid),
                )
            )
            .scalar()
            or 0
        )
        return {"lines": int(lines), "bytes": int(bytes_), "max_lines": None, "max_bytes": None}
    else:
        raise HTTPException(status_code=400, detail="链接目标不存在")


@public_router.get("/{slug}/api/logs/stats")
def public_logs_stats(
    slug: str,
    hours: int = Query(24, ge=1, le=168, description="统计窗口（小时）"),
    buckets: int = Query(24, ge=2, le=240, description="分桶数量"),
    min_level: int = Query(0, ge=0, le=50),
    max_level: int = Query(50, ge=0, le=50),
    q: Optional[str] = Query(None, description="消息关键字或正则"),
    regex: bool = Query(False, description="q 是否为正则"),
    granularity: Optional[str] = Query(None, description="聚合粒度：auto/day/week"),
    db: Session = Depends(get_db),
):
    link = _resolve_link(db, slug)
    if not link.allow_logs:
        raise HTTPException(status_code=403, detail="该链接未开放日志访问")
    from_dt = now() - timedelta(hours=int(hours or 24))

    min_level = _normalize_level_code(min_level)
    max_level = _normalize_level_code(max_level)
    base = db.query(LogEntry.id, LogEntry.ts, LogEntry.message)
    if link.target_type == "crawler" and link.crawler:
        base = base.filter(LogEntry.crawler_id == link.crawler.id)
    elif link.target_type == "api_key" and link.api_key:
        base = base.filter(LogEntry.api_key_id == link.api_key.id)
    elif link.target_type == "group" and link.group:
        base = base.filter(
            or_(
                LogEntry.crawler.has(Crawler.group_id == link.group.id),
                LogEntry.api_key.has(APIKey.group_id == link.group.id),
            )
        )
    else:
        raise HTTPException(status_code=400, detail="链接目标不存在")

    qy = base.filter(LogEntry.ts >= from_dt).filter(LogEntry.level_code >= min_level).filter(LogEntry.level_code <= max_level)
    # 关键字：数据库端过滤；正则：Python 端过滤
    use_regex = bool(regex)
    text = (q or "").strip() if q else ""
    if text and not use_regex:
        qy = qy.filter(LogEntry.message.ilike(f"%{text}%"))
    qy = qy.order_by(LogEntry.ts.asc())
    rows = qy.limit(20000).all()  # 扫描上限
    if text and use_regex:
        try:
            pattern = re.compile(text)
            rows = [r for r in rows if pattern.search(r[2] or "")]
        except re.error:
            pass
    scanned = len(rows)
    if not rows:
        end_dt = now()
        return {"start": from_dt.isoformat(), "end": end_dt.isoformat(), "buckets": [], "total": 0, "scanned": 0}
    start_dt = rows[0][1]
    end_dt = rows[-1][1]
    b = max(2, int(buckets or 24))
    edges = _make_edges(start_dt, end_dt, b, granularity)
    counts = [0] * (len(edges) - 1)
    j = 0
    for _id, ts, _msg in rows:
        while j < len(edges) - 2 and ts >= edges[j + 1]:
            j += 1
        counts[j] += 1
    bucket_list = [{"t": edges[i].isoformat(), "count": counts[i]} for i in range(len(edges) - 1)]
    result = {"start": start_dt.isoformat(), "end": end_dt.isoformat(), "buckets": bucket_list, "total": sum(counts), "scanned": scanned}
    # 缓存（公开页缓存以 slug+参数为 key）
    key = (slug, hours, b, min_level, max_level, text, bool(regex), (granularity or "auto").lower())
    cached = _stats_cache_get(_PUBLIC_STATS_CACHE, key)
    if cached is not None:
        return cached
    _stats_cache_set(_PUBLIC_STATS_CACHE, key, result)
    return result


@public_router.get("/{slug}/api/logs", response_model=list[LogOut])
def public_logs(
    slug: str,
    start: Optional[date] = None,
    end: Optional[date] = None,
    min_level: int = Query(0, ge=0, le=50),
    max_level: int = Query(50, ge=0, le=50),
    limit: int = Query(200, ge=1, le=1000),
    q: Optional[str] = Query(None, description="消息关键字或正则"),
    regex: bool = Query(False, description="将 q 作为正则表达式进行匹配"),
    device: Optional[str] = Query(None, description="按设备名包含筛选"),
    ip: Optional[str] = Query(None, description="按来源 IP 包含筛选"),
    db: Session = Depends(get_db),
):
    link = _resolve_link(db, slug)
    if not link.allow_logs:
        raise HTTPException(status_code=403, detail="该链接未开放日志访问")
    min_level = _normalize_level_code(min_level)
    max_level = _normalize_level_code(max_level)
    if min_level > max_level:
        min_level, max_level = max_level, min_level

    query = db.query(LogEntry).options(joinedload(LogEntry.crawler), joinedload(LogEntry.api_key))
    if link.target_type == "crawler" and link.crawler:
        query = query.filter(LogEntry.crawler_id == link.crawler.id)
    elif link.target_type == "api_key" and link.api_key:
        query = query.filter(LogEntry.api_key_id == link.api_key.id)
    elif link.target_type == "group" and link.group:
        query = query.filter(
            or_(
                LogEntry.crawler.has(Crawler.group_id == link.group.id),
                LogEntry.api_key.has(APIKey.group_id == link.group.id),
            )
        )
    else:
        raise HTTPException(status_code=400, detail="链接目标不存在")

    query = _apply_log_filters(query, start, end, min_level, max_level)
    if device and device.strip():
        query = query.filter(LogEntry.device_name.ilike(f"%{device.strip()}%"))
    if ip and ip.strip():
        query = query.filter(LogEntry.source_ip.ilike(f"%{ip.strip()}%"))
    query, pattern = _maybe_apply_message_search(query, q, regex)
    query = query.order_by(LogEntry.ts.desc())
    if pattern is not None:
        scan_limit = min(max(limit * 10, limit), MAX_REGEX_SCAN)
        records = query.limit(scan_limit).all()
        asc = list(reversed(records))
        filtered = [item for item in asc if pattern.search(item.message or "")]
        sliced = filtered[-limit:] if limit else filtered
        return _serialise_logs(sliced)
    else:
        if limit:
            query = query.limit(limit)
        logs = list(reversed(query.all()))
        return _serialise_logs(logs)


router = api_router

__all__ = ["router", "public_router"]


# ---------- 统计与缓存辅助 ----------

def _stats_cache_get(cache: dict, key: tuple) -> dict | None:
    if STATS_CACHE_TTL <= 0:
        return None
    item = cache.get(key)
    if not item:
        return None
    ts, data = item
    if time.time() - ts > STATS_CACHE_TTL:
        return None
    return data


def _stats_cache_set(cache: dict, key: tuple, data: dict) -> None:
    if STATS_CACHE_TTL <= 0:
        return
    cache[key] = (time.time(), data)


def _make_edges(start_dt: datetime, end_dt: datetime, buckets: int, granularity: str | None) -> list[datetime]:
    b = max(2, int(buckets or 24))
    gran = (granularity or "auto").lower()
    if gran == "day":
        step = timedelta(days=1)
    elif gran == "week":
        step = timedelta(days=7)
    else:
        total_seconds = max(1.0, (end_dt - start_dt).total_seconds())
        step = timedelta(seconds=(total_seconds / b))
    edges: list[datetime] = [start_dt]
    while len(edges) < b:
        edges.append(edges[-1] + step)
        if edges[-1] >= end_dt:
            break
    if edges[-1] < end_dt:
        edges.append(end_dt)
    # 调整为恰好 b+1 个边界
    while len(edges) < b + 1:
        edges.append(edges[-1])
    if len(edges) > b + 1:
        edges = edges[: b + 1]
    return edges
