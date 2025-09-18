"""
文件服务：匿名/注册/令牌上传与访问
"""
from __future__ import annotations

import hashlib
import ipaddress
import secrets
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..config import settings
from ..constants import FILE_STORAGE_DIR, ROLE_ADMIN, ROLE_SUPERADMIN, THEME_PRESETS, LOG_LEVEL_OPTIONS
from ..dependencies import get_current_user, get_db, get_optional_user
from ..models import FileAPIToken, FileAccessLog, FileEntry, User
from ..schemas import (
    FileAccessLogOut,
    FileEntryOut,
    FileTokenCreate,
    FileTokenOut,
    FileUploadResponse,
)

router = APIRouter(tags=["files"])

templates = Jinja2Templates(directory="app/templates")
templates.env.globals.update(site_icp=settings.SITE_ICP, theme_presets=THEME_PRESETS, log_levels=LOG_LEVEL_OPTIONS, site_name=settings.SITE_NAME)


STORAGE_ROOT = Path(settings.FILE_STORAGE_DIR or FILE_STORAGE_DIR)
ALLOWED_VISIBILITY = {"private", "group", "public"}

@router.get("/files", response_class=HTMLResponse)
def files_console(request: Request, current_user: Optional[User] = Depends(get_optional_user)):
    return templates.TemplateResponse("files.html", {"request": request, "user": current_user})



def _ensure_storage_dir(subdir: Optional[str] = None) -> Path:
    target = STORAGE_ROOT if not subdir else STORAGE_ROOT / subdir
    target.mkdir(parents=True, exist_ok=True)
    return target


def _get_client_ip(request: Request) -> Optional[str]:
    if request.client and request.client.host:
        return request.client.host
    return None


def _check_token_ip(token: FileAPIToken, request: Request) -> None:
    client_ip = _get_client_ip(request)
    if not client_ip:
        return
    if token.allowed_ips:
        ip_list = [ip.strip() for ip in token.allowed_ips.split(",") if ip.strip()]
        if ip_list and client_ip not in ip_list:
            raise HTTPException(status_code=403, detail="IP 未被允许访问该令牌")
    if token.allowed_cidrs:
        cidrs = [cidr.strip() for cidr in token.allowed_cidrs.split(",") if cidr.strip()]
        if cidrs:
            ip_obj = ipaddress.ip_address(client_ip)
            allowed = any(ip_obj in ipaddress.ip_network(cidr, strict=False) for cidr in cidrs)
            if not allowed:
                raise HTTPException(status_code=403, detail="IP 段未被允许访问该令牌")


def _save_upload_file(upload: UploadFile) -> tuple[str, int, str]:
    suffix = Path(upload.filename or "").suffix
    storage_name = f"{secrets.token_hex(16)}{suffix}"
    target_dir = _ensure_storage_dir("objects")
    target_path = target_dir / storage_name

    sha256 = hashlib.sha256()
    size = 0
    with target_path.open("wb") as buffer:
        while True:
            chunk = upload.file.read(8192)
            if not chunk:
                break
            size += len(chunk)
            sha256.update(chunk)
            buffer.write(chunk)
    upload.file.close()
    return storage_name, size, sha256.hexdigest()


def _log_action(
    db: Session,
    action: str,
    file: Optional[FileEntry],
    request: Request,
    user: Optional[User] = None,
    token: Optional[FileAPIToken] = None,
    status_text: str = "success",
) -> None:
    log = FileAccessLog(
        action=action,
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        status=status_text,
        file=file,
        user=user,
        token=token,
    )
    db.add(log)
    db.commit()


def _ensure_file_permission(file: FileEntry, current_user: Optional[User], token: Optional[FileAPIToken]) -> None:
    if file.visibility == "public":
        return
    if token:
        if file.owner_id == token.user_id:
            return
        raise HTTPException(status_code=403, detail="令牌无权访问该文件")
    if not current_user:
        raise HTTPException(status_code=403, detail="文件需要登录访问")
    if current_user.role in {ROLE_ADMIN, ROLE_SUPERADMIN}:
        return
    if file.visibility == "group" and current_user.group_id and file.owner_group_id == current_user.group_id:
        return
    if file.owner_id == current_user.id:
        return
    raise HTTPException(status_code=403, detail="无权访问该文件")


def _serialize_files(files: List[FileEntry]) -> List[FileEntryOut]:
    payload: List[FileEntryOut] = []
    for f in files:
        payload.append(
            FileEntryOut(
                id=f.id,
                original_name=f.original_name,
                description=f.description,
                content_type=f.content_type,
                size_bytes=f.size_bytes,
                visibility=f.visibility,
                is_anonymous=f.is_anonymous,
                download_count=f.download_count,
                created_at=f.created_at,
                owner_id=f.owner_id,
                owner_group_id=f.owner_group_id,
            )
        )
    return payload


@router.post("/files/up", response_model=FileUploadResponse)
def anonymous_upload(
    request: Request,
    upload: UploadFile = File(...),
    file_name: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    storage_name, size, checksum = _save_upload_file(upload)
    entry = FileEntry(
        storage_path=str(Path("objects") / storage_name),
        original_name=file_name or (upload.filename or storage_name),
        content_type=upload.content_type,
        size_bytes=size,
        checksum_sha256=checksum,
        visibility="public",
        is_anonymous=True,
        owner=None,
        owner_group=None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    _log_action(db, "upload", entry, request, user=None, token=None)
    return FileUploadResponse(
        file_id=entry.id,
        original_name=entry.original_name,
        visibility=entry.visibility,
        size_bytes=entry.size_bytes,
    )


@router.get("/files/public", response_model=list[FileEntryOut])
def list_public_files(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    files = (
        db.query(FileEntry)
        .filter(FileEntry.visibility == "public")
        .order_by(FileEntry.created_at.desc())
        .limit(limit)
        .all()
    )
    return _serialize_files(files)


@router.get("/files/{file_id}/download")
def download_file(
    file_id: int,
    request: Request,
    token_value: Optional[str] = Query(default=None, description="可选：通过 API Token 下载"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    token: Optional[FileAPIToken] = None
    if token_value:
        token = db.query(FileAPIToken).filter(FileAPIToken.token == token_value, FileAPIToken.is_active == True).first()
        if not token:
            raise HTTPException(status_code=403, detail="令牌无效或已禁用")
        _check_token_ip(token, request)
        current_user = token.user
    file = db.query(FileEntry).filter(FileEntry.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")
    _ensure_file_permission(file, current_user, token)
    storage_path = STORAGE_ROOT / file.storage_path
    if not storage_path.exists():
        _log_action(db, "download", file, request, user=current_user, token=token, status_text="missing")
        raise HTTPException(status_code=410, detail="文件已失效")
    file.download_count += 1
    db.commit()
    _log_action(db, "download", file, request, user=current_user, token=token)
    return FileResponse(
        storage_path,
        media_type=file.content_type or "application/octet-stream",
        filename=file.original_name,
    )


@router.post("/files/me/up", response_model=FileUploadResponse)
def user_upload(
    request: Request,
    upload: UploadFile = File(...),
    file_name: Optional[str] = Form(default=None),
    visibility: str = Form(default="private"),
    description: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if visibility not in ALLOWED_VISIBILITY:
        raise HTTPException(status_code=400, detail="可见性参数非法")
    storage_name, size, checksum = _save_upload_file(upload)
    entry = FileEntry(
        storage_path=str(Path("objects") / storage_name),
        original_name=file_name or (upload.filename or storage_name),
        description=description,
        content_type=upload.content_type,
        size_bytes=size,
        checksum_sha256=checksum,
        visibility=visibility,
        is_anonymous=False,
        owner=current_user,
        owner_group=current_user.group if visibility == "group" else None,
        uploaded_by_user=current_user,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    _log_action(db, "upload", entry, request, user=current_user, token=None)
    return FileUploadResponse(
        file_id=entry.id,
        original_name=entry.original_name,
        visibility=entry.visibility,
        size_bytes=entry.size_bytes,
    )


@router.get("/files/me", response_model=list[FileEntryOut])
def list_my_files(
    scope: Optional[str] = Query(default=None, description="可选：public/private/group/anonymous"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(FileEntry).filter(FileEntry.owner_id == current_user.id)
    if scope in ALLOWED_VISIBILITY:
        query = query.filter(FileEntry.visibility == scope)
    elif scope == "anonymous":
        query = db.query(FileEntry).filter(FileEntry.is_anonymous == True)
    files = query.order_by(FileEntry.created_at.desc()).all()
    return _serialize_files(files)


@router.delete("/files/me/{file_id}")
def delete_my_file(
    file_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = db.query(FileEntry).filter(FileEntry.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")
    if file.owner_id != current_user.id and current_user.role not in {ROLE_ADMIN, ROLE_SUPERADMIN}:
        raise HTTPException(status_code=403, detail="无权删除该文件")
    storage_path = STORAGE_ROOT / file.storage_path
    if storage_path.exists():
        storage_path.unlink()
    db.delete(file)
    db.commit()
    _log_action(db, "delete", file, request, user=current_user, token=None)
    return {"ok": True}


@router.post("/files/api/tokens", response_model=FileTokenOut)
def create_file_token(
    payload: FileTokenCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token_value = secrets.token_urlsafe(24)
    token = FileAPIToken(
        token=token_value,
        name=payload.name,
        description=payload.description,
        allowed_ips=payload.allowed_ips,
        allowed_cidrs=payload.allowed_cidrs,
        user=current_user,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    _log_action(db, "create_token", None, request, user=current_user, token=token)
    return token


@router.get("/files/api/tokens", response_model=list[FileTokenOut])
def list_file_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tokens = (
        db.query(FileAPIToken)
        .filter(FileAPIToken.user_id == current_user.id)
        .order_by(FileAPIToken.created_at.desc())
        .all()
    )
    return tokens


@router.patch("/files/api/tokens/{token_id}", response_model=FileTokenOut)
def update_file_token(
    token_id: int,
    is_active: Optional[bool] = Form(default=None),
    name: Optional[str] = Form(default=None),
    description: Optional[str] = Form(default=None),
    allowed_ips: Optional[str] = Form(default=None),
    allowed_cidrs: Optional[str] = Form(default=None),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token = (
        db.query(FileAPIToken)
        .filter(FileAPIToken.id == token_id, FileAPIToken.user_id == current_user.id)
        .first()
    )
    if not token:
        raise HTTPException(status_code=404, detail="令牌不存在")
    if is_active is not None:
        token.is_active = is_active
    if name is not None:
        token.name = name
    if description is not None:
        token.description = description
    if allowed_ips is not None:
        token.allowed_ips = allowed_ips
    if allowed_cidrs is not None:
        token.allowed_cidrs = allowed_cidrs
    db.commit()
    db.refresh(token)
    _log_action(db, "update_token", None, request, user=current_user, token=token)
    return token


@router.get("/files/api/logs", response_model=list[FileAccessLogOut])
def list_access_logs(
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base_query = db.query(FileAccessLog).order_by(FileAccessLog.created_at.desc())
    if current_user.role in {ROLE_ADMIN, ROLE_SUPERADMIN}:
        logs = base_query.limit(limit).all()
        return [
            FileAccessLogOut(
                id=log.id,
                action=log.action,
                ip_address=log.ip_address,
                status=log.status,
                created_at=log.created_at,
                file_id=log.file_id,
                user_id=log.user_id,
                token_id=log.token_id,
            )
            for log in logs
        ]
    else:
        logs = (
            base_query
            .join(FileEntry, FileAccessLog.file_id == FileEntry.id, isouter=True)
            .join(FileAPIToken, FileAccessLog.token_id == FileAPIToken.id, isouter=True)
            .filter(
                (FileEntry.owner_id == current_user.id)
                | (FileAPIToken.user_id == current_user.id)
                | (FileAccessLog.user_id == current_user.id)
            )
            .limit(limit)
            .all()
        )
        return [
            FileAccessLogOut(
                id=log.id,
                action=log.action,
                ip_address=log.ip_address,
                status=log.status,
                created_at=log.created_at,
                file_id=log.file_id,
                user_id=log.user_id,
                token_id=log.token_id,
            )
            for log in logs
        ]


@router.post("/files/{token_value}/up", response_model=FileUploadResponse)
def token_upload(
    token_value: str,
    request: Request,
    upload: UploadFile = File(...),
    file_name: Optional[str] = Form(default=None),
    visibility: str = Form(default="private"),
    description: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    token = (
        db.query(FileAPIToken)
        .filter(FileAPIToken.token == token_value, FileAPIToken.is_active == True)
        .first()
    )
    if not token:
        raise HTTPException(status_code=403, detail="令牌无效或已禁用")
    _check_token_ip(token, request)
    if visibility not in ALLOWED_VISIBILITY:
        raise HTTPException(status_code=400, detail="可见性参数非法")

    storage_name, size, checksum = _save_upload_file(upload)
    entry = FileEntry(
        storage_path=str(Path("objects") / storage_name),
        original_name=file_name or (upload.filename or storage_name),
        description=description,
        content_type=upload.content_type,
        size_bytes=size,
        checksum_sha256=checksum,
        visibility=visibility,
        is_anonymous=False,
        owner_id=token.user_id,
        owner_group=token.user.group if visibility == "group" else None,
        uploaded_by_token=token,
    )
    db.add(entry)
    token.usage_count += 1
    token.last_used_at = datetime.utcnow()
    db.commit()
    db.refresh(entry)
    _log_action(db, "upload", entry, request, user=None, token=token)
    return FileUploadResponse(
        file_id=entry.id,
        original_name=entry.original_name,
        visibility=entry.visibility,
        size_bytes=entry.size_bytes,
    )


@router.get("/files/{token_value}", response_model=list[FileEntryOut])
def token_list(
    token_value: str,
    request: Request,
    db: Session = Depends(get_db),
):
    token = (
        db.query(FileAPIToken)
        .filter(FileAPIToken.token == token_value, FileAPIToken.is_active == True)
        .first()
    )
    if not token:
        raise HTTPException(status_code=403, detail="令牌无效或已禁用")
    _check_token_ip(token, request)
    token.usage_count += 1
    token.last_used_at = datetime.utcnow()
    files = (
        db.query(FileEntry)
        .filter(FileEntry.owner_id == token.user_id)
        .order_by(FileEntry.created_at.desc())
        .all()
    )
    db.commit()
    _log_action(db, "list", None, request, user=None, token=token)
    return _serialize_files(files)

