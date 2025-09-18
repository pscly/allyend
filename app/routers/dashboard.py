"""
仪表盘与页面路由
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from ..models import Crawler, CrawlerRun, LogEntry, APIKey, User


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def root():
    return RedirectResponse(url="/dashboard")


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
    # 每个爬虫的最近日志
    latest_logs = {}
    for c in crawlers:
        log = (
            db.query(LogEntry)
            .filter(LogEntry.crawler_id == c.id)
            .order_by(LogEntry.ts.desc())
            .limit(5)
            .all()
        )
        latest_logs[c.id] = log
    keys = db.query(APIKey).filter(APIKey.user_id == current_user.id).order_by(APIKey.created_at.desc()).all()
    return templates.TemplateResponse(
        "crawlers.html",
        {
            "request": request,
            "user": current_user,
            "crawlers": crawlers,
            "latest_logs": latest_logs,
            "keys": keys,
        },
    )

