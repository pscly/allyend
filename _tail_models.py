    crawler: Mapped["Crawler"] = relationship("Crawler", back_populates="heartbeat_events")

    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id"))
    api_key: Mapped["APIKey"] = relationship("APIKey")


class CrawlerCommand(Base):
    __tablename__ = "crawler_commands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    command: Mapped[str] = mapped_column(String(32))
    payload: Mapped[Optional[dict]] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    result: Mapped[Optional[dict]] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    crawler_id: Mapped[int] = mapped_column(ForeignKey("crawlers.id"))
    crawler: Mapped["Crawler"] = relationship("Crawler", back_populates="commands")

    issued_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    issued_by: Mapped[Optional["User"]] = relationship("User", back_populates="crawler_commands")


class CrawlerAccessLink(Base):
    __tablename__ = "crawler_access_links"
    __table_args__ = (UniqueConstraint("slug", name="uq_crawler_access_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    target_type: Mapped[str] = mapped_column(String(16))  # crawler / api_key / group
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_logs: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    crawler_id: Mapped[Optional[int]] = mapped_column(ForeignKey("crawlers.id"), nullable=True)
    crawler: Mapped[Optional[Crawler]] = relationship("Crawler", back_populates="quick_links")

    api_key_id: Mapped[Optional[int]] = mapped_column(ForeignKey("api_keys.id"), nullable=True)
    api_key: Mapped[Optional[APIKey]] = relationship("APIKey", back_populates="quick_links")

    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("crawler_groups.id"), nullable=True)
    group: Mapped[Optional[CrawlerGroup]] = relationship("CrawlerGroup", back_populates="quick_links")

    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by: Mapped[Optional[User]] = relationship("User")

    @property
    def crawler_local_id(self) -> Optional[int]:
        return self.crawler.local_id if self.crawler else None

    @property
    def api_key_local_id(self) -> Optional[int]:
        return self.api_key.local_id if self.api_key else None

    @property
    def group_slug(self) -> Optional[str]:
        return self.group.slug if self.group else None



class CrawlerConfigTemplate(Base):
    __tablename__ = "crawler_config_templates"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_crawler_config_template_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    format: Mapped[str] = mapped_column(String(16), default="json")
    content: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship("User", back_populates="config_templates")

    assignments: Mapped[List["CrawlerConfigAssignment"]] = relationship(
        "CrawlerConfigAssignment",
        back_populates="template",
    )


class CrawlerConfigAssignment(Base):
    __tablename__ = "crawler_config_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "target_type", "target_id", name="uq_crawler_config_assignment_target"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    format: Mapped[str] = mapped_column(String(16), default="json")
    content: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    target_type: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[int] = mapped_column(Integer)

    template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("crawler_config_templates.id"), nullable=True)
    template: Mapped[Optional["CrawlerConfigTemplate"]] = relationship("CrawlerConfigTemplate", back_populates="assignments")

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship("User", back_populates="config_assignments")


class CrawlerAlertRule(Base):
    __tablename__ = "crawler_alert_rules"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_crawler_alert_rule_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(32))
    target_type: Mapped[str] = mapped_column(String(16), default="all")
    target_ids: Mapped[list[int]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    payload_field: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    comparator: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status_from: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    status_to: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=1)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=10)
    channels: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship("User", back_populates="alert_rules")

    states: Mapped[List["CrawlerAlertState"]] = relationship("CrawlerAlertState", back_populates="rule", cascade="all, delete-orphan")
    events: Mapped[List["CrawlerAlertEvent"]] = relationship("CrawlerAlertEvent", back_populates="rule", cascade="all, delete-orphan")


class CrawlerAlertState(Base):
    __tablename__ = "crawler_alert_states"
    __table_args__ = (UniqueConstraint("rule_id", "crawler_id", name="uq_crawler_alert_state"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("crawler_alert_rules.id"))
    crawler_id: Mapped[int] = mapped_column(ForeignKey("crawlers.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    consecutive_hits: Mapped[int] = mapped_column(Integer, default=0)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    last_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    context: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    rule: Mapped["CrawlerAlertRule"] = relationship("CrawlerAlertRule", back_populates="states")
    crawler: Mapped["Crawler"] = relationship("Crawler")
    user: Mapped["User"] = relationship("User")


class CrawlerAlertEvent(Base):
    __tablename__ = "crawler_alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("crawler_alert_rules.id"))
    crawler_id: Mapped[int] = mapped_column(ForeignKey("crawlers.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)
    channel_results: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    rule: Mapped["CrawlerAlertRule"] = relationship("CrawlerAlertRule", back_populates="events")
    crawler: Mapped["Crawler"] = relationship("Crawler")
    user: Mapped["User"] = relationship("User", back_populates="alert_events")

class FileAPIToken(Base):
    __tablename__ = "file_api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    allowed_ips: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    allowed_cidrs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship("User", back_populates="file_tokens")

    uploads: Mapped[List["FileEntry"]] = relationship("FileEntry", back_populates="uploaded_by_token")
    logs: Mapped[List["FileAccessLog"]] = relationship("FileAccessLog", back_populates="token")


class FileEntry(Base):
    __tablename__ = "file_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    storage_path: Mapped[str] = mapped_column(String(255), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    visibility: Mapped[str] = mapped_column(String(16), default="private")  # private/group/public
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    download_count: Mapped[int] = mapped_column(Integer, default=0)

    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    owner: Mapped[Optional[User]] = relationship("User", back_populates="files_owned", foreign_keys=[owner_id])

    owner_group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user_groups.id"), nullable=True)
    owner_group: Mapped[Optional[UserGroup]] = relationship("UserGroup")

    uploaded_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_by_user: Mapped[Optional[User]] = relationship("User", foreign_keys=[uploaded_by_user_id])

    uploaded_by_token_id: Mapped[Optional[int]] = mapped_column(ForeignKey("file_api_tokens.id"), nullable=True)
    uploaded_by_token: Mapped[Optional[FileAPIToken]] = relationship("FileAPIToken", back_populates="uploads")

    access_logs: Mapped[List["FileAccessLog"]] = relationship("FileAccessLog", back_populates="file", cascade="all, delete-orphan")


class FileAccessLog(Base):
    __tablename__ = "file_access_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(32))  # upload/download/delete/list
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("file_entries.id"), nullable=True)
    file: Mapped[Optional[FileEntry]] = relationship("FileEntry", back_populates="access_logs")

    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    user: Mapped[Optional[User]] = relationship("User")

    token_id: Mapped[Optional[int]] = mapped_column(ForeignKey("file_api_tokens.id"), nullable=True)
    token: Mapped[Optional[FileAPIToken]] = relationship("FileAPIToken", back_populates="logs")

