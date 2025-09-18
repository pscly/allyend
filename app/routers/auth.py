"""
认证/用户/Key 管理路由：
- /login, /register 页面
- /api/auth/login, /api/auth/register 接口
- /api/keys 管理 API Key
"""
from __future__ import annotations

from datetime import datetime
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_password_hash, verify_password
from ..config import settings
from ..constants import ROLE_ADMIN, ROLE_SUPERADMIN, ROLE_USER, THEME_PRESETS, LOG_LEVEL_OPTIONS
from ..dependencies import get_current_user, get_db
from ..models import APIKey, InviteCode, InviteUsage, SystemSetting, User, UserGroup
from ..schemas import Token, UserCreate, APIKeyOut, APIKeyUpdate, PublicAPIKeyOut


router = APIRouter()

templates = Jinja2Templates(directory="app/templates")
templates.env.globals.update(site_icp=settings.SITE_ICP, theme_presets=THEME_PRESETS, log_levels=LOG_LEVEL_OPTIONS, site_name=settings.SITE_NAME)


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
    if invite.expires_at and datetime.utcnow() > invite.expires_at:
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
    resp.set_cookie("access_token", token, httponly=False)
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
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@router.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    resp.delete_cookie("access_token")
    return resp


# -------- API 形式（可配合前端/移动端） --------


@router.post("/api/auth/register", response_model=Token)
def api_register(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
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
    return Token(access_token=token)


@router.post("/api/auth/login", response_model=Token)
def api_login(payload: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    token = create_access_token(str(user.id), settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(access_token=token)


@router.get("/api/keys", response_model=list[APIKeyOut])
def list_keys(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    keys = db.query(APIKey).filter(APIKey.user_id == current_user.id).order_by(APIKey.created_at.desc()).all()
    return keys


@router.post("/api/keys", response_model=APIKeyOut)
def create_key(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    new_key = secrets.token_urlsafe(32)
    rec = APIKey(key=new_key, active=True, user_id=current_user.id)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.patch("/api/keys/{key_id}", response_model=APIKeyOut)
def update_key(key_id: int, payload: APIKeyUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rec = db.query(APIKey).filter(APIKey.id == key_id, APIKey.user_id == current_user.id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Key 不存在")
    if payload.name is not None:
        rec.name = payload.name
    if payload.description is not None:
        rec.description = payload.description
    if payload.active is not None:
        rec.active = payload.active
    if payload.is_public is not None:
        rec.is_public = payload.is_public
    db.commit()
    db.refresh(rec)
    return rec


@router.delete("/api/keys/{key_id}")
def delete_key(key_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rec = db.query(APIKey).filter(APIKey.id == key_id, APIKey.user_id == current_user.id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Key 不存在")
    db.delete(rec)
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
    return keys
