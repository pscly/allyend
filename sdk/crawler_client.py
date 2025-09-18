"""
Python SDK：便于在爬虫工具中上报状态/日志

示例：
    from sdk.crawler_client import CrawlerClient
    client = CrawlerClient(base_url="http://localhost:9093", api_key="<你的APIKey>")
    c = client.register_crawler("news_spider")
    run = client.start_run(crawler_id=c["id"])
    client.log(crawler_id=c["id"], level="INFO", message="启动")
    client.heartbeat(crawler_id=c["id"])
    client.finish_run(crawler_id=c["id"], run_id=run["id"], status="success")
"""
from __future__ import annotations

from typing import Any, Dict, Optional
import requests


class CrawlerClient:
    """简单同步客户端"""

    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": self.api_key})
        self.timeout = timeout

    def register_crawler(self, name: str) -> Dict[str, Any]:
        r = self.session.post(f"{self.base_url}/api/crawlers/register", json={"name": name}, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def heartbeat(self, crawler_id: int) -> Dict[str, Any]:
        r = self.session.post(f"{self.base_url}/api/crawlers/{crawler_id}/heartbeat", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def start_run(self, crawler_id: int) -> Dict[str, Any]:
        r = self.session.post(f"{self.base_url}/api/crawlers/{crawler_id}/runs/start", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def finish_run(self, crawler_id: int, run_id: int, status: str = "success") -> Dict[str, Any]:
        r = self.session.post(
            f"{self.base_url}/api/crawlers/{crawler_id}/runs/{run_id}/finish",
            params={"status_": status},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def log(self, crawler_id: int, level: str, message: str, run_id: Optional[int] = None) -> Dict[str, Any]:
        payload = {"level": level, "message": message}
        if run_id is not None:
            payload["run_id"] = run_id
        r = self.session.post(f"{self.base_url}/api/crawlers/{crawler_id}/logs", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

