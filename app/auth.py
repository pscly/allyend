"""
认证与安全工具
- 密码哈希：passlib[bcrypt]
- JWT：python-jose
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

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


def create_access_token(subject: str, expires_minutes: int) -> str:
    """创建 JWT Token，subject 通常为用户ID"""
    expire = aware_now() + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """解码 JWT，返回 subject（用户ID）"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def get_token_from_request(request: Request) -> Optional[str]:
    """仅从 Cookie 中获取 Token（废弃 Authorization: Bearer 兼容）"""
    token = request.cookies.get("access_token")
    return token or None

