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

