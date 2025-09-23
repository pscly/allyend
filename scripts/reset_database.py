"""
开发期重置数据库脚本：删除 SQLite 文件并按当前 ORM 结构重建，再写入默认数据。

用法（项目根目录）：
  uv run scripts/reset_database.py --yes   # 无确认直接执行

注意：该脚本仅针对 SQLite。其他数据库请自行清理后运行应用。
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.config import settings
from app.database import ensure_database_schema
from app.database import bootstrap_defaults


def _sqlite_path(url: str) -> Path | None:
    if not url.startswith("sqlite"):
        return None
    return Path(url.replace("sqlite:///", "")).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description="重置数据库（仅 SQLite）")
    parser.add_argument("--yes", action="store_true", help="跳过交互确认，直接执行")
    args = parser.parse_args()

    db_path = _sqlite_path(settings.DATABASE_URL)
    if db_path is None:
        print(f"当前数据库不是 SQLite（{settings.DATABASE_URL}），请手动清理后再运行应用。")
        return

    if not args.yes:
        ans = input(f"将删除数据库文件 {db_path} 并重建，确认执行？(yes/NO) ")
        if ans.strip().lower() != "yes":
            print("已取消。")
            return

    if db_path.exists():
        os.remove(db_path)
        print(f"已删除：{db_path}")
    else:
        print(f"数据库文件不存在：{db_path}，将直接创建新库。")

    ensure_database_schema()
    bootstrap_defaults()
    print("数据库已重建并写入默认数据。")


if __name__ == "__main__":
    main()

