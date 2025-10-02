"""
认证与安全工具
- 密码哈希：passlib[bcrypt]
- JWT：python-jose
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional, Tuple, Dict, Any

from fastapi import HTTPException, status, Request
from jose import jwt, JWTError
from passlib.context import CryptContext

from .config import settings
from .database import SessionLocal
from .models import User
from .utils.time_utils import aware_now


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)


def create_access_token(subject: str, expires_minutes: int, session_id: Optional[str] = None) -> str:
    """创建 JWT Token，subject 通常为用户ID。

    可选地携带会话ID（sid），用于多设备会话校验与注销。
    """
    expire = aware_now() + timedelta(minutes=expires_minutes)
    payload: Dict[str, Any] = {"sub": subject, "exp": expire}
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """解码 JWT，返回完整 payload。"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def decode_access_token(token: str) -> Optional[str]:
    """兼容旧用法：仅返回 subject（用户ID）"""
    payload = decode_token(token)
    if not payload:
        return None
    return payload.get("sub")


def get_token_from_request(request: Request) -> Optional[str]:
    """仅从 Cookie 中获取 Token（废弃 Authorization: Bearer 兼容）"""
    token = request.cookies.get("access_token")
    return token or None

