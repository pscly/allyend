"""
认证/用户/Key 管理路由：
- /login, /register 页面
- /api/auth/login, /api/auth/register 接口
- /api/keys 管理 API Key
"""
from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..auth import create_access_token, get_password_hash, verify_password
from ..config import settings
from ..constants import ROLE_ADMIN, ROLE_SUPERADMIN, ROLE_USER, THEME_PRESETS, LOG_LEVEL_OPTIONS
from ..dependencies import get_current_user, get_db
from ..models import APIKey, Crawler, CrawlerGroup, InviteCode, InviteUsage, SystemSetting, User, UserGroup
from ..schemas import UserCreate, APIKeyOut, APIKeyCreate, APIKeyUpdate, PublicAPIKeyOut, UserProfileOut
from ..utils.time_utils import now
from ..utils.audit import record_operation, summarize_api_key, summarize_group


router = APIRouter()

HEARTBEAT_OK_SECONDS = 5 * 60
HEARTBEAT_WARN_SECONDS = 15 * 60


def _derive_status(last_heartbeat: Optional[datetime]) -> str:
    if not last_heartbeat:
        return "offline"
    delta = (now() - last_heartbeat).total_seconds()
    if delta <= HEARTBEAT_OK_SECONDS:
        return "online"
    if delta <= HEARTBEAT_WARN_SECONDS:
        return "warning"
    return "offline"


_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
templates.env.globals.update(site_icp=settings.SITE_ICP, theme_presets=THEME_PRESETS, log_levels=LOG_LEVEL_OPTIONS, site_name=settings.SITE_NAME)

def _hydrate_api_key(key: APIKey) -> APIKey:
    crawler = getattr(key, "crawler", None)
    if crawler:
        status = _derive_status(crawler.last_heartbeat)
        key.crawler_id = crawler.id
        key.crawler_local_id = crawler.local_id
        key.crawler_name = crawler.name
        key.crawler_status = status
        key.crawler_last_heartbeat = crawler.last_heartbeat
        key.crawler_public_slug = crawler.public_slug
    else:
        key.crawler_id = None
        key.crawler_local_id = None
        key.crawler_name = None
        key.crawler_status = None
        key.crawler_last_heartbeat = None
        key.crawler_public_slug = None
    return key



REGISTRATION_MODE_KEY = "registration_mode"
DEFAULT_REGISTRATION_MODE = "open" if settings.ALLOW_DIRECT_SIGNUP else "invite"


def _get_registration_mode(db: Session) -> str:
    setting = db.query(SystemSetting).filter(SystemSetting.key == REGISTRATION_MODE_KEY).first()
    if setting:
        return setting.value
    return DEFAULT_REGISTRATION_MODE


def _get_default_group(db: Session) -> Optional[UserGroup]:
    group = db.query(UserGroup).filter(UserGroup.is_default == True).first()
    if group:
        return group
    return db.query(UserGroup).order_by(UserGroup.id).first()


def _validate_invite(db: Session, code: str) -> InviteCode:
    invite = db.query(InviteCode).filter(InviteCode.code == code).first()
    if not invite:
        raise HTTPException(status_code=400, detail="邀请码无效")
    if invite.expires_at and now() > invite.expires_at:
        raise HTTPException(status_code=400, detail="邀请码已过期")
    if invite.max_uses and invite.used_count >= invite.max_uses:
        raise HTTPException(status_code=400, detail="邀请码已用尽")
    return invite


def _assign_group_from_invite(invite: Optional[InviteCode], db: Session) -> Optional[UserGroup]:
    if invite and invite.target_group:
        return invite.target_group
    return _get_default_group(db)


def _compute_role(invite: Optional[InviteCode]) -> str:
    if invite:
        if invite.code == settings.ROOT_ADMIN_INVITE_CODE:
            return ROLE_SUPERADMIN
        if invite.allow_admin:
            return ROLE_ADMIN
    return ROLE_USER


def _perform_registration(
    db: Session,
    username: str,
    password: str,
    display_name: Optional[str],
    email: Optional[str],
    invite_code: Optional[str],
    request_ip: Optional[str] = None,
) -> User:
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if email and db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="邮箱已被占用")

    mode = _get_registration_mode(db)
    invite: Optional[InviteCode] = None

    if mode == "closed":
        raise HTTPException(status_code=403, detail="注册已关闭")

    if invite_code:
        invite = _validate_invite(db, invite_code.strip())
    elif mode == "invite":
        raise HTTPException(status_code=400, detail="当前注册需要邀请码")

    group = _assign_group_from_invite(invite, db)
    if not group:
        raise HTTPException(status_code=500, detail="缺少默认用户组，请联系管理员")

    role = _compute_role(invite)
    hashed_password = get_password_hash(password)

    user = User(
        username=username,
        hashed_password=hashed_password,
        role=role,
        is_root_admin=(role == ROLE_SUPERADMIN),
        group=group,
        invite_code=invite,
        invited_by=invite.creator if invite else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if invite:
        invite.used_count += 1
        usage = InviteUsage(invite=invite, user=user, ip_address=request_ip)
        db.add(usage)
        db.commit()

    return user


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    mode = _get_registration_mode(db)
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "mode": "login",
            "registration_mode": mode,
        },
    )


@router.post("/login")
def login_form(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "mode": "login",
                "registration_mode": _get_registration_mode(db),
                "error": "用户名或密码错误",
            },
            status_code=400,
        )
    token = create_access_token(str(user.id), settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    resp = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    # 表单登录也使用同样的 Cookie 策略
    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        path=settings.COOKIE_PATH or "/",
        secure=bool(settings.COOKIE_SECURE),
        domain=settings.COOKIE_DOMAIN or None,
    )
    return resp


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, db: Session = Depends(get_db)):
    mode = _get_registration_mode(db)
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "mode": "register",
            "registration_mode": mode,
        },
    )


@router.post("/register")
def register_form(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    display_name: Optional[str] = Form(default=None),
    email: Optional[str] = Form(default=None),
    invite_code: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    try:
        _perform_registration(
            db,
            username.strip(),
            password,
            display_name,
            email.strip() if email else None,
            invite_code,
            request.client.host if request.client else None,
        )
    except HTTPException as exc:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "mode": "register",
                "registration_mode": _get_registration_mode(db),
                "error": exc.detail,
                "username": username,
                "display_name": display_name,
                "email": email,
                "invite_code": invite_code,
            },
            status_code=exc.status_code if exc.status_code < 500 else 400,
        )
    # 注册成功后直接设置 Cookie 并跳转到控制台
    user = db.query(User).filter(User.username == username.strip()).first()
    token = create_access_token(str(user.id), settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    resp = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        path=settings.COOKIE_PATH or "/",
        secure=bool(settings.COOKIE_SECURE),
        domain=settings.COOKIE_DOMAIN or None,
    )
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    # 与设置时一致的 path/domain，确保删除生效
    resp.delete_cookie(
        key="access_token",
        path=settings.COOKIE_PATH or "/",
        domain=settings.COOKIE_DOMAIN or None,
    )
    return resp


# -------- API 形式（可配合前端/移动端） --------


@router.post("/api/auth/register", response_model=UserProfileOut)
def api_register(payload: UserCreate, request: Request, response: Response, db: Session = Depends(get_db)):
    _perform_registration(
        db,
        payload.username.strip(),
        payload.password,
        payload.display_name,
        payload.email.strip() if payload.email else None,
        payload.invite_code,
        request.client.host if request.client else None,
    )
    user = db.query(User).filter(User.username == payload.username.strip()).first()
    token = create_access_token(str(user.id), settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # 仅使用 Cookie 会话（HttpOnly + 可配置属性）
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        path=settings.COOKIE_PATH or "/",
        secure=bool(settings.COOKIE_SECURE),
        domain=settings.COOKIE_DOMAIN or None,
    )
    return user


@router.post("/api/auth/login", response_model=UserProfileOut)
def api_login(payload: UserCreate, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    token = create_access_token(str(user.id), settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # 仅使用 Cookie 会话（HttpOnly + 可配置属性）
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        path=settings.COOKIE_PATH or "/",
        secure=bool(settings.COOKIE_SECURE),
        domain=settings.COOKIE_DOMAIN or None,
    )
    return user


@router.get("/api/users/me", response_model=UserProfileOut)
def api_current_user(current_user: User = Depends(get_current_user)):
    """返回当前登录用户的基础资料，供前端初始化"""
    return current_user


@router.get("/api/keys", response_model=list[APIKeyOut])
def list_keys(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    keys = (
        db.query(APIKey)
        .options(joinedload(APIKey.group))
        .options(joinedload(APIKey.crawler))
        .filter(APIKey.user_id == current_user.id)
        .order_by(APIKey.local_id.asc())
        .all()
    )
    return [_hydrate_api_key(key) for key in keys]


@router.post("/api/keys", response_model=APIKeyOut)
def create_key(
    payload: APIKeyCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    new_key = secrets.token_urlsafe(48)
    max_local = db.query(func.max(APIKey.local_id)).filter(APIKey.user_id == current_user.id).scalar() or 0
    rec = APIKey(
        key=new_key,
        active=True,
        user_id=current_user.id,
        local_id=max_local + 1,
        name=payload.name,
        description=payload.description,
        allowed_ips=payload.allowed_ips,
        is_public=payload.is_public,
    )
    if payload.group_id is not None:
        group = (
            db.query(CrawlerGroup)
            .filter(CrawlerGroup.id == payload.group_id, CrawlerGroup.user_id == current_user.id)
            .first()
        )
        if not group:
            raise HTTPException(status_code=404, detail="分组不存在或无权访问")
        rec.group = group
    db.add(rec)
    db.flush()

    crawler_local = db.query(func.max(Crawler.local_id)).filter(Crawler.user_id == current_user.id).scalar() or 0
    crawler_name = payload.name or f"crawler-{crawler_local + 1}"
    crawler = Crawler(
        name=crawler_name,
        user_id=current_user.id,
        local_id=crawler_local + 1,
        api_key=rec,
        group_id=rec.group_id,
        is_public=payload.is_public,
        status="offline",
        status_changed_at=now(),
    )
    db.add(crawler)
    # 审计：Key 创建（注意不记录明文 key）
    record_operation(
        db,
        action="api_key.create",
        target_type="api_key",
        target_id=rec.id,
        target_name=rec.name or f"key#{rec.local_id}",
        before=None,
        after=summarize_api_key(rec),
        actor=current_user,
        actor_ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(rec)
    return _hydrate_api_key(rec)


@router.patch("/api/keys/{key_id}", response_model=APIKeyOut)
def update_key(
    key_id: int,
    payload: APIKeyUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rec = db.query(APIKey).filter(APIKey.id == key_id, APIKey.user_id == current_user.id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Key 不存在")
    before = summarize_api_key(rec)
    if payload.name is not None:
        rec.name = payload.name
        if rec.crawler:
            rec.crawler.name = payload.name or rec.crawler.name
    if payload.description is not None:
        rec.description = payload.description
    if payload.active is not None:
        rec.active = payload.active
    if payload.is_public is not None:
        rec.is_public = payload.is_public
        if rec.crawler:
            rec.crawler.is_public = payload.is_public
    if payload.allowed_ips is not None:
        rec.allowed_ips = payload.allowed_ips
    if payload.group_id is not None:
        if payload.group_id == 0:
            rec.group = None
            if rec.crawler:
                rec.crawler.group = None
        else:
            group = (
                db.query(CrawlerGroup)
                .filter(CrawlerGroup.id == payload.group_id, CrawlerGroup.user_id == current_user.id)
                .first()
            )
            if not group:
                raise HTTPException(status_code=404, detail="分组不存在或无权访问")
            rec.group = group
            if rec.crawler:
                rec.crawler.group = group
    # 审计：Key 更新
    record_operation(
        db,
        action="api_key.update",
        target_type="api_key",
        target_id=rec.id,
        target_name=rec.name or f"key#{rec.local_id}",
        before=before,
        after=summarize_api_key(rec),
        actor=current_user,
        actor_ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(rec)
    return _hydrate_api_key(rec)


@router.post("/api/keys/{key_id}/rotate", response_model=APIKeyOut)
def rotate_key(
    key_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rec = db.query(APIKey).filter(APIKey.id == key_id, APIKey.user_id == current_user.id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Key 不存在")
    before = summarize_api_key(rec)
    rec.key = secrets.token_urlsafe(48)
    rec.last_used_at = None
    rec.last_used_ip = None
    # 审计：Key 轮换（不记录明文，仅做字段变更快照）
    record_operation(
        db,
        action="api_key.rotate",
        target_type="api_key",
        target_id=rec.id,
        target_name=rec.name or f"key#{rec.local_id}",
        before=before,
        after=summarize_api_key(rec),
        actor=current_user,
        actor_ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(rec)
    return _hydrate_api_key(rec)


@router.delete("/api/keys/{key_id}")
def delete_key(
    key_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rec = db.query(APIKey).filter(APIKey.id == key_id, APIKey.user_id == current_user.id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Key 不存在")
    before = summarize_api_key(rec)
    db.delete(rec)
    # 审计：Key 删除
    record_operation(
        db,
        action="api_key.delete",
        target_type="api_key",
        target_id=rec.id,
        target_name=rec.name or f"key#{rec.local_id}",
        before=before,
        after=None,
        actor=current_user,
        actor_ip=request.client.host if request.client else None,
    )
    db.commit()
    return {"ok": True}


@router.get("/api/public/keys", response_model=list[PublicAPIKeyOut])
def list_public_keys(db: Session = Depends(get_db)):
    keys = (
        db.query(APIKey)
        .filter(APIKey.is_public == True, APIKey.active == True)
        .order_by(APIKey.created_at.desc())
        .all()
    )
    return [_hydrate_api_key(key) for key in keys]
