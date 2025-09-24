"""管理员相关页面与接口"""
from __future__ import annotations

import secrets
from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session, joinedload

from ..config import settings
from ..constants import ROLE_USER, ROLE_ADMIN, ROLE_SUPERADMIN, THEME_PRESETS, LOG_LEVEL_OPTIONS
from ..dependencies import get_current_user, get_db
from ..models import InviteCode, SystemSetting, User, UserGroup
from ..utils.time_utils import now
from ..schemas import (
    AdminUserOut,
    AdminUserUpdate,
    InviteCodeCreate,
    InviteCodeOut,
    RegistrationSettingUpdate,
    SystemSettingsResponse,
    UserGroupOut,
)


# 将原 /admin 路由整体迁移到 /hjxgl，避免与前端 /admin 冲突
router = APIRouter(prefix="/hjxgl", tags=["admin"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
REGISTRATION_MODE_KEY = "registration_mode"
DEFAULT_REGISTRATION_MODE = "open" if settings.ALLOW_DIRECT_SIGNUP else "invite"

templates.env.globals.update(site_icp=settings.SITE_ICP, theme_presets=THEME_PRESETS, log_levels=LOG_LEVEL_OPTIONS, site_name=settings.SITE_NAME)


def _require_admin(user: User) -> None:
    if user.role not in {ROLE_ADMIN, ROLE_SUPERADMIN}:
        raise HTTPException(status_code=403, detail="需要管理员权限")


def _serialize_user(user: User) -> AdminUserOut:
    group = None
    if user.group:
        group = UserGroupOut(
            id=user.group.id,
            name=user.group.name,
            slug=user.group.slug,
            description=user.group.description,
            enable_crawlers=user.group.enable_crawlers,
            enable_files=user.group.enable_files,
        )
    invited_by = user.invited_by.username if user.invited_by else None
    return AdminUserOut(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        is_root_admin=user.is_root_admin,
        group=group,
        invited_by=invited_by,
        created_at=user.created_at,
    )


def _set_registration_mode(db: Session, mode: str) -> None:
    setting = db.query(SystemSetting).filter(SystemSetting.key == "registration_mode").first()
    if not setting:
        setting = SystemSetting(key="registration_mode", value=mode)
        db.add(setting)
    else:
        setting.value = mode
    db.commit()


def _generate_invite_code() -> str:
    return secrets.token_urlsafe(8)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def admin_console(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(current_user)
    mode_setting = db.query(SystemSetting).filter(SystemSetting.key == REGISTRATION_MODE_KEY).first()
    mode = mode_setting.value if mode_setting else DEFAULT_REGISTRATION_MODE
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": current_user,
            "registration_mode": mode,
        },
    )


@router.get("/api/users", response_model=list[AdminUserOut])
def admin_list_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(current_user)
    users = (
        db.query(User)
        .options(joinedload(User.group))
        .order_by(User.created_at.desc())
        .all()
    )
    return [_serialize_user(user) for user in users]


@router.patch("/api/users/{user_id}", response_model=AdminUserOut)
def admin_update_user(
    user_id: int,
    payload: AdminUserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.is_root_admin and current_user.role != ROLE_SUPERADMIN:
        raise HTTPException(status_code=403, detail="无法修改超级管理员")
    if payload.role:
        if payload.role not in {ROLE_USER, ROLE_ADMIN, ROLE_SUPERADMIN}:
            raise HTTPException(status_code=400, detail="角色非法")
        if payload.role == ROLE_SUPERADMIN and current_user.role != ROLE_SUPERADMIN:
            raise HTTPException(status_code=403, detail="无权提升为超级管理员")
        target.role = payload.role
        target.is_root_admin = payload.role == ROLE_SUPERADMIN
    if payload.group_id is not None:
        group = db.query(UserGroup).filter(UserGroup.id == payload.group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="用户组不存在")
        target.group = group
    if payload.is_active is not None:
        target.is_active = payload.is_active
    db.commit()
    db.refresh(target)
    return _serialize_user(target)


@router.get("/api/groups", response_model=list[UserGroupOut])
def admin_list_groups(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(current_user)
    groups = db.query(UserGroup).order_by(UserGroup.name).all()
    return groups


@router.get("/api/invites", response_model=list[InviteCodeOut])
def admin_list_invites(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(current_user)
    invites = (
        db.query(InviteCode)
        .order_by(InviteCode.created_at.desc())
        .all()
    )
    return invites


@router.post("/api/invites", response_model=InviteCodeOut)
def admin_create_invite(
    payload: InviteCodeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    code = _generate_invite_code()
    target_group = None
    if payload.target_group_id is not None:
        target_group = db.query(UserGroup).filter(UserGroup.id == payload.target_group_id).first()
        if not target_group:
            raise HTTPException(status_code=404, detail="用户组不存在")
    invite = InviteCode(
        code=code,
        note=payload.note,
        allow_admin=payload.allow_admin,
        target_group=target_group,
        max_uses=payload.max_uses,
        creator=current_user,
    )
    if payload.expires_in_minutes:
        invite.expires_at = now() + timedelta(minutes=payload.expires_in_minutes)
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


@router.delete("/api/invites/{invite_id}")
def admin_delete_invite(invite_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(current_user)
    invite = db.query(InviteCode).filter(InviteCode.id == invite_id).first()
    if not invite:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    db.delete(invite)
    db.commit()
    return {"ok": True}


@router.get("/api/settings", response_model=SystemSettingsResponse)
def admin_get_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(current_user)
    mode_setting = db.query(SystemSetting).filter(SystemSetting.key == REGISTRATION_MODE_KEY).first()
    mode = mode_setting.value if mode_setting else DEFAULT_REGISTRATION_MODE
    return SystemSettingsResponse(registration_mode=mode)


@router.patch("/api/settings/registration", response_model=SystemSettingsResponse)
def admin_update_registration(
    payload: RegistrationSettingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    _set_registration_mode(db, payload.mode)
    return SystemSettingsResponse(registration_mode=payload.mode)

