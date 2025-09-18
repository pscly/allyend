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
    message: str
    run_id: Optional[int] = None


# ------- 查询响应模型（前端/管理端） -------

class CrawlerOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    last_heartbeat: Optional[datetime] = None

    class Config:
        from_attributes = True


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
    message: str
    ts: datetime
    run_id: Optional[int] = None

    class Config:
        from_attributes = True
