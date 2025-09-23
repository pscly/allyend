"""
一次性数据清理脚本：清理未绑定 API Key 的“孤儿”爬虫记录。

使用方式（在项目根目录执行）：
  uv run scripts/cleanup_orphan_crawlers.py           # 仅查看将要删除的记录（dry-run）
  uv run scripts/cleanup_orphan_crawlers.py --apply   # 实际执行删除

说明：
- 仅删除 crawlers 表中 api_key_id 为空的记录；相关 runs/logs 会级联删除（ORM 关系已配置）。
- 请在执行前备份数据库（默认 SQLite 位于 data/app.db）。
"""
from __future__ import annotations

import argparse
from typing import List

from app.database import SessionLocal
from app.models import Crawler


def main() -> None:
    parser = argparse.ArgumentParser(description="清理未绑定 API Key 的爬虫")
    parser.add_argument("--apply", action="store_true", help="执行删除（默认仅预览）")
    args = parser.parse_args()

    with SessionLocal() as session:
        orphans: List[Crawler] = (
            session.query(Crawler).filter(Crawler.api_key_id == None).all()  # noqa: E711
        )
        if not orphans:
            print("未找到需要清理的孤儿爬虫记录，数据库已干净。")
            return

        print(f"发现 {len(orphans)} 条孤儿爬虫记录（api_key_id IS NULL）：")
        for c in orphans:
            print(f"- Crawler(id={c.id}, local_id={c.local_id}, name={c.name!r}, user_id={c.user_id})")

        if not args.apply:
            print("\n预览结束：未执行删除。若要实际清理，请加 --apply 参数。")
            return

        # 级联删除 runs/logs 在 ORM 关系上已配置 cascade；直接删除爬虫即可
        for c in orphans:
            session.delete(c)
        session.commit()
        print(f"已删除 {len(orphans)} 条孤儿爬虫记录。")


if __name__ == "__main__":
    main()

