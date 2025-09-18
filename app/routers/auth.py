"""
认证/用户/Key 管理路由：
- /login, /register 页面
- /api/auth/login, /api/auth/register 接口
- /api/keys 管理 API Key
"""
from __future__ import annotations

from datetime import datetime
import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_password_hash, verify_password
from ..config import settings
from ..dependencies import get_db, get_current_user
from ..models import User, APIKey
from ..schemas import Token, UserCreate, APIKeyOut


router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("login.html", {"request": request, "mode": "login"})


@router.post("/login")
def login_form(response: Response, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名或密码错误")
    token = create_access_token(str(user.id), settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    resp = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    resp.set_cookie("access_token", token, httponly=False)  # 示例简化：生产建议设置为 httponly=True, secure, samesite
    return resp


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("login.html", {"request": request, "mode": "register"})


@router.post("/register")
def register_form(response: Response, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.username == username).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    user = User(username=username, hashed_password=get_password_hash(password))
    db.add(user)
    db.commit()
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@router.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    resp.delete_cookie("access_token")
    return resp


# -------- API 形式（可配合前端/移动端） --------


@router.post("/api/auth/register", response_model=Token)
def api_register(payload: UserCreate, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.username == payload.username).first()
    if exists:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(username=payload.username, hashed_password=get_password_hash(payload.password))
    db.add(user)
    db.commit()
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
    # 简化：明文保存；生产建议保存哈希并仅展示一次明文
    new_key = secrets.token_urlsafe(32)
    rec = APIKey(key=new_key, active=True, user_id=current_user.id)
    db.add(rec)
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

