"""
Pydantic 模型定义（请求/响应）
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    invite_code: Optional[str] = None


class UserGroupOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    enable_crawlers: bool
    enable_files: bool

    class Config:
        from_attributes = True


class InviteCodeCreate(BaseModel):
    note: Optional[str] = None
    allow_admin: bool = False
    max_uses: Optional[int] = None
    expires_in_minutes: Optional[int] = Field(
        default=None,
        description="可选：邀请码失效时间（分钟）",
        ge=1,
    )
    target_group_id: Optional[int] = None


class InviteCodeOut(BaseModel):
    id: int
    code: str
    note: Optional[str]
    allow_admin: bool
    max_uses: Optional[int]
    used_count: int
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyOut(BaseModel):
    id: int
    key: str
    name: Optional[str]
    description: Optional[str]
    active: bool
    is_public: bool
    created_at: datetime
    last_used_at: Optional[datetime]
    last_used_ip: Optional[str]

    class Config:
        from_attributes = True


class APIKeyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    is_public: Optional[bool] = None


class PublicAPIKeyOut(BaseModel):
    id: int
    key: str
    name: Optional[str]
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


class CrawlerOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    last_heartbeat: Optional[datetime] = None
    last_source_ip: Optional[str] = None
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
    source_ip: Optional[str] = None

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
    source_ip: Optional[str] = None
    api_key_id: Optional[int] = None

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


class QuickLinkCreate(BaseModel):
    slug: Optional[str] = Field(default=None, min_length=6, max_length=64)
    target_type: str
    target_id: int
    allow_logs: bool = True
    description: Optional[str] = None


class QuickLinkOut(BaseModel):
    id: int
    slug: str
    target_type: str
    description: Optional[str]
    is_active: bool
    allow_logs: bool
    created_at: datetime
    crawler_id: Optional[int] = None
    api_key_id: Optional[int] = None

    class Config:
        from_attributes = True


class FileTokenCreate(BaseModel):
    token: Optional[str] = Field(default=None, description='可选，自定义令牌，默认补齐 up- 前缀')
    name: Optional[str] = None
    description: Optional[str] = None
    allowed_ips: Optional[str] = Field(default=None, description="以逗号分隔的 IP 列表")
    allowed_cidrs: Optional[str] = Field(default=None, description="以逗号分隔的 CIDR")


class FileTokenOut(BaseModel):
    id: int
    token: str
    name: Optional[str]
    description: Optional[str]
    is_active: bool
    allowed_ips: Optional[str]
    allowed_cidrs: Optional[str]
    usage_count: int
    last_used_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class FileEntryOut(BaseModel):
    id: int
    original_name: str
    description: Optional[str]
    content_type: Optional[str]
    size_bytes: int
    visibility: str
    is_anonymous: bool
    download_count: int
    created_at: datetime
    owner_id: Optional[int]
    owner_group_id: Optional[int]
    download_name: Optional[str] = None
    download_url: Optional[str] = None

    class Config:
        from_attributes = True


class FileUploadResponse(BaseModel):
    file_id: int
    original_name: str
    visibility: str
    size_bytes: int


class FileAccessLogOut(BaseModel):
    id: int
    action: str
    ip_address: Optional[str]
    status: str
    created_at: datetime
    file_id: Optional[int]
    user_id: Optional[int]
    token_id: Optional[int]

    class Config:
        from_attributes = True


class SystemSettingOut(BaseModel):
    key: str
    value: str
    updated_at: datetime

    class Config:
        from_attributes = True


class AdminUserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    is_root_admin: bool
    group: Optional[UserGroupOut] = None
    invited_by: Optional[str] = None
    created_at: datetime


class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    group_id: Optional[int] = None
    is_active: Optional[bool] = None


class RegistrationSettingUpdate(BaseModel):
    mode: str = Field(..., pattern='^(open|invite|closed)$')


class SystemSettingsResponse(BaseModel):
    registration_mode: str

