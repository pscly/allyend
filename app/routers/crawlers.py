"""
爬虫接入与监控 API：
- 统一归属到 /pa 路径
- 支持快捷访问链接、来源 IP 记录
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, time
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from ..constants import (
    LOG_LEVEL_CODE_TO_NAME,
    LOG_LEVEL_NAME_TO_CODE,
    MIN_QUICK_LINK_LENGTH,
    ROLE_ADMIN,
    ROLE_SUPERADMIN,
)
from ..dependencies import get_current_user, get_db
from ..models import (
    APIKey,
    Crawler,
    CrawlerAccessLink,
    CrawlerRun,
    LogEntry,
    User,
)
from ..schemas import (
    CrawlerOut,
    CrawlerRegisterRequest,
    CrawlerUpdate,
    LogCreate,
    LogOut,
    QuickLinkCreate,
    QuickLinkOut,
    RunOut,
    RunStartResponse,
)
from ..utils.time_utils import now


api_router = APIRouter(prefix="/pa/api", tags=["pa-crawlers"])
public_router = APIRouter(prefix="/pa", tags=["pa-public"])

LEVEL_CODES = sorted(LOG_LEVEL_CODE_TO_NAME.keys())
LEVEL_ALIASES = {"WARN": "WARNING", "ERR": "ERROR", "FATAL": "CRITICAL"}


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
    if request.client and request.client.host:
        return request.client.host
    return None


def _ensure_crawler_feature(user: User) -> None:
    if user.role in {ROLE_ADMIN, ROLE_SUPERADMIN}:
        return
    if user.group and not user.group.enable_crawlers:
        raise HTTPException(status_code=403, detail="当前分组未启用爬虫功能")


def _require_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> APIKey:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 X-API-Key")
    key = db.query(APIKey).filter(APIKey.key == x_api_key, APIKey.active == True).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key 无效")
    key.last_used_at = now()
    key.last_used_ip = _get_client_ip(request)
    db.commit()
    db.refresh(key)
    return key


@api_router.post("/register")
def register_crawler(
    payload: CrawlerRegisterRequest,
    request: Request,
    api_key: APIKey = Depends(_require_api_key),
    db: Session = Depends(get_db),
):
    ip = _get_client_ip(request)
    crawler = (
        db.query(Crawler)
        .filter(Crawler.user_id == api_key.user_id, Crawler.name == payload.name)
        .first()
    )
    if not crawler:
        max_local = db.query(func.max(Crawler.local_id)).filter(Crawler.user_id == api_key.user_id).scalar() or 0
        crawler = Crawler(name=payload.name, user_id=api_key.user_id, local_id=max_local + 1)
        crawler.last_source_ip = ip
        db.add(crawler)
        db.commit()
        db.refresh(crawler)
    else:
        crawler.last_source_ip = ip or crawler.last_source_ip
        db.commit()
    return {"id": crawler.id, "local_id": crawler.local_id, "name": crawler.name}


@api_router.post("/{crawler_id}/heartbeat")
def heartbeat(
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
    current_time = now()
    ip = _get_client_ip(request)
    crawler.last_heartbeat = current_time
    crawler.last_source_ip = ip or crawler.last_source_ip
    run = (
        db.query(CrawlerRun)
        .filter(CrawlerRun.crawler_id == crawler_id, CrawlerRun.status == "running")
        .order_by(CrawlerRun.started_at.desc())
        .first()
    )
    if run:
        run.last_heartbeat = current_time
        run.source_ip = ip or run.source_ip
    db.commit()
    return {"ok": True, "ts": current_time.isoformat()}


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
        )
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="运行不存在")
    run.status = status_
    run.ended_at = now()
    db.commit()
    return {"ok": True}


@api_router.post("/{crawler_id}/logs")
def write_log(
    crawler_id: int,
    payload: LogCreate,
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
    level_name, level_code = _resolve_log_level(payload)
    entry = LogEntry(
        level=level_name,
        level_code=level_code,
        message=payload.message,
        crawler_id=crawler_id,
        run_id=payload.run_id,
        source_ip=_get_client_ip(request),
        api_key_id=api_key.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"ok": True, "id": entry.id}


# ------- 管理端查询与操作 -------


@api_router.get("/me", response_model=list[CrawlerOut])
def my_crawlers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    crawlers = (
        db.query(Crawler)
        .filter(Crawler.user_id == current_user.id)
        .order_by(Crawler.local_id.asc())
        .all()
    )
    return crawlers


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
        .filter(Crawler.id == crawler_id, Crawler.user_id == current_user.id)
        .first()
    )
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    if payload.name and payload.name.strip():
        crawler.name = payload.name.strip()
    if payload.is_public is not None:
        crawler.is_public = payload.is_public
        if payload.is_public and not crawler.public_slug:
            crawler.public_slug = _ensure_quick_slug(db)
        if not payload.is_public:
            crawler.public_slug = None
    db.commit()
    db.refresh(crawler)
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


@api_router.get("/me/logs", response_model=list[LogOut])
def my_logs(
    crawler_ids: Optional[str] = Query(None, description="逗号分隔的爬虫ID列表"),
    start: Optional[date] = None,
    end: Optional[date] = None,
    min_level: int = Query(0, ge=0, le=50),
    max_level: int = Query(50, ge=0, le=50),
    limit: int = Query(200, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
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
    query = query.order_by(LogEntry.ts.desc())
    if limit:
        query = query.limit(limit)
    logs = list(reversed(query.all()))
    return _serialise_logs(logs)


@api_router.get("/me/{crawler_id}/logs", response_model=list[LogOut])
def my_crawler_logs(
    crawler_id: int,
    limit: int = 100,
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
    q = (
        db.query(LogEntry)
        .filter(LogEntry.crawler_id == crawler_id)
        .order_by(LogEntry.ts.desc())
        .options(joinedload(LogEntry.crawler), joinedload(LogEntry.api_key))
    )
    if limit:
        q = q.limit(max(1, min(limit, 1000)))
    logs = list(reversed(q.all()))
    return _serialise_logs(logs)


# ------- 快捷链接管理 -------


@api_router.get("/links", response_model=list[QuickLinkOut])
def list_quick_links(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_crawler_feature(current_user)
    links = (
        db.query(CrawlerAccessLink)
        .options(joinedload(CrawlerAccessLink.crawler), joinedload(CrawlerAccessLink.api_key))
        .outerjoin(Crawler)
        .outerjoin(APIKey)
        .filter(
            (Crawler.user_id == current_user.id)
            | (APIKey.user_id == current_user.id)
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
    if payload.target_type not in {"crawler", "api_key"}:
        raise HTTPException(status_code=400, detail="target_type 仅支持 crawler 或 api_key")

    crawler: Optional[Crawler] = None
    api_key: Optional[APIKey] = None

    if payload.target_type == "crawler":
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
    else:
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

    link = CrawlerAccessLink(
        slug=slug,
        target_type=payload.target_type,
        description=payload.description,
        allow_logs=payload.allow_logs,
        crawler=crawler,
        api_key=api_key,
        created_by=current_user,
    )
    db.add(link)
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
    owner_ids = []
    if link.crawler:
        owner_ids.append(link.crawler.user_id)
    if link.api_key:
        owner_ids.append(link.api_key.user_id)
    if current_user.id not in owner_ids and current_user.role not in {ROLE_ADMIN, ROLE_SUPERADMIN}:
        raise HTTPException(status_code=403, detail="无权删除该链接")
    db.delete(link)
    db.commit()
    return {"ok": True}


# ------- 公共访问 -------


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
        .options(joinedload(CrawlerAccessLink.crawler))
        .options(joinedload(CrawlerAccessLink.api_key))
        .filter(CrawlerAccessLink.slug == slug, CrawlerAccessLink.is_active == True)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="快捷链接不存在或已停用")
    return link


@public_router.get("/{slug}")
def public_crawler_summary(slug: str, db: Session = Depends(get_db)):
    link = _resolve_link(db, slug)
    if link.target_type == "crawler" and link.crawler:
        crawler = link.crawler
        return {
            "type": "crawler",
            "slug": slug,
            "crawler_id": crawler.id,
            "name": crawler.name,
            "last_heartbeat": crawler.last_heartbeat,
            "last_source_ip": crawler.last_source_ip,
            "is_public": crawler.is_public,
        }
    if link.target_type == "api_key" and link.api_key:
        api_key = link.api_key
        return {
            "type": "api_key",
            "slug": slug,
            "api_key_id": api_key.id,
            "name": api_key.name,
            "last_used_at": api_key.last_used_at,
            "last_used_ip": api_key.last_used_ip,
        }
    raise HTTPException(status_code=400, detail="链接目标不存在")


@public_router.get("/{slug}/logs", response_model=list[LogOut])
def public_logs(
    slug: str,
    start: Optional[date] = None,
    end: Optional[date] = None,
    min_level: int = Query(0, ge=0, le=50),
    max_level: int = Query(50, ge=0, le=50),
    limit: int = Query(200, ge=1, le=1000),
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
    else:
        raise HTTPException(status_code=400, detail="链接目标不存在")

    query = _apply_log_filters(query, start, end, min_level, max_level)
    query = query.order_by(LogEntry.ts.desc())
    if limit:
        query = query.limit(limit)
    logs = list(reversed(query.all()))
    return _serialise_logs(logs)


router = api_router

__all__ = ["router", "public_router"]
