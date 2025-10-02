"""
认证/用户/Key 管理路由：
- /login, /register 页面
- /api/auth/login, /api/auth/register 接口
- /api/keys 管理 API Key
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import UploadFile, File
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..auth import create_access_token, get_password_hash, verify_password, get_token_from_request, decode_token
from ..config import settings
from ..constants import ROLE_ADMIN, ROLE_SUPERADMIN, ROLE_USER, THEME_PRESETS, LOG_LEVEL_OPTIONS
from ..dependencies import get_current_user, get_db
from ..models import APIKey, Crawler, CrawlerGroup, InviteCode, InviteUsage, SystemSetting, User, UserGroup, UserSession
from ..schemas import UserCreate, APIKeyOut, APIKeyCreate, APIKeyUpdate, PublicAPIKeyOut, UserProfileOut, LoginRequest, SessionOut
from ..utils.time_utils import now, aware_now
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
    """为保持兼容，API Key 输出携带爬虫字段但默认为空。

    由于一个 Key 现在可以对应多个工程，这里不再返回单一爬虫信息，
    前端如需工程列表，请调用 /pa/api/me。
    """
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
    remember_me: Optional[str] = Form(default=None),
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
    remember = bool(remember_me)
    session = _create_session(db, user, request, remember)
    expires_minutes = 30 * 24 * 60 if remember else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    token = create_access_token(str(user.id), expires_minutes, session_id=session.session_id)
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
        max_age=expires_minutes * 60,
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
            request.headers.get("X-Real-IP"),
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


def _create_session(db: Session, user: User, request: Request, remember_me: bool) -> UserSession:
    sid = secrets.token_urlsafe(24)
    expires = aware_now() + (timedelta(days=30) if remember_me else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    session = UserSession(
        session_id=sid,
        user=user,
        user_agent=request.headers.get("User-Agent"),
        ip_address=request.headers.get("X-Real-IP") if request.client else None,
        remember_me=remember_me,
        created_at=aware_now(),
        last_active_at=aware_now(),
        expires_at=expires,
        revoked=False,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _clear_cookie(resp: Response) -> None:
    resp.delete_cookie(
        key="access_token",
        path=settings.COOKIE_PATH or "/",
        domain=settings.COOKIE_DOMAIN or None,
    )


@router.get("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    # 尝试注销当前会话
    token = get_token_from_request(request)
    if token:
        payload = decode_token(token)
        if payload and payload.get("sid"):
            session = (
                db.query(UserSession)
                .filter(UserSession.session_id == payload["sid"])
                .first()
            )
            if session:
                session.revoked = True
                db.add(session)
                db.commit()
    resp = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    _clear_cookie(resp)
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
        request.headers.get("X-Real-IP") if request.client else None,
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
def api_login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    # 创建会话（支持多设备）
    session = _create_session(db, user, request, bool(payload.remember_me))
    # 按记住我设置 Token 过期时间
    expires_minutes = 30 * 24 * 60 if payload.remember_me else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    token = create_access_token(str(user.id), expires_minutes, session_id=session.session_id)
    # 仅使用 Cookie 会话（HttpOnly + 可配置属性）
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        path=settings.COOKIE_PATH or "/",
        secure=bool(settings.COOKIE_SECURE),
        domain=settings.COOKIE_DOMAIN or None,
        max_age=expires_minutes * 60,
    )
    return user


@router.get("/api/users/me", response_model=UserProfileOut)
def api_current_user(current_user: User = Depends(get_current_user)):
    """返回当前登录用户的基础资料，供前端初始化"""
    return current_user


@router.post("/api/auth/logout")
def api_logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = get_token_from_request(request)
    if token:
        payload = decode_token(token)
        if payload and payload.get("sid"):
            session = (
                db.query(UserSession)
                .filter(UserSession.session_id == payload["sid"])
                .first()
            )
            if session:
                session.revoked = True
                db.add(session)
                db.commit()
    _clear_cookie(response)
    return {"ok": True}


@router.post("/api/users/me/avatar", response_model=UserProfileOut)
def upload_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    # 基本校验
    content_type = (file.content_type or "").lower()
    if content_type not in {"image/png", "image/jpeg", "image/webp", "image/jpg"}:
        raise HTTPException(status_code=400, detail="仅支持 PNG/JPEG/WEBP 图片")
    suffix = Path(file.filename or "avatar").suffix.lower() or ".png"

    # 保存到 /avatars/{user_id}/
    user_dir = Path(settings.FILE_STORAGE_DIR).resolve() / "avatars" / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    target_name = f"avatar_{int(aware_now().timestamp())}{suffix}"
    target_path = user_dir / target_name
    with target_path.open("wb") as out:
        while True:
            chunk = file.file.read(8192)
            if not chunk:
                break
            out.write(chunk)
    file.file.close()

    # 更新用户头像 URL
    current_user.avatar_url = f"/avatars/{current_user.id}/{target_name}"
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/api/users/me/avatar")
def delete_avatar(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.avatar_url = None
    db.add(current_user)
    db.commit()
    return {"ok": True}


@router.get("/api/auth/sessions", response_model=list[SessionOut])
def list_sessions(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    token = get_token_from_request(request)
    current_sid = None
    if token:
        payload = decode_token(token)
        current_sid = payload.get("sid") if payload else None
    sessions = (
        db.query(UserSession)
        .filter(UserSession.user_id == current_user.id)
        .order_by(UserSession.last_active_at.desc().nullslast(), UserSession.created_at.desc())
        .all()
    )
    result: list[SessionOut] = []
    for s in sessions:
        if s.revoked:
            continue
        item = SessionOut.model_validate(s)
        item.current = (s.session_id == current_sid)
        result.append(item)
    return result


@router.delete("/api/auth/sessions/{session_id}")
def revoke_session(session_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = (
        db.query(UserSession)
        .filter(UserSession.session_id == session_id, UserSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    session.revoked = True
    db.add(session)
    db.commit()
    return {"ok": True}


@router.get("/api/keys", response_model=list[APIKeyOut])
def list_keys(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    keys = (
        db.query(APIKey)
        .options(joinedload(APIKey.group))
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

    # 说明：API Key 与工程（Crawler）解绑为一对多关系，不再在创建 Key 时自动生成工程。
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
        actor_ip=request.headers.get("X-Real-IP") if request.client else None,
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
    if payload.description is not None:
        rec.description = payload.description
    if payload.active is not None:
        rec.active = payload.active
    if payload.is_public is not None:
        rec.is_public = payload.is_public
    if payload.allowed_ips is not None:
        rec.allowed_ips = payload.allowed_ips
    if payload.group_id is not None:
        if payload.group_id == 0:
            rec.group = None
        else:
            group = (
                db.query(CrawlerGroup)
                .filter(CrawlerGroup.id == payload.group_id, CrawlerGroup.user_id == current_user.id)
                .first()
            )
            if not group:
                raise HTTPException(status_code=404, detail="分组不存在或无权访问")
            rec.group = group
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
        actor_ip=request.headers.get("X-Real-IP") if request.client else None,
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
        actor_ip=request.headers.get("X-Real-IP") if request.client else None,
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
        actor_ip=request.headers.get("X-Real-IP") if request.client else None,
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
