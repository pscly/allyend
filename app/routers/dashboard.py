"""
仪表盘与页面路由
"""
from __future__ import annotations

import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..config import settings
from ..constants import THEME_PRESETS, LOG_LEVEL_OPTIONS
from ..dependencies import get_current_user, get_optional_user, get_db
from ..models import (
    APIKey,
    Crawler,
    CrawlerRun,
    FileAccessLog,
    FileEntry,
    LogEntry,
    OperationAuditLog,
    User,
)
from ..schemas import (
    DashboardActivityItemOut,
    DashboardOverviewOut,
    ThemeSettingOut,
    ThemeSettingUpdate,
)
from ..utils.time_utils import aware_now


router = APIRouter()
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
templates.env.globals.update(site_icp=settings.SITE_ICP, theme_presets=THEME_PRESETS, log_levels=LOG_LEVEL_OPTIONS, site_name=settings.SITE_NAME)



DAILY_QUOTES = [
    "愿你所想都能如愿，所行皆有回应。",
    "给自己一个微笑，给世界一份善意。",
    "保持热爱，奔赴下一场山海。",
    "每天醒来，都是全新的自己。",
]


def _daily_quote() -> str:
    if not DAILY_QUOTES:
        return "这是一个美好的一天。"
    idx = aware_now().timetuple().tm_yday % len(DAILY_QUOTES)
    return DAILY_QUOTES[idx]


@router.get("/", response_class=HTMLResponse)
def home(request: Request, current_user: Optional[User] = Depends(get_optional_user)):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": current_user,
            "quote": _daily_quote(),
        },
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user,
        },
    )


@router.get("/dashboard/crawlers", response_class=HTMLResponse)
def crawlers_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    crawlers = (
        db.query(Crawler)
        .filter(Crawler.user_id == current_user.id)
        .order_by(Crawler.created_at.desc())
        .all()
    )
    keys = (
        db.query(APIKey)
        .filter(APIKey.user_id == current_user.id)
        .order_by(APIKey.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "crawlers.html",
        {
            "request": request,
            "user": current_user,
            "crawlers": crawlers,
            "keys": keys,
            # 初始不指定详情目标
            "initial_crawler_id": None,
        },
    )


@router.get("/dashboard/crawlers/{crawler_id}", response_class=HTMLResponse)
def crawler_detail_page(
    crawler_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """支持通过 URL 直接打开某个爬虫详情。

    - 仍复用 crawlers.html 模板，通过注入 initial_crawler_id 由前端脚本自动展开详情区域。
    - 若 ID 不属于当前用户，保持 404 以避免越权。
    """
    crawler = (
        db.query(Crawler)
        .filter(Crawler.id == crawler_id, Crawler.user_id == current_user.id)
        .first()
    )
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在或无权访问")

    keys = (
        db.query(APIKey)
        .filter(APIKey.user_id == current_user.id)
        .order_by(APIKey.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "crawlers.html",
        {
            "request": request,
            "user": current_user,
            "crawlers": [crawler],
            "keys": keys,
            "initial_crawler_id": crawler.id,
        },
    )


@router.get("/public", response_class=HTMLResponse)
def public_space(request: Request, current_user: Optional[User] = Depends(get_optional_user), db: Session = Depends(get_db)):
    keys = (
        db.query(APIKey)
        .filter(APIKey.is_public == True, APIKey.active == True)
        .order_by(APIKey.created_at.desc())
        .all()
    )
    crawlers = (
        db.query(Crawler)
        .filter(Crawler.is_public == True)
        .order_by(Crawler.created_at.desc())
        .all()
    )
    need_commit = False
    for crawler in crawlers:
        if crawler.is_public and not crawler.public_slug:
            while True:
                candidate = secrets.token_urlsafe(6).replace('-', '').lower()
                exists = db.query(Crawler).filter(Crawler.public_slug == candidate).first()
                if not exists:
                    crawler.public_slug = candidate
                    need_commit = True
                    break
    if need_commit:
        db.commit()
        for crawler in crawlers:
            db.refresh(crawler)
    return templates.TemplateResponse(
        "public.html",
        {
            "request": request,
            "user": current_user,
            "keys": keys,
            "crawlers": crawlers,
        },
    )


@router.get("/api/users/me/theme", response_model=ThemeSettingOut)
def get_my_theme(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/api/users/me/theme", response_model=ThemeSettingOut)
def update_my_theme(
    payload: ThemeSettingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    def pick_color(value: Optional[str], fallback: str) -> str:
        if value and isinstance(value, str) and value.startswith("#") and len(value) in (4, 7):
            return value
        return fallback

    if payload.theme_name is not None:
        user.theme_name = payload.theme_name
        preset = THEME_PRESETS.get(payload.theme_name)
        if preset and payload.theme_primary is None and payload.theme_secondary is None and payload.theme_background is None:
            user.theme_primary = preset["primary"]
            user.theme_secondary = preset["secondary"]
            user.theme_background = preset["background"]

    if payload.theme_primary is not None:
        user.theme_primary = pick_color(payload.theme_primary, user.theme_primary)
    if payload.theme_secondary is not None:
        user.theme_secondary = pick_color(payload.theme_secondary, user.theme_secondary)
    if payload.theme_background is not None:
        user.theme_background = pick_color(payload.theme_background, user.theme_background)
    if payload.is_dark_mode is not None:
        user.is_dark_mode = payload.is_dark_mode

    db.commit()
    db.refresh(user)
    return user


@router.get("/api/dashboard/overview", response_model=DashboardOverviewOut)
def get_dashboard_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """仪表盘概览：返回轻量统计与最近活动时间。"""
    crawlers_total = int(
        db.query(func.count(Crawler.id)).filter(Crawler.user_id == current_user.id).scalar() or 0
    )
    crawlers_online = int(
        db.query(func.count(Crawler.id))
        .filter(Crawler.user_id == current_user.id, Crawler.status == "online")
        .scalar()
        or 0
    )
    crawlers_offline = max(0, crawlers_total - crawlers_online)

    api_keys_total = int(
        db.query(func.count(APIKey.id)).filter(APIKey.user_id == current_user.id).scalar() or 0
    )

    files_total, files_total_bytes = (
        db.query(
            func.count(FileEntry.id),
            func.coalesce(func.sum(FileEntry.size_bytes), 0),
        )
        .filter(FileEntry.owner_id == current_user.id)
        .first()
        or (0, 0)
    )

    logs_total = int(
        db.query(func.count(LogEntry.id))
        .join(Crawler, LogEntry.crawler_id == Crawler.id)
        .filter(Crawler.user_id == current_user.id)
        .scalar()
        or 0
    )

    latest_audit = (
        db.query(func.max(OperationAuditLog.created_at))
        .filter(OperationAuditLog.actor_id == current_user.id)
        .scalar()
    )
    latest_file = (
        db.query(func.max(FileAccessLog.created_at))
        .filter(FileAccessLog.user_id == current_user.id)
        .scalar()
    )
    latest_run = (
        db.query(func.max(CrawlerRun.started_at))
        .join(Crawler, CrawlerRun.crawler_id == Crawler.id)
        .filter(Crawler.user_id == current_user.id)
        .scalar()
    )
    latest_candidates = [item for item in (latest_audit, latest_file, latest_run) if item]
    latest_activity_at = max(latest_candidates) if latest_candidates else None

    return DashboardOverviewOut(
        crawlers_total=crawlers_total,
        crawlers_online=crawlers_online,
        crawlers_offline=crawlers_offline,
        api_keys_total=api_keys_total,
        files_total=int(files_total or 0),
        files_total_bytes=int(files_total_bytes or 0),
        logs_total=logs_total,
        latest_activity_at=latest_activity_at,
    )


@router.get("/api/dashboard/activity", response_model=list[DashboardActivityItemOut])
def get_dashboard_activity(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """仪表盘最近活动：合并审计/文件/爬虫运行的轻量事件流。"""
    audit_logs = (
        db.query(OperationAuditLog)
        .filter(OperationAuditLog.actor_id == current_user.id)
        .order_by(OperationAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    file_logs = (
        db.query(FileAccessLog)
        .options(joinedload(FileAccessLog.file))
        .filter(FileAccessLog.user_id == current_user.id)
        .order_by(FileAccessLog.created_at.desc())
        .limit(limit)
        .all()
    )
    runs = (
        db.query(CrawlerRun)
        .join(Crawler, CrawlerRun.crawler_id == Crawler.id)
        .options(joinedload(CrawlerRun.crawler))
        .filter(Crawler.user_id == current_user.id)
        .order_by(CrawlerRun.started_at.desc())
        .limit(limit)
        .all()
    )

    events: list[DashboardActivityItemOut] = []

    for item in audit_logs:
        target_suffix = ""
        if item.target_name:
            target_suffix = f" {item.target_name}"
        elif item.target_id is not None:
            target_suffix = f" #{item.target_id}"
        message = f"{item.action} {item.target_type}{target_suffix}".strip()
        events.append(
            DashboardActivityItemOut(
                type="audit",
                action=item.action,
                message=message,
                created_at=item.created_at,
                actor=item.actor_name,
                ip_address=item.actor_ip,
                target_type=item.target_type,
                target_id=item.target_id,
            )
        )

    for item in file_logs:
        file_name = None
        if item.file and item.file.original_name:
            file_name = item.file.original_name
        elif item.file_id is not None:
            file_name = f"file#{item.file_id}"
        else:
            file_name = "file"
        message = f"{item.action} {file_name}"
        events.append(
            DashboardActivityItemOut(
                type="file",
                action=item.action,
                message=message,
                created_at=item.created_at,
                actor=current_user.username,
                ip_address=item.ip_address,
            )
        )

    for item in runs:
        crawler_name = item.crawler.name if item.crawler else f"crawler#{item.crawler_id}"
        message = f"{crawler_name} run {item.status}"
        events.append(
            DashboardActivityItemOut(
                type="crawler_run",
                action=item.status,
                message=message,
                created_at=item.started_at,
                actor=current_user.username,
                ip_address=item.source_ip,
                target_type="crawler",
                target_id=item.crawler_id,
            )
        )

    events.sort(key=lambda e: e.created_at, reverse=True)
    return events[:limit]

