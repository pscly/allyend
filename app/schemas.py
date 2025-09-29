"""
Pydantic 模型定义（请求/响应）
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class UserProfileOut(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: str
    is_active: bool
    is_root_admin: bool
    group: Optional[UserGroupOut] = None
    theme_name: str
    theme_primary: str
    theme_secondary: str
    theme_background: str
    is_dark_mode: bool
    created_at: datetime
    # 日志配额（字节）：None 表示使用系统默认（前端可调用 /me/logs/usage 获取实际配额）
    log_quota_bytes: Optional[int] = None

    class Config:
        from_attributes = True


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


class CrawlerGroupOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    color: Optional[str] = None
    crawler_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class CrawlerGroupCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


class CrawlerGroupUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


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
    local_id: int
    key: str
    name: Optional[str]
    description: Optional[str]
    active: bool
    is_public: bool
    created_at: datetime
    last_used_at: Optional[datetime]
    last_used_ip: Optional[str]
    allowed_ips: Optional[str] = None
    group: Optional[CrawlerGroupOut] = None
    crawler_id: Optional[int] = None
    crawler_local_id: Optional[int] = None
    crawler_name: Optional[str] = None
    crawler_status: Optional[str] = None
    crawler_last_heartbeat: Optional[datetime] = None
    crawler_public_slug: Optional[str] = None

    class Config:
        from_attributes = True


class APIKeyCreate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    group_id: Optional[int] = None
    allowed_ips: Optional[str] = None
    is_public: bool = False


class APIKeyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    is_public: Optional[bool] = None
    group_id: Optional[int] = None
    allowed_ips: Optional[str] = None


class PublicAPIKeyOut(BaseModel):
    id: int
    local_id: int
    key: str
    name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CrawlerRegisterRequest(BaseModel):
    name: str


class HeartbeatPayload(BaseModel):
    status: Optional[str] = None
    payload: Optional[dict] = None
    device_name: Optional[str] = None


class RunStartResponse(BaseModel):
    id: int
    status: str
    started_at: datetime


class LogCreate(BaseModel):
    level: str = "INFO"
    level_code: Optional[int] = None
    message: str
    run_id: Optional[int] = None
    device_name: Optional[str] = None


class LogUsageOut(BaseModel):
    """单个爬虫日志用量信息"""
    lines: int
    bytes: int
    max_lines: Optional[int] = None
    max_bytes: Optional[int] = None


class UserLogUsageOut(BaseModel):
    """用户维度日志用量信息"""
    total_lines: int
    total_bytes: int
    quota_bytes: Optional[int] = None


class CrawlerOut(BaseModel):
    id: int
    local_id: Optional[int] = None
    name: str
    created_at: datetime
    last_heartbeat: Optional[datetime] = None
    last_source_ip: Optional[str] = None
    last_device_name: Optional[str] = None
    status: str
    status_changed_at: Optional[datetime] = None
    uptime_ratio: Optional[float] = None
    uptime_minutes: Optional[float] = None
    heartbeat_payload: Optional[dict] = None
    is_public: bool
    public_slug: Optional[str] = None
    # 隐藏状态
    is_hidden: bool
    pinned_at: Optional[datetime] = None
    pinned: Optional[bool] = None
    # 隐藏时间（可选）
    # 注意：为兼容老数据，允许 None
    # 由后端在隐藏/取消隐藏时维护
    # 前端一般无需直接显示
    # 这里保持为 Optional
    hidden_at: Optional[datetime] = None
    # 某些历史数据可能未绑定 API Key，这里允许为可空以避免 500
    api_key_id: Optional[int] = None
    api_key_local_id: Optional[int] = None
    api_key_name: Optional[str] = None
    api_key_active: Optional[bool] = None
    group: Optional[CrawlerGroupOut] = None
    config_assignment_id: Optional[int] = None
    config_assignment_name: Optional[str] = None
    config_assignment_version: Optional[int] = None
    config_assignment_format: Optional[str] = None
    # 日志上限设置（None 表示使用系统默认）
    log_max_lines: Optional[int] = None
    log_max_bytes: Optional[int] = None

    class Config:
        from_attributes = True


class CrawlerUpdate(BaseModel):
    name: Optional[str] = None
    is_public: Optional[bool] = None
    # 置顶/取消置顶
    pinned: Optional[bool] = None
    # 隐藏/取消隐藏
    is_hidden: Optional[bool] = None
    # 日志上限设置（可在前端修改）；None 表示保持不变
    log_max_lines: Optional[int] = None
    log_max_bytes: Optional[int] = None


class RunOut(BaseModel):
    id: int
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    source_ip: Optional[str] = None

    class Config:
        from_attributes = True


class CrawlerHeartbeatOut(BaseModel):
    id: int
    status: str
    payload: Optional[dict] = None
    source_ip: Optional[str] = None
    device_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CrawlerCommandOut(BaseModel):
    id: int
    command: str
    payload: Optional[dict] = None
    status: str
    result: Optional[dict] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CrawlerCommandCreate(BaseModel):
    command: str
    payload: Optional[dict] = None
    expires_in_seconds: Optional[int] = Field(default=None, ge=10, le=86400)


class CrawlerCommandAck(BaseModel):
    status: Optional[str] = Field(default=None, description="执行结果状态，例如 success/failed")
    result: Optional[dict] = None


class LogOut(BaseModel):
    id: int
    level: str
    level_code: int
    message: str
    ts: datetime
    run_id: Optional[int] = None
    crawler_id: int
    crawler_local_id: Optional[int] = None
    crawler_name: Optional[str] = None
    source_ip: Optional[str] = None
    device_name: Optional[str] = None
    api_key_id: Optional[int] = None
    api_key_local_id: Optional[int] = None

    class Config:
        from_attributes = True


class OperationAuditLogOut(BaseModel):
    id: int
    action: str
    target_type: str
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    before: Optional[dict] = None
    after: Optional[dict] = None
    actor_id: Optional[int] = None
    actor_name: Optional[str] = None
    actor_ip: Optional[str] = None
    created_at: datetime

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
    target_type: Literal["crawler", "api_key", "group"]
    target_id: int
    allow_logs: bool = True
    description: Optional[str] = None


class QuickLinkUpdate(BaseModel):
    slug: Optional[str] = Field(default=None, min_length=6, max_length=64)
    description: Optional[str] = None
    allow_logs: Optional[bool] = None
    is_active: Optional[bool] = None


class QuickLinkOut(BaseModel):
    id: int
    slug: str
    target_type: str
    description: Optional[str]
    is_active: bool
    allow_logs: bool
    created_at: datetime
    crawler_id: Optional[int] = None
    crawler_local_id: Optional[int] = None
    api_key_id: Optional[int] = None
    api_key_local_id: Optional[int] = None
    group_id: Optional[int] = None
    group_slug: Optional[str] = None
    group_name: Optional[str] = None

    class Config:
        from_attributes = True




class CrawlerConfigTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    format: Literal["json", "yaml"] = "json"
    content: str
    is_active: bool = True


class CrawlerConfigTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    format: Optional[Literal["json", "yaml"]] = None
    content: Optional[str] = None
    is_active: Optional[bool] = None


class CrawlerConfigTemplateOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    format: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CrawlerConfigAssignmentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    target_type: Literal["crawler", "group", "api_key"]
    target_id: int
    format: Literal["json", "yaml"] = "json"
    content: str
    template_id: Optional[int] = None
    is_active: bool = True


class CrawlerConfigAssignmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    format: Optional[Literal["json", "yaml"]] = None
    content: Optional[str] = None
    template_id: Optional[int] = None
    is_active: Optional[bool] = None


class CrawlerConfigAssignmentOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    target_type: str
    target_id: int
    format: str
    content: str
    version: int
    is_active: bool
    template_id: Optional[int] = None
    template_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CrawlerConfigFetchOut(BaseModel):
    has_config: bool
    assignment_id: Optional[int] = None
    name: Optional[str] = None
    format: Optional[str] = None
    version: Optional[int] = None
    content: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertChannelConfig(BaseModel):
    type: Literal["email", "webhook"]
    target: str
    enabled: bool = True
    note: Optional[str] = None


class CrawlerAlertRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: Literal["status_offline", "payload_threshold"]
    target_type: Literal["all", "group", "crawler", "api_key"] = "all"
    target_ids: list[int] = Field(default_factory=list)
    status_from: Optional[str] = None
    status_to: Optional[str] = None
    payload_field: Optional[str] = None
    comparator: Optional[Literal["gt", "ge", "lt", "le", "eq", "ne"]] = "gt"
    threshold: Optional[float] = None
    consecutive_failures: int = Field(default=1, ge=1, le=10)
    cooldown_minutes: int = Field(default=10, ge=0, le=1440)
    channels: list[AlertChannelConfig] = Field(default_factory=list)
    is_active: bool = True


class CrawlerAlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[Literal["status_offline", "payload_threshold"]] = None
    target_type: Optional[Literal["all", "group", "crawler", "api_key"]] = None
    target_ids: Optional[list[int]] = None
    status_from: Optional[str] = None
    status_to: Optional[str] = None
    payload_field: Optional[str] = None
    comparator: Optional[Literal["gt", "ge", "lt", "le", "eq", "ne"]] = None
    threshold: Optional[float] = None
    consecutive_failures: Optional[int] = Field(default=None, ge=1, le=10)
    cooldown_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    channels: Optional[list[AlertChannelConfig]] = None
    is_active: Optional[bool] = None


class CrawlerAlertRuleOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    trigger_type: str
    target_type: str
    target_ids: list[int]
    status_from: Optional[str] = None
    status_to: Optional[str] = None
    payload_field: Optional[str] = None
    comparator: Optional[str] = None
    threshold: Optional[float] = None
    consecutive_failures: int
    cooldown_minutes: int
    channels: list[AlertChannelConfig]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_triggered_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CrawlerAlertEventOut(BaseModel):
    id: int
    rule_id: int
    crawler_id: int
    crawler_local_id: Optional[int] = None
    crawler_name: Optional[str] = None
    triggered_at: datetime
    status: str
    message: Optional[str] = None
    payload: dict
    channel_results: list[dict]
    error: Optional[str] = None

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


class FileEntryUpdate(BaseModel):
    visibility: Optional[str] = None
    description: Optional[str] = None


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
    # 日志配额（字节）：None 表示使用系统默认
    log_quota_bytes: Optional[int] = None


class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    group_id: Optional[int] = None
    is_active: Optional[bool] = None
    # 设置用户日志配额（字节）；传 -1 或 0 表示无限制；None 不修改
    log_quota_bytes: Optional[int] = None


class RegistrationSettingUpdate(BaseModel):
    mode: str = Field(..., pattern='^(open|invite|closed)$')


class SystemSettingsResponse(BaseModel):
    registration_mode: str

