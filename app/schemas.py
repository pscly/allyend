"""
Pydantic 模型定义（请求/响应）
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str
    password: str


class APIKeyOut(BaseModel):
    id: int
    key: str
    active: bool
    is_public: bool
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyUpdate(BaseModel):
    active: Optional[bool] = None
    is_public: Optional[bool] = None


class PublicAPIKeyOut(BaseModel):
    id: int
    key: str
    created_at: datetime

    class Config:
        from_attributes = True


class CrawlerRegisterRequest(BaseModel):
    name: str


class RunStartResponse(BaseModel):
    id: int
    status: str
    started_at: datetime


class LogCreate(BaseModel):
    level: str = "INFO"
    level_code: Optional[int] = None
    message: str
    run_id: Optional[int] = None


# ------- 查询响应模型（前端/管理端） -------

class CrawlerOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    last_heartbeat: Optional[datetime] = None
    is_public: bool
    public_slug: Optional[str] = None

    class Config:
        from_attributes = True


class CrawlerUpdate(BaseModel):
    name: Optional[str] = None
    is_public: Optional[bool] = None


class RunOut(BaseModel):
    id: int
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None

    class Config:
        from_attributes = True


class LogOut(BaseModel):
    id: int
    level: str
    level_code: int
    message: str
    ts: datetime
    run_id: Optional[int] = None
    crawler_id: int
    crawler_name: Optional[str] = None

    class Config:
        from_attributes = True
class ThemeSettingOut(BaseModel):
    theme_name: str
    theme_primary: str
    theme_secondary: str
    theme_background: str
    is_dark_mode: bool

    class Config:
        from_attributes = True


class ThemeSettingUpdate(BaseModel):
    theme_name: Optional[str] = None
    theme_primary: Optional[str] = None
    theme_secondary: Optional[str] = None
    theme_background: Optional[str] = None
    is_dark_mode: Optional[bool] = None
