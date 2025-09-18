"""
仪表盘与页面路由
"""
from __future__ import annotations

import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..config import settings
from ..constants import THEME_PRESETS, LOG_LEVEL_OPTIONS
from ..dependencies import get_current_user, get_optional_user, get_db, get_optional_user
from ..models import Crawler, APIKey, User
from ..schemas import ThemeSettingOut, ThemeSettingUpdate


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals.update(site_icp=settings.SITE_ICP, theme_presets=THEME_PRESETS, log_levels=LOG_LEVEL_OPTIONS, site_name=settings.SITE_NAME)


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

