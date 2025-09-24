"""
Python SDK：便于在爬虫客户端中上报状态、心跳与远程指令回执

示例：
    from sdk.crawler_client import CrawlerClient
    client = CrawlerClient(base_url="http://localhost:9093", api_key="<你的APIKey>")

    crawler = client.register_crawler("news_spider")    # 去服务端注册
    run = client.start_run(crawler_id=crawler["id"])    # 启动一次 代表一次爬虫任务3
    client.log(crawler_id=crawler["id"], level="INFO", message="启动")   # 上报一个info 信息
    client.heartbeat(crawler_id=crawler["id"], payload={"tasks_completed": 12}) # 发送心跳包，和自定义状态(如 完成数量)
    commands = client.fetch_commands(crawler_id=crawler["id"])
    for cmd in commands:
        # 执行远程指令
        client.ack_command(crawler_id=crawler["id"], command_id=cmd["id"], status="success")


    from sdk.crawler_client import CrawlerClient
    client = CrawlerClient(base_url="http://localhost:9093", api_key="<你的APIKey>")

    


"""
from __future__ import annotations

# 中文编码要求：UTF-8，无 BOM
# 本文件为 Python SDK，面向全新项目开发，去除兼容性包袱，保持实现简洁清晰。

import builtins
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, Optional
import os
import sys
import time
import threading

import requests
try:  # 可选依赖：若可用则启用连接池重试与退避
    from urllib3.util.retry import Retry  # type: ignore
    from requests.adapters import HTTPAdapter  # type: ignore
    _HAS_RETRY = True
except Exception:  # 运行环境不具备 urllib3 Retry 时自动降级为无重试
    _HAS_RETRY = False


class CrawlerClient:
    """同步 SDK 客户端（简洁实现，默认无历史兼容逻辑）。

    特性：
    - 连接池 + 可选重试：对临时网络故障更友好
    - 上下文管理：建议使用 with 语法自动释放连接
    - API 直观：贴近服务端 REST 设计
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 10.0,
        retries: int = 2,
        backoff_factor: float = 0.3,
    ) -> None:
        # 基础配置
        self.base_url = base_url.rstrip("/")
        self.api_base = self._normalize_api_base(self.base_url)
        self.api_key = api_key
        self.timeout = float(timeout)

        # 会话与鉴权
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": self.api_key})

        # 后台指令线程控制
        self._cmd_thread: threading.Thread | None = None
        self._cmd_stop: threading.Event | None = None

        # 可选：启用简单重试（对 5xx/连接错误）
        if _HAS_RETRY and retries and retries > 0:
            self._enable_retries(retries=int(retries), backoff_factor=float(backoff_factor))

    # -------------- 生命周期管理 --------------
    def close(self) -> None:
        """关闭底层 HTTP 连接池。"""
        # 优先停止后台线程
        try:
            self.stop_command_worker()
        except Exception:
            pass
        # 关闭 HTTP 连接池
        try:
            self.session.close()
        except Exception:
            pass

    def __enter__(self) -> "CrawlerClient":  # 上下文管理：with 使用
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _enable_retries(self, retries: int, backoff_factor: float) -> None:
        """为会话适配器启用重试策略（需要 urllib3 Retry）。"""
        if not _HAS_RETRY:
            return
        retry = Retry(
            total=retries,
            connect=retries,
            read=retries,
            backoff_factor=backoff_factor,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=("HEAD", "GET", "POST", "PUT", "PATCH", "DELETE"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    @staticmethod
    def _normalize_api_base(base_url: str) -> str:
        """最简化根路径规范化：仅支持 /pa/api。

        - 若传入已以 /pa/api 结尾，则直接使用；
        - 否则在末尾追加 /pa/api。
        说明：移除历史兼容分支，保持 SDK 与后端当前设计一致。
        """
        base = base_url.rstrip("/")
        return base if base.endswith("/pa/api") else f"{base}/pa/api"

    def register_crawler(self, name: str) -> Dict[str, Any]:
        r = self.session.post(f"{self.api_base}/register", json={"name": name}, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def heartbeat(
        self,
        crawler_id: int,
        status: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if status:
            body["status"] = status
        if payload:
            body["payload"] = payload
        r = self.session.post(
            f"{self.api_base}/{crawler_id}/heartbeat",
            json=body if body else None,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def start_run(self, crawler_id: int) -> Dict[str, Any]:
        r = self.session.post(f"{self.api_base}/{crawler_id}/runs/start", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def finish_run(self, crawler_id: int, run_id: int, status: str = "success") -> Dict[str, Any]:
        r = self.session.post(
            f"{self.api_base}/{crawler_id}/runs/{run_id}/finish",
            params={"status_": status},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def fetch_commands(self, crawler_id: int) -> list[Dict[str, Any]]:
        r = self.session.post(
            f"{self.api_base}/{crawler_id}/commands/next",
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def ack_command(
        self,
        crawler_id: int,
        command_id: int,
        status: str = "success",
        result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"status": status}
        if result is not None:
            payload["result"] = result
        r = self.session.post(
            f"{self.api_base}/{crawler_id}/commands/{command_id}/ack",
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    # ---------------- 高级：远程控制辅助 ----------------

    def restart_self(self, delay_seconds: float = 0.0) -> None:
        """让当前进程重启（跨平台可靠）。

        实现说明：
        - POSIX: 直接 os.execv 覆盖当前进程镜像；
        - Windows: 以相同参数启动新进程，然后使用 os._exit(0) 退出当前进程，避免部分环境下 execv 不生效的问题。
        - 注意：调用该方法不会返回；调用前应完成必要回执与清理。
        """
        if delay_seconds and delay_seconds > 0:
            try:
                time.sleep(delay_seconds)
            except Exception:
                pass
        try:
            if os.name == "nt":  # Windows 平台
                import subprocess  # 延迟导入，避免无谓依赖
                creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
                    subprocess, "DETACHED_PROCESS", 0
                )
                subprocess.Popen(
                    [sys.executable, *sys.argv],
                    close_fds=True,
                    creationflags=creationflags,
                )
                # 立即退出当前进程，让外部监控/调用方感知重启
                os._exit(0)
            else:
                # POSIX 平台：原地覆盖
                os.execv(sys.executable, [sys.executable, *sys.argv])
        except Exception:
            # 兜底：无论如何终止当前进程，交给上游拉起
            os._exit(0)

    def shutdown_self(self, delay_seconds: float = 0.0, exit_code: int = 0) -> None:
        """平滑停机：延迟后退出当前进程。

        注意：仅负责进程退出，业务应在调用前完成资源清理。
        """
        if delay_seconds and delay_seconds > 0:
            try:
                time.sleep(delay_seconds)
            except Exception:
                pass
        # 使用 sys.exit，留给 atexit/ finally 钩子处理清理逻辑
        sys.exit(int(exit_code or 0))

    # ---------------- 本地命令执行（受控） ----------------
    def run_shell(
        self,
        command: str | list[str],
        *,
        timeout: Optional[float] = None,
        shell: Optional[bool] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        text: bool = True,
        encoding: Optional[str] = None,
    ) -> Dict[str, Any]:
        """在本机受控执行命令，返回 {code, out, err, duration}。

        安全提示：此为客户端行为，请仅在受信任环境启用相关远程指令。
        """
        import subprocess
        start = time.time()
        is_windows = os.name == "nt"
        use_shell = bool(shell) if shell is not None else (is_windows and isinstance(command, str))
        try:
            completed = subprocess.run(
                command,  # type: ignore[arg-type]
                shell=use_shell,
                check=False,
                capture_output=True,
                timeout=timeout,
                cwd=cwd,
                env=env,
                text=text,
                encoding=encoding,
            )
            duration = max(0.0, time.time() - start)
            return {
                "code": completed.returncode,
                "out": completed.stdout,
                "err": completed.stderr,
                "duration": duration,
            }
        except subprocess.TimeoutExpired as exc:
            duration = max(0.0, time.time() - start)
            return {
                "code": None,
                "out": (exc.stdout or "") if text else None,
                "err": (exc.stderr or "") + f"\n<timeout after {duration:.2f}s>",
                "duration": duration,
            }
        except Exception as exc:
            duration = max(0.0, time.time() - start)
            return {"code": None, "out": "", "err": str(exc), "duration": duration}

    def run_command_loop(
        self,
        crawler_id: int,
        interval_seconds: float = 5.0,
        handler: Optional[Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """轮询服务端远程指令并执行默认/自定义处理器。

        - 默认支持的指令：
          - restart: 回执后执行就地重启（os.execv）。
          - graceful_shutdown/shutdown: 回执后延迟退出进程（默认 0.2s）。
          - hot_update_config: 回执 success（由上层在 handler 中实现动态加载更佳）。
          - switch_task: 支持负载形如 {"task": "name"} 或指令文本 "switch_task <name>"，默认仅回执。
          - pause/resume: 仅回执，不做具体动作（推荐在自定义 handler 中落地）。
        - 可传入 handler 覆盖处理逻辑；返回值将作为回执 result。
        - 建议与 heartbeat 一起周期调用（或单独起线程）。
        """
        interval = max(1.0, float(interval_seconds or 5.0))
        while True:
            try:
                commands = self.fetch_commands(crawler_id)
                for cmd in commands:
                    name = str(cmd.get("command", "")).strip().lower()
                    result: Optional[Dict[str, Any]] = None
                    payload = cmd.get("payload") or {}
                    # 优先自定义处理
                    if handler is not None:
                        try:
                            result = handler(cmd)
                        except Exception as exc:  # 自定义处理失败，回执失败状态
                            self.ack_command(crawler_id, cmd["id"], status="failed", result={"error": str(exc)})
                            continue
                    else:
                        # 默认处理
                        if name == "restart":
                            # 先回执 "accepted"，再重启自身
                            self.ack_command(crawler_id, cmd["id"], status="accepted", result={"action": "restart"})
                            self.restart_self(delay_seconds=0.2)
                            continue  # 理论上不会到达
                        elif name in {"graceful_shutdown", "shutdown"}:
                            self.ack_command(crawler_id, cmd["id"], status="accepted", result={"action": name})
                            self.shutdown_self(delay_seconds=0.2)
                            continue
                        elif name == "hot_update_config":
                            # 默认仅回执，推荐通过自定义 handler 完成落地
                            result = {"action": name, "note": "ack-only"}
                        elif name == "run_shell":
                            # 远程命令执行：payload 约定 {cmd?: str, args?: list[str], timeout?: number, shell?: bool, cwd?: str, env?: dict}
                            payload = payload or {}
                            cmd = payload.get("cmd")
                            args = payload.get("args")
                            timeout_val = payload.get("timeout")
                            shell_flag = payload.get("shell")
                            cwd_val = payload.get("cwd")
                            env_val = payload.get("env")
                            if isinstance(args, list) and not cmd:
                                exec_cmd: Any = [str(x) for x in args]
                            else:
                                exec_cmd = str(cmd or "")
                            exec_res = self.run_shell(
                                exec_cmd,
                                timeout=float(timeout_val) if timeout_val is not None else None,
                                shell=bool(shell_flag) if shell_flag is not None else None,
                                cwd=str(cwd_val) if cwd_val else None,
                                env=env_val if isinstance(env_val, dict) else None,
                            )
                            # 简化输出，避免日志过大：截断到 16KB
                            def _truncate(s: Optional[str], limit: int = 16 * 1024) -> Optional[str]:
                                if s is None:
                                    return None
                                return s if len(s) <= limit else (s[: limit] + f"\n<trimmed {len(s)-limit} bytes>")

                            result = {
                                "action": name,
                                "code": exec_res.get("code"),
                                "out": _truncate(exec_res.get("out")),
                                "err": _truncate(exec_res.get("err")),
                                "duration": exec_res.get("duration"),
                            }
                        elif name.startswith("switch_task"):
                            task = None
                            # 支持指令文本附带参数
                            parts = str(cmd.get("command", "")).split()
                            if len(parts) >= 2:
                                task = parts[1]
                            if not task:
                                task = (payload or {}).get("task")
                            result = {"action": "switch_task", "task": task}
                        elif name in {"pause", "resume"}:
                            result = {"action": name}
                        else:
                            result = {"note": "no-op"}
                    # 正常回执成功
                    self.ack_command(crawler_id, cmd["id"], status="success", result=result)
            except KeyboardInterrupt:
                raise
            except Exception as exc:  # 轮询错误容错
                if on_error:
                    try:
                        on_error(exc)
                    except Exception:
                        pass
            finally:
                try:
                    time.sleep(interval)
                except Exception:
                    pass

    # ---------------- 线程化：远程指令后台轮询 ----------------
    def start_command_worker(
        self,
        crawler_id: int,
        interval_seconds: float = 5.0,
        handler: Optional[Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        daemon: bool = True,
    ) -> None:
        """启动后台线程循环获取并执行远程指令。

        - 单例线程：若已在运行，将先请求停止原线程再启动新线程。
        - 使用事件停止，sleep 期间也可被及时打断。
        - 参数与 run_command_loop 一致。
        """
        # 若已有线程，先停止
        if self._cmd_thread and self._cmd_thread.is_alive():
            self.stop_command_worker()

        stop_evt = threading.Event()
        self._cmd_stop = stop_evt

        def _worker() -> None:
            interval = max(1.0, float(interval_seconds or 5.0))
            while not stop_evt.is_set():
                try:
                    commands = self.fetch_commands(crawler_id)
                    for cmd in commands:
                        if stop_evt.is_set():
                            break
                        name = str(cmd.get("command", "")).strip().lower()
                        result: Optional[Dict[str, Any]] = None
                        payload = cmd.get("payload") or {}
                        if handler is not None:
                            try:
                                result = handler(cmd)
                            except Exception as exc:
                                self.ack_command(crawler_id, cmd["id"], status="failed", result={"error": str(exc)})
                                continue
                        else:
                            if name == "restart":
                                self.ack_command(crawler_id, cmd["id"], status="accepted", result={"action": "restart"})
                                self.restart_self(delay_seconds=0.2)
                                continue
                            elif name in {"graceful_shutdown", "shutdown"}:
                                self.ack_command(crawler_id, cmd["id"], status="accepted", result={"action": name})
                                self.shutdown_self(delay_seconds=0.2)
                                continue
                            elif name == "hot_update_config":
                                result = {"action": name, "note": "ack-only"}
                            elif name == "run_shell":
                                payload = payload or {}
                                cmd_text = payload.get("cmd")
                                args = payload.get("args")
                                timeout_val = payload.get("timeout")
                                shell_flag = payload.get("shell")
                                cwd_val = payload.get("cwd")
                                env_val = payload.get("env")
                                if isinstance(args, list) and not cmd_text:
                                    exec_cmd: Any = [str(x) for x in args]
                                else:
                                    exec_cmd = str(cmd_text or "")
                                exec_res = self.run_shell(
                                    exec_cmd,
                                    timeout=float(timeout_val) if timeout_val is not None else None,
                                    shell=bool(shell_flag) if shell_flag is not None else None,
                                    cwd=str(cwd_val) if cwd_val else None,
                                    env=env_val if isinstance(env_val, dict) else None,
                                )
                                def _truncate(s: Optional[str], limit: int = 16 * 1024) -> Optional[str]:
                                    if s is None:
                                        return None
                                    return s if len(s) <= limit else (s[: limit] + f"\n<trimmed {len(s)-limit} bytes>")

                                result = {
                                    "action": name,
                                    "code": exec_res.get("code"),
                                    "out": _truncate(exec_res.get("out")),
                                    "err": _truncate(exec_res.get("err")),
                                    "duration": exec_res.get("duration"),
                                }
                            elif name.startswith("switch_task"):
                                task = None
                                parts = str(cmd.get("command", "")).split()
                                if len(parts) >= 2:
                                    task = parts[1]
                                if not task:
                                    task = (payload or {}).get("task")
                                result = {"action": "switch_task", "task": task}
                            elif name in {"pause", "resume"}:
                                result = {"action": name}
                            else:
                                result = {"note": "no-op"}
                        self.ack_command(crawler_id, cmd["id"], status="success", result=result)
                except KeyboardInterrupt:
                    break
                except Exception as exc:
                    if on_error:
                        try:
                            on_error(exc)
                        except Exception:
                            pass
                finally:
                    # 使用事件等待，可被 stop 及时打断
                    stop_evt.wait(timeout=max(1.0, float(interval_seconds or 5.0)))

        t = threading.Thread(target=_worker, name=f"cmd-worker-{crawler_id}")
        t.daemon = bool(daemon)
        t.start()
        self._cmd_thread = t

    def stop_command_worker(self, timeout: float = 2.0) -> None:
        """请求停止并等待后台指令线程退出。"""
        if not self._cmd_thread:
            return
        if self._cmd_stop:
            try:
                self._cmd_stop.set()
            except Exception:
                pass
        try:
            self._cmd_thread.join(timeout=max(0.0, float(timeout)))
        except Exception:
            pass
        finally:
            self._cmd_thread = None
            self._cmd_stop = None

    def log(self, crawler_id: int, level: str | int, message: str, run_id: Optional[int] = None) -> Dict[str, Any]:
        level_value = str(level).upper() if not isinstance(level, int) else str(level)
        payload: Dict[str, Any] = {"level": level_value, "message": message}
        if run_id is not None:
            payload["run_id"] = run_id
        r = self.session.post(
            f"{self.api_base}/{crawler_id}/logs",
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
        return text.rstrip("") or text

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
