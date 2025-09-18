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

    # 可选：将 print 输出同步到平台日志
    printer = client.printer(crawler_id=c["id"], run_id=run["id"], default_level="INFO")
    printer("爬虫启动完成", level="INFO")

    # 或通过上下文管理器临时替换 print
    with client.capture_print(crawler_id=c["id"], run_id=run["id"], default_level="INFO"):
        print("这条信息会记录到平台", level="WARNING")
"""
from __future__ import annotations

import builtins
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, Optional

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

    def log(self, crawler_id: int, level: str | int, message: str, run_id: Optional[int] = None) -> Dict[str, Any]:
        level_value = str(level).upper() if not isinstance(level, int) else str(level)
        payload: Dict[str, Any] = {"level": level_value, "message": message}
        if run_id is not None:
            payload["run_id"] = run_id
        r = self.session.post(
            f"{self.base_url}/api/crawlers/{crawler_id}/logs",
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _compose_message(args: tuple[Any, ...], kwargs: Dict[str, Any]) -> str:
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "")
        text = sep.join(str(arg) for arg in args)
        if end:
            text += end
        return text.rstrip("\n") or text

    def printer(
        self,
        crawler_id: int,
        run_id: Optional[int] = None,
        default_level: str | int = "INFO",
        mirror: bool = True,
        _mirror_func: Callable[..., None] | None = builtins.print,
    ) -> Callable[..., None]:
        """返回一个可代替 print 的函数，自动写入日志。"""

        def _printer(*args: Any, **kwargs: Any) -> None:
            level_override = kwargs.pop("level", None)
            mirror_override = kwargs.pop("mirror", mirror)
            message = self._compose_message(args, kwargs)
            level_value = level_override if level_override is not None else default_level
            self.log(crawler_id=crawler_id, level=level_value, message=message, run_id=run_id)
            if mirror_override and _mirror_func is not None:
                _mirror_func(*args, **kwargs)

        return _printer

    @contextmanager
    def capture_print(
        self,
        crawler_id: int,
        run_id: Optional[int] = None,
        default_level: str | int = "INFO",
        mirror: bool = True,
    ) -> Iterator[None]:
        """上下文管理器：在 with 块内将 print 自动同步到后台日志。"""

        original_print = builtins.print
        printer = self.printer(
            crawler_id,
            run_id=run_id,
            default_level=default_level,
            mirror=mirror,
            _mirror_func=original_print,
        )

        def patched_print(*args: Any, **kwargs: Any) -> None:
            printer(*args, **kwargs)

        builtins.print = patched_print
        try:
            yield
        finally:
            builtins.print = original_print
