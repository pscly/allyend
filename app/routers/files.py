"""
文件服务：用户网盘与令牌上传访问
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
import secrets
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status, Form
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
    FileEntryUpdate,
    FileTokenCreate,
    FileTokenOut,
    FileUploadResponse,
)
from ..utils.time_utils import now

router = APIRouter(tags=["files"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
templates.env.globals.update(site_icp=settings.SITE_ICP, theme_presets=THEME_PRESETS, log_levels=LOG_LEVEL_OPTIONS, site_name=settings.SITE_NAME)


STORAGE_ROOT = Path(settings.FILE_STORAGE_DIR or FILE_STORAGE_DIR)
ALLOWED_VISIBILITY = {"private", "group", "public", "disabled"}
TOKEN_PREFIX = "up-"
TOKEN_SUFFIX_PATTERN = re.compile(r'^[A-Za-z0-9_-]+$')
TOKEN_GENERATION_ATTEMPTS = 5
DUPLICATE_SUFFIX_RE = re.compile(r'^(?P<stem>.+?)-(?P<index>\d+)$')

@router.get("/files", response_class=HTMLResponse)
def files_list(request: Request, current_user: Optional[User] = Depends(get_optional_user), db: Session = Depends(get_db)):
    files = (
        db.query(FileEntry)
        .order_by(FileEntry.created_at.desc())
        .all()
    )
    aliases = _build_download_aliases(db, files)
    table = []
    for entry in files:
        download_name = aliases.get(entry.id, entry.original_name)
        owner_name = None
        if entry.owner:
            owner_name = entry.owner.display_name or entry.owner.username
        elif entry.uploaded_by_user:
            owner_name = entry.uploaded_by_user.display_name or entry.uploaded_by_user.username
        elif entry.uploaded_by_token:
            owner_name = entry.uploaded_by_token.name or f"令牌 {entry.uploaded_by_token.id}"
        download_path = f"/files/{download_name}"
        if download_name.startswith(TOKEN_PREFIX):
            download_path = f"{download_path}?download=1"
        table.append({
            "name": entry.original_name,
            "size": entry.size_bytes,
            "created": entry.created_at,
            "owner": owner_name,
            "download": download_path,
        })
    return templates.TemplateResponse(
        "files_list.html",
        {
            "request": request,
            "user": current_user,
            "files": table,
        },
    )


@router.get("/files/manage", response_class=HTMLResponse)
def files_manage(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("files_manage.html", {"request": request, "user": current_user})



def _ensure_storage_dir(subdir: Optional[str] = None) -> Path:
    target = STORAGE_ROOT if not subdir else STORAGE_ROOT / subdir
    target.mkdir(parents=True, exist_ok=True)
    return target


def _get_client_ip(request: Request) -> Optional[str]:
    if request.client and request.headers.get("X-Real-IP"):
        return request.headers.get("X-Real-IP")
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


def _split_filename_parts(name: str) -> tuple[str, str]:
    """
    拆分文件名与扩展名，返回 (主干, 扩展名)。
    """
    if not name:
        return "", ""
    if "." not in name:
        return name, ""
    idx = name.rfind(".")
    return name[:idx], name[idx:]


def _apply_duplicate_suffix(name: str, index: int) -> str:
    """
    根据序号为重名文件生成后缀，index 为 0 表示原名。
    """
    if index <= 0:
        return name
    stem, ext = _split_filename_parts(name)
    stem = stem or name
    ext = ext or ""
    return f"{stem}-{index}{ext}"


def _build_download_aliases(db: Session, entries: Sequence[FileEntry]) -> Dict[int, str]:
    """
    为给定文件列表生成下载别名，保证与数据库中相同原始名称的顺序一致。
    """
    alias_map: Dict[int, str] = {}
    if not entries:
        return alias_map
    names = {entry.original_name for entry in entries}
    for name in names:
        ids = (
            db.query(FileEntry.id)
            .filter(FileEntry.original_name == name)
            .order_by(FileEntry.created_at.asc(), FileEntry.id.asc())
            .all()
        )
        for offset, entry_id in enumerate(ids):
            alias_map[entry_id] = _apply_duplicate_suffix(name, offset)
    return alias_map


def _resolve_alias_target(db: Session, alias: str) -> tuple[str, int]:
    """
    将下载别名还原为原始文件名和序号。
    """
    base_name = alias
    suffix_index = 0
    stem, ext = _split_filename_parts(alias)
    match = DUPLICATE_SUFFIX_RE.match(stem) if stem else None
    if match:
        candidate_stem = match.group("stem")
        index_value = int(match.group("index"))
        candidate_base = f"{candidate_stem}{ext}"
        exists = (
            db.query(FileEntry.id)
            .filter(FileEntry.original_name == candidate_base)
            .order_by(FileEntry.id)
            .first()
        )
        if exists is not None:
            base_name = candidate_base
            suffix_index = index_value
    return base_name, suffix_index




def _generate_token_value(db: Session, requested: Optional[str]) -> str:
    """
    生成带 up- 前缀的 API 令牌，若用户指定则校验格式与唯一性。
    """
    candidate = (requested or '').strip()
    if candidate:
        normalized = candidate if candidate.startswith(TOKEN_PREFIX) else f"{TOKEN_PREFIX}{candidate}"
        suffix = normalized[len(TOKEN_PREFIX):]
        if not suffix:
            raise HTTPException(status_code=400, detail='自定义令牌需包含有效内容')
        if len(normalized) > 128:
            raise HTTPException(status_code=400, detail='令牌长度超出限制')
        if not TOKEN_SUFFIX_PATTERN.fullmatch(suffix):
            raise HTTPException(status_code=400, detail='令牌仅支持字母、数字、下划线与短横线')
        existing = db.query(FileAPIToken).filter(FileAPIToken.token == normalized).first()
        if existing:
            raise HTTPException(status_code=409, detail='令牌已被占用，请更换其他值')
        return normalized
    for _ in range(TOKEN_GENERATION_ATTEMPTS):
        generated = f"{TOKEN_PREFIX}{secrets.token_urlsafe(18)}"
        existing = db.query(FileAPIToken).filter(FileAPIToken.token == generated).first()
        if not existing:
            return generated
    raise HTTPException(status_code=500, detail='无法生成唯一令牌，请稍后再试')


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
    if file.visibility == "disabled":
        if token:
            raise HTTPException(status_code=403, detail="文件已被禁用")
        if current_user:
            if current_user.role in {ROLE_ADMIN, ROLE_SUPERADMIN}:
                return
            if file.owner_id == current_user.id:
                return
        raise HTTPException(status_code=403, detail="文件已被禁用")
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



def _serialize_files(db: Session, files: List[FileEntry]) -> List[FileEntryOut]:
    payload: List[FileEntryOut] = []
    if not files:
        return payload
    aliases = _build_download_aliases(db, files)
    for f in files:
        download_name = aliases.get(f.id, f.original_name)
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
                download_name=download_name,
                download_url=f"/files/{download_name}",
            )
        )
    return payload



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
    return _serialize_files(db, files)


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
    upload: UploadFile = File(..., alias='file'),
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
    scope: Optional[str] = Query(default=None, description="可选：public/private/group/disabled"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(FileEntry).filter(FileEntry.owner_id == current_user.id)
    if scope in ALLOWED_VISIBILITY:
        query = query.filter(FileEntry.visibility == scope)
    files = query.order_by(FileEntry.created_at.desc()).all()
    return _serialize_files(db, files)


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


@router.patch("/files/me/{file_id}", response_model=FileEntryOut)
def update_my_file(
    file_id: int,
    payload: FileEntryUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = db.query(FileEntry).filter(FileEntry.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")
    if file.owner_id != current_user.id and current_user.role not in {ROLE_ADMIN, ROLE_SUPERADMIN}:
        raise HTTPException(status_code=403, detail="无权修改该文件")

    changes = False

    if payload.visibility is not None:
        desired_visibility = payload.visibility.strip().lower()
        if desired_visibility not in ALLOWED_VISIBILITY:
            raise HTTPException(status_code=400, detail="可见性参数非法")
        if file.visibility != desired_visibility:
            if desired_visibility == "group":
                target_group = file.owner.group if file.owner and file.owner.group else current_user.group
                if not target_group:
                    raise HTTPException(status_code=400, detail="文件所属用户未加入任何分组，无法设置分组可见")
                file.owner_group = target_group
            else:
                file.owner_group = None
            file.visibility = desired_visibility
            changes = True

    if payload.description is not None:
        new_desc = payload.description.strip()
        normalized_desc = new_desc if new_desc else None
        if file.description != normalized_desc:
            file.description = normalized_desc
            changes = True

    if not changes:
        return _serialize_files(db, [file])[0]

    db.commit()
    db.refresh(file)
    _log_action(db, "update", file, request, user=current_user, token=None, status_text="update")
    return _serialize_files(db, [file])[0]


@router.post("/files/tokens", response_model=FileTokenOut)
def create_file_token(
    payload: FileTokenCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token_value = _generate_token_value(db, payload.token)
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


@router.get("/files/tokens", response_model=list[FileTokenOut])
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


@router.patch("/files/tokens/{token_id}", response_model=FileTokenOut)
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
    upload: UploadFile = File(..., alias="file"),
    file_name: Optional[str] = Form(default=None),
    visibility: str = Form(default="private"),
    description: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    token_value = token_value.strip()
    if not token_value.startswith(TOKEN_PREFIX):
        raise HTTPException(status_code=400, detail='令牌格式不正确，需以 up- 开头')
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
    token.last_used_at = now()
    db.commit()
    db.refresh(entry)
    _log_action(db, "upload", entry, request, user=None, token=token)
    return FileUploadResponse(
        file_id=entry.id,
        original_name=entry.original_name,
        visibility=entry.visibility,
        size_bytes=entry.size_bytes,
    )





def _download_file_by_alias(
    filename: str,
    request: Request,
    db: Session,
    current_user: Optional[User],
):
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=404, detail="文件不存在")
    base_name, suffix_index = _resolve_alias_target(db, filename)
    entries = (
        db.query(FileEntry)
        .filter(FileEntry.original_name == base_name)
        .order_by(FileEntry.created_at.asc(), FileEntry.id.asc())
        .all()
    )
    if not entries or suffix_index >= len(entries):
        raise HTTPException(status_code=404, detail="文件不存在")
    entry = entries[suffix_index]
    expected_alias = _apply_duplicate_suffix(base_name, suffix_index)
    if expected_alias != filename:
        raise HTTPException(status_code=404, detail="文件不存在")
    _ensure_file_permission(entry, current_user, None)
    storage_path = STORAGE_ROOT / entry.storage_path
    if not storage_path.exists():
        _log_action(db, "download", entry, request, user=current_user, token=None, status_text="missing")
        raise HTTPException(status_code=410, detail="文件已失效")
    entry.download_count += 1
    db.commit()
    _log_action(db, "download", entry, request, user=current_user, token=None)
    return FileResponse(
        storage_path,
        media_type=entry.content_type or "application/octet-stream",
        filename=entry.original_name,
    )


@router.get("/files/{identifier}")
def files_entry(
    identifier: str,
    request: Request,
    download: bool = Query(default=False, description="为 true 时强制按文件下载"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    identifier = identifier.strip()
    if not download and identifier.startswith(TOKEN_PREFIX):
        token = (
            db.query(FileAPIToken)
            .filter(FileAPIToken.token == identifier, FileAPIToken.is_active == True)
            .first()
        )
        if token:
            _check_token_ip(token, request)
            token.usage_count += 1
            token.last_used_at = now()
            files = (
                db.query(FileEntry)
                .filter(FileEntry.owner_id == token.user_id)
                .order_by(FileEntry.created_at.desc())
                .all()
            )
            db.commit()
            _log_action(db, "list", None, request, user=None, token=token)
            return _serialize_files(db, files)
        raise HTTPException(status_code=403, detail="令牌无效或已禁用")

    return _download_file_by_alias(identifier, request, db, current_user)
