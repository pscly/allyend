import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import Base
from app.models import FileAPIToken, FileEntry, User
from app.routers import files


@pytest.fixture()
def session():
    """构建独立的内存数据库会话，方便针对内部工具函数做验证"""
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
        engine.dispose()


@pytest.fixture()
def user(session):
    """准备一个最小化的用户对象，供令牌相关测试复用"""
    instance = User(username='tester', hashed_password='hashed')
    session.add(instance)
    session.commit()
    return instance


def test_split_filename_parts():
    assert files._split_filename_parts('report.pdf') == ('report', '.pdf')
    assert files._split_filename_parts('archive.tar.gz') == ('archive.tar', '.gz')
    assert files._split_filename_parts('noext') == ('noext', '')
    assert files._split_filename_parts('') == ('', '')


def test_apply_duplicate_suffix():
    assert files._apply_duplicate_suffix('report.pdf', 0) == 'report.pdf'
    assert files._apply_duplicate_suffix('report.pdf', 1) == 'report-1.pdf'
    assert files._apply_duplicate_suffix('report', 2) == 'report-2'


def test_resolve_alias_target(session):
    entry = FileEntry(storage_path='objects/report.pdf', original_name='report.pdf', size_bytes=1)
    session.add(entry)
    session.commit()

    base_name, index = files._resolve_alias_target(session, 'report-2.pdf')
    assert base_name == 'report.pdf'
    assert index == 2


def test_resolve_alias_target_without_match(session):
    base_name, index = files._resolve_alias_target(session, 'ghost-1.txt')
    assert base_name == 'ghost-1.txt'
    assert index == 0


def test_generate_token_value_with_custom_candidate(session, user):
    token = files._generate_token_value(session, 'custom')
    assert token == 'up-custom'


def test_generate_token_value_rejects_duplicate(session, user):
    session.add(FileAPIToken(token='up-dup', user=user))
    session.commit()

    with pytest.raises(HTTPException) as exc:
        files._generate_token_value(session, 'dup')
    assert exc.value.status_code == 409


def test_generate_token_value_retry_on_collision(session, user, monkeypatch):
    session.add(FileAPIToken(token='up-conflict', user=user))
    session.commit()

    sequence = iter(['conflict', 'fresh'])

    def fake_token_urlsafe(length: int) -> str:
        return next(sequence)

    monkeypatch.setattr(files.secrets, 'token_urlsafe', fake_token_urlsafe)

    token = files._generate_token_value(session, None)
    assert token == 'up-fresh'
