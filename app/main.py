"""
应用入口：
- FastAPI 初始化、模板/静态资源、路由挂载
- 启动时创建数据库表
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine, apply_schema_upgrades, bootstrap_defaults
from .routers import auth as auth_router
from .routers import crawlers as crawlers_router
from .routers import dashboard as dashboard_router
from .routers import files as files_router


app = FastAPI(title=settings.SITE_NAME, version="0.2.0")

# CORS（按需开放）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态资源
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def on_startup():
    # 创建表（开发环境方便使用；生产建议迁移工具）
    Base.metadata.create_all(bind=engine)
    apply_schema_upgrades()
    bootstrap_defaults()


# 路由注册
app.include_router(auth_router.router)
app.include_router(crawlers_router.router)
app.include_router(crawlers_router.public_router)
app.include_router(files_router.router)
app.include_router(dashboard_router.router)


# 便于 uv run 直接引用
def get_app():
    return app



