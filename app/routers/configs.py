"""应用 JSON 配置管理与公开访问接口

- 公开读取：GET /pz?app=xxx 直接返回 JSON（无需登录），并记录访问日志（IP/UA/时间）
- 管理接口（需登录）：
  - GET   /api/configs                 列出所有 app 的配置（含最后更新时间与读取次数）
  - GET   /api/configs/{app}           获取指定 app 的配置详情
  - PUT   /api/configs/{app}           新建/更新配置（JSON 内容）
  - POST  /api/configs/{app}/upload    通过文件上传 JSON 配置
  - DELETE /api/configs/{app}          删除配置
  - GET   /api/configs/{app}/reads     最近访问日志列表
  - GET   /api/configs/{app}/stats     读取统计（时间序列 + Top IP）
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db, get_optional_user
from ..models import AppConfig, AppConfigReadLog
from ..schemas import (
    AppConfigListItem,
    AppConfigOut,
    AppConfigReadLogOut,
    AppConfigStatsOut,
    AppConfigStatsPoint,
    AppConfigUpsert,
)


router = APIRouter(prefix="/api/configs", tags=["configs"])
public_router = APIRouter(tags=["configs-public"])


def _client_ip(request: Request) -> Optional[str]:
    # 从常见代理头恢复真实 IP
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    xrip = request.headers.get("x-real-ip")
    if xrip:
        return xrip
    client = request.client
    return client.host if client else None


@public_router.get("/pz")
def fetch_public_config(app: str = Query(..., min_length=1, max_length=64), request: Request = None, db: Session = Depends(get_db)):
    """公开读取指定 app 的 JSON 配置。

    - 直接以 application/json 返回；
    - 记录访问日志（app/ip/ua/时间）。
    """
    cfg = db.query(AppConfig).filter(AppConfig.app == app).first()
    if not cfg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")
    # 若被禁用，则对外表现为不存在（避免泄露存在性）
    if cfg.enabled is False:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在或已禁用")

    # 校验内容是合法 JSON 字符串
    try:
        payload = json.loads(cfg.content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="配置内容不是有效的 JSON")

    # 记录访问日志
    try:
        log = AppConfigReadLog(
            app=app,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()

    return JSONResponse(content=payload)


@router.get("")
def list_configs(
    q: str | None = Query(None, description="按 app/描述 模糊搜索"),
    only_enabled: bool = Query(False, description="仅显示启用项"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> list[AppConfigListItem]:
    qry = db.query(AppConfig)
    if q:
        like = f"%{q}%"
        qry = qry.filter((AppConfig.app.ilike(like)) | (AppConfig.description.ilike(like)))
    if only_enabled:
        qry = qry.filter(AppConfig.enabled.is_(True))
    rows = qry.order_by(AppConfig.pinned_at.is_(None), AppConfig.pinned_at.desc(), AppConfig.updated_at.desc()).all()
    # 统计读取次数
    counts: dict[str, int] = {}
    if rows:
        apps = [r.app for r in rows]
        q = db.query(AppConfigReadLog.app).filter(AppConfigReadLog.app.in_(apps)).all()
        c = Counter([a for (a,) in q])
        counts = {k: int(v) for k, v in c.items()}
    return [
        AppConfigListItem(
            app=r.app,
            description=r.description,
            enabled=(r.enabled is not False),
            pinned=(r.pinned_at is not None),
            pinned_at=r.pinned_at,
            updated_at=r.updated_at,
            read_count=counts.get(r.app, 0),
        )
        for r in rows
    ]


@router.get("/{app}")
def get_config(app: str, db: Session = Depends(get_db), user=Depends(get_current_user)) -> AppConfigOut:
    cfg = db.query(AppConfig).filter(AppConfig.app == app).first()
    if not cfg:
        raise HTTPException(404, "配置不存在")
    try:
        content = json.loads(cfg.content)
    except json.JSONDecodeError:
        raise HTTPException(500, "配置内容不是有效的 JSON")
    return AppConfigOut(
        app=cfg.app,
        description=cfg.description,
        content=content,
        version=cfg.version,
        enabled=(cfg.enabled is not False),
        pinned=(cfg.pinned_at is not None),
        pinned_at=cfg.pinned_at,
        created_at=cfg.created_at,
        updated_at=cfg.updated_at,
    )


@router.put("/{app}")
def upsert_config(app: str, payload: AppConfigUpsert, db: Session = Depends(get_db), user=Depends(get_current_user)) -> AppConfigOut:
    # 验证 JSON 可序列化
    try:
        content_str = json.dumps(payload.content, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"JSON 序列化失败: {exc}")

    cfg = db.query(AppConfig).filter(AppConfig.app == app).first()
    if not cfg:
        cfg = AppConfig(app=app, description=payload.description, content=content_str, version=1)
        db.add(cfg)
    else:
        cfg.description = payload.description
        cfg.content = content_str
        cfg.version = (cfg.version or 0) + 1
    db.commit()
    db.refresh(cfg)
    return get_config(app, db)


@router.patch("/{app}/meta")
def update_meta(
    app: str,
    enabled: bool | None = Query(None, description="是否启用"),
    pinned: bool | None = Query(None, description="是否置顶"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> AppConfigOut:
    cfg = db.query(AppConfig).filter(AppConfig.app == app).first()
    if not cfg:
        raise HTTPException(404, "配置不存在")
    changed = False
    if enabled is not None:
        cfg.enabled = bool(enabled)
        changed = True
    if pinned is not None:
        cfg.pinned_at = datetime.utcnow() if pinned else None
        changed = True
    if changed:
        db.commit()
        db.refresh(cfg)
    return get_config(app, db)


@router.post("/{app}/upload")
async def upload_config(app: str, file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(get_current_user)) -> AppConfigOut:
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(400, "仅支持 .json 文件")
    data = await file.read()
    try:
        obj = json.loads(data.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"JSON 解析失败: {exc}")
    return upsert_config(app, AppConfigUpsert(description=None, content=obj), db)  # type: ignore[arg-type]


@router.delete("/{app}")
def delete_config(app: str, db: Session = Depends(get_db), user=Depends(get_current_user)) -> dict:
    cfg = db.query(AppConfig).filter(AppConfig.app == app).first()
    if not cfg:
        raise HTTPException(404, "配置不存在")
    db.delete(cfg)
    db.commit()
    return {"ok": True}


@router.get("/{app}/reads")
def list_reads(app: str, limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db), user=Depends(get_current_user)) -> list[AppConfigReadLogOut]:
    rows = (
        db.query(AppConfigReadLog)
        .filter(AppConfigReadLog.app == app)
        .order_by(AppConfigReadLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        AppConfigReadLogOut(app=r.app, ip_address=r.ip_address, user_agent=r.user_agent, created_at=r.created_at)
        for r in rows
    ]


@router.get("/{app}/stats")
def stats(
    app: str,
    days: int = Query(7, ge=1, le=60),
    granularity: str = Query("day", pattern="^(hour|day)$"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> AppConfigStatsOut:
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(AppConfigReadLog)
        .filter(AppConfigReadLog.app == app, AppConfigReadLog.created_at >= since)
        .order_by(AppConfigReadLog.created_at.asc())
        .all()
    )
    # 分桶
    buckets: dict[datetime, int] = {}
    for r in rows:
        dt = r.created_at
        if granularity == "hour":
            key = datetime(dt.year, dt.month, dt.day, dt.hour)
        else:
            key = datetime(dt.year, dt.month, dt.day)
        buckets[key] = buckets.get(key, 0) + 1

    series = [AppConfigStatsPoint(ts=k, count=v) for k, v in sorted(buckets.items(), key=lambda x: x[0])]

    # Top IP
    top = Counter([r.ip_address or "-" for r in rows]).most_common(10)
    return AppConfigStatsOut(app=app, range_days=days, granularity=granularity, series=series, top_ips=[(ip or "-", int(c)) for ip, c in top])
