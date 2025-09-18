"""
爬虫接入与监控 API：
- 通过 X-API-Key 认证（对应用户）
- 注册爬虫、上报心跳、运行开始/结束、日志上报
"""
from __future__ import annotations

import secrets
from datetime import datetime, date, time
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from ..dependencies import get_db
from ..constants import LOG_LEVEL_CODE_TO_NAME, LOG_LEVEL_NAME_TO_CODE, LOG_LEVEL_OPTIONS
from ..models import APIKey, Crawler, CrawlerRun, LogEntry
from ..schemas import CrawlerRegisterRequest, RunStartResponse, LogCreate, CrawlerOut, RunOut, LogOut, CrawlerUpdate
from ..dependencies import get_current_user
from ..models import User


router = APIRouter(prefix="/api/crawlers", tags=["crawlers"])
LEVEL_CODES = sorted(LOG_LEVEL_CODE_TO_NAME.keys())
LEVEL_ALIASES = {"WARN": "WARNING", "ERR": "ERROR", "FATAL": "CRITICAL"}


def _normalize_level_code(code: int) -> int:
    """将任意整数映射到标准日志等级。"""
    closest = min(LEVEL_CODES, key=lambda x: abs(x - code))
    return closest


def _resolve_log_level(payload: LogCreate) -> tuple[str, int]:
    """根据请求体计算日志等级名称和代码。"""
    if payload.level_code is not None:
        normalized = _normalize_level_code(payload.level_code)
        name = LOG_LEVEL_CODE_TO_NAME.get(normalized, "INFO")
        return name, normalized
    level_name = (payload.level or "INFO").upper()
    if level_name in LOG_LEVEL_NAME_TO_CODE:
        return level_name, LOG_LEVEL_NAME_TO_CODE[level_name]
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


def _ensure_public_slug(crawler: Crawler, db: Session) -> None:
    if crawler.public_slug:
        return
    while True:
        candidate = secrets.token_urlsafe(6).replace('-', '').lower()
        exists = db.query(Crawler).filter(Crawler.public_slug == candidate).first()
        if not exists:
            crawler.public_slug = candidate
            break


def _serialise_logs(logs: List[LogEntry]) -> List[LogEntry]:
    for log in logs:
        if not getattr(log, "crawler_name", None) and log.crawler:
            log.crawler_name = log.crawler.name
    return logs

@router.get("/levels", tags=["meta"])
def list_log_levels():
    """提供前端可用的日志等级列表。"""
    return LOG_LEVEL_OPTIONS


def _require_api_key(x_api_key: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """通过 X-API-Key 获取用户ID"""
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 X-API-Key")
    key = db.query(APIKey).filter(APIKey.key == x_api_key, APIKey.active == True).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key 无效")
    return key.user_id


@router.post("/register")
def register_crawler(payload: CrawlerRegisterRequest, user_id: int = Depends(_require_api_key), db: Session = Depends(get_db)):
    # 同一用户下按名称去重
    crawler = db.query(Crawler).filter(Crawler.user_id == user_id, Crawler.name == payload.name).first()
    if not crawler:
        crawler = Crawler(name=payload.name, user_id=user_id)
        db.add(crawler)
        db.commit()
        db.refresh(crawler)
    return {"id": crawler.id, "name": crawler.name}


@router.post("/{crawler_id}/heartbeat")
def heartbeat(crawler_id: int, user_id: int = Depends(_require_api_key), db: Session = Depends(get_db)):
    crawler = db.query(Crawler).filter(Crawler.id == crawler_id, Crawler.user_id == user_id).first()
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    now = datetime.utcnow()
    crawler.last_heartbeat = now
    # 若有正在运行的 run，同步心跳
    run = (
        db.query(CrawlerRun)
        .filter(CrawlerRun.crawler_id == crawler_id, CrawlerRun.status == "running")
        .order_by(CrawlerRun.started_at.desc())
        .first()
    )
    if run:
        run.last_heartbeat = now
    db.commit()
    return {"ok": True, "ts": now.isoformat()}


@router.post("/{crawler_id}/runs/start", response_model=RunStartResponse)
def start_run(crawler_id: int, user_id: int = Depends(_require_api_key), db: Session = Depends(get_db)):
    crawler = db.query(Crawler).filter(Crawler.id == crawler_id, Crawler.user_id == user_id).first()
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    run = CrawlerRun(crawler_id=crawler_id, status="running", started_at=datetime.utcnow())
    db.add(run)
    db.commit()
    db.refresh(run)
    return RunStartResponse(id=run.id, status=run.status, started_at=run.started_at)


@router.post("/{crawler_id}/runs/{run_id}/finish")
def finish_run(crawler_id: int, run_id: int, status_: str = "success", user_id: int = Depends(_require_api_key), db: Session = Depends(get_db)):
    run = (
        db.query(CrawlerRun)
        .filter(CrawlerRun.id == run_id, CrawlerRun.crawler_id == crawler_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="运行不存在")
    run.status = status_
    run.ended_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/{crawler_id}/logs")
def write_log(crawler_id: int, payload: LogCreate, user_id: int = Depends(_require_api_key), db: Session = Depends(get_db)):
    crawler = db.query(Crawler).filter(Crawler.id == crawler_id, Crawler.user_id == user_id).first()
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    level_name, level_code = _resolve_log_level(payload)
    entry = LogEntry(
        level=level_name,
        level_code=level_code,
        message=payload.message,
        crawler_id=crawler_id,
        run_id=payload.run_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"ok": True, "id": entry.id}


# ------- 管理端查询（登录后查看） -------


@router.get("/me", response_model=list[CrawlerOut], tags=["me"])
def my_crawlers(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    crawlers = (
        db.query(Crawler)
        .filter(Crawler.user_id == current_user.id)
        .order_by(Crawler.created_at.desc())
        .all()
    )
    need_commit = False
    for crawler in crawlers:
        if crawler.is_public and not crawler.public_slug:
            _ensure_public_slug(crawler, db)
            need_commit = True
    if need_commit:
        db.commit()
        for crawler in crawlers:
            db.refresh(crawler)
    return crawlers



@router.patch("/me/{crawler_id}", response_model=CrawlerOut, tags=["me"])
def update_my_crawler(
    crawler_id: int,
    payload: CrawlerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    crawler = db.query(Crawler).filter(Crawler.id == crawler_id, Crawler.user_id == current_user.id).first()
    if not crawler:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    if payload.name is not None and payload.name.strip():
        crawler.name = payload.name.strip()
    if payload.is_public is not None:
        crawler.is_public = payload.is_public
        if payload.is_public:
            _ensure_public_slug(crawler, db)
        else:
            crawler.public_slug = None
    db.commit()
    db.refresh(crawler)
    return crawler

@router.get("/me/{crawler_id}/runs", response_model=list[RunOut], tags=["me"])
def my_crawler_runs(crawler_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 校验归属
    c = db.query(Crawler).filter(Crawler.id == crawler_id, Crawler.user_id == current_user.id).first()
    if not c:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    runs = (
        db.query(CrawlerRun)
        .filter(CrawlerRun.crawler_id == crawler_id)
        .order_by(CrawlerRun.started_at.desc())
        .all()
    )
    return runs


@router.get("/me/logs", response_model=list[LogOut], tags=["me"])
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
    ids = _parse_id_list(crawler_ids)
    min_level = _normalize_level_code(min_level)
    max_level = _normalize_level_code(max_level)
    if min_level > max_level:
        min_level, max_level = max_level, min_level
    query = (
        db.query(LogEntry)
        .join(Crawler)
        .filter(Crawler.user_id == current_user.id)
        .options(joinedload(LogEntry.crawler))
    )
    if ids:
        query = query.filter(LogEntry.crawler_id.in_(ids))
    query = _apply_log_filters(query, start, end, min_level, max_level)
    query = query.order_by(LogEntry.ts.desc())
    if limit:
        query = query.limit(limit)
    logs = list(reversed(query.all()))
    return _serialise_logs(logs)


@router.get("/me/{crawler_id}/logs", response_model=list[LogOut], tags=["me"])
def my_crawler_logs(crawler_id: int, limit: int = 100, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.query(Crawler).filter(Crawler.id == crawler_id, Crawler.user_id == current_user.id).first()
    if not c:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    q = (
        db.query(LogEntry)
        .filter(LogEntry.crawler_id == crawler_id)
        .order_by(LogEntry.ts.desc())
        .options(joinedload(LogEntry.crawler))
    )
    if limit:
        q = q.limit(max(1, min(limit, 1000)))
    logs = list(reversed(q.all()))
    return _serialise_logs(logs)















@router.get("/public", response_model=list[CrawlerOut], tags=["public"])
def public_crawlers(db: Session = Depends(get_db)):
    crawlers = (
        db.query(Crawler)
        .filter(Crawler.is_public == True)
        .order_by(Crawler.created_at.desc())
        .all()
    )
    need_commit = False
    for crawler in crawlers:
        if crawler.is_public and not crawler.public_slug:
            _ensure_public_slug(crawler, db)
            need_commit = True
    if need_commit:
        db.commit()
        for crawler in crawlers:
            db.refresh(crawler)
    return crawlers


@router.get("/public/logs", response_model=list[LogOut], tags=["public"])
def public_logs(
    crawler_ids: Optional[str] = Query(None, description="逗号分隔的爬虫ID列表"),
    slug: Optional[str] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    min_level: int = Query(0, ge=0, le=50),
    max_level: int = Query(50, ge=0, le=50),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    ids = _parse_id_list(crawler_ids)
    min_level = _normalize_level_code(min_level)
    max_level = _normalize_level_code(max_level)
    if min_level > max_level:
        min_level, max_level = max_level, min_level
    query = (
        db.query(LogEntry)
        .join(Crawler)
        .filter(Crawler.is_public == True)
        .options(joinedload(LogEntry.crawler))
    )
    if slug:
        crawler = (
            db.query(Crawler)
            .filter(Crawler.public_slug == slug, Crawler.is_public == True)
            .first()
        )
        if not crawler:
            raise HTTPException(status_code=404, detail="公开爬虫不存在")
        query = query.filter(LogEntry.crawler_id == crawler.id)
    elif ids:
        query = query.filter(LogEntry.crawler_id.in_(ids))
    query = _apply_log_filters(query, start, end, min_level, max_level)
    query = query.order_by(LogEntry.ts.desc())
    if limit:
        query = query.limit(limit)
    logs = list(reversed(query.all()))
    return _serialise_logs(logs)









