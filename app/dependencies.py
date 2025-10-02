"""
依赖项：数据库会话、当前用户
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from typing import Optional
from sqlalchemy.orm import Session

from .database import SessionLocal
from .auth import get_token_from_request, decode_access_token, decode_token
from .models import User, UserSession
from .utils.time_utils import now


def get_db():
    """获取 DB 会话，使用后自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """从请求中解析当前用户，并在存在会话ID时校验与刷新活跃时间。"""
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证")

    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或被禁用")

    sid = payload.get("sid")
    if sid:
        session = (
            db.query(UserSession)
            .filter(UserSession.session_id == sid, UserSession.user_id == user.id)
            .first()
        )
        if not session or session.revoked:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话已失效")
        if session.expires_at and now() > session.expires_at:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话已过期")
        # 刷新活跃时间与 IP
        session.last_active_at = now()
        if request.client and request.headers.get("X-Real-IP"):
            session.ip_address = request.headers.get("X-Real-IP")
        db.add(session)
        db.commit()

    return user




def get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """可选当前用户，未登录返回 None"""
    try:
        return get_current_user(request, db)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise
