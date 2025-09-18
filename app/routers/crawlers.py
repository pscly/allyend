"""
爬虫接入与监控 API：
- 通过 X-API-Key 认证（对应用户）
- 注册爬虫、上报心跳、运行开始/结束、日志上报
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..models import APIKey, Crawler, CrawlerRun, LogEntry
from ..schemas import CrawlerRegisterRequest, RunStartResponse, LogCreate


router = APIRouter(prefix="/api/crawlers", tags=["crawlers"])


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
    entry = LogEntry(level=payload.level, message=payload.message, crawler_id=crawler_id, run_id=payload.run_id)
    db.add(entry)
    db.commit()
    return {"ok": True, "id": entry.id}

