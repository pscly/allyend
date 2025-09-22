import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.auth import get_password_hash
from app.database import Base
from app.dependencies import get_db
from app.main import app
from app.models import User


@pytest.fixture()
def session_factory():
    """构建共享的内存数据库 Session 工厂，并注入 FastAPI 依赖"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        yield TestingSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(session_factory):
    """提供注入好测试数据库的 TestClient"""
    with TestClient(app) as test_client:
        yield test_client


def test_profile_requires_authentication(client):
    response = client.get("/api/users/me")
    assert response.status_code == 401


def test_profile_returns_user_payload(client, session_factory):
    session = session_factory()
    try:
        user = User(username="tester", hashed_password=get_password_hash("secret"))
        session.add(user)
        session.commit()
    finally:
        session.close()

    login_response = client.post(
        "/api/auth/login",
        json={"username": "tester", "password": "secret"},
    )
    assert login_response.status_code == 200

    # 使用同一个客户端会自动携带 Cookie 会话
    profile_response = client.get("/api/users/me")
    assert profile_response.status_code == 200
    payload = profile_response.json()
    assert payload["username"] == "tester"
    assert payload["role"] == "user"
    assert payload["is_active"] is True
    assert payload["theme_name"]
