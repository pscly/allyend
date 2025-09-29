"""
进阶版 SDK 示例（UTF-8 无 BOM）

覆盖场景：
- CLI 配置（超时、重试、退避、TLS 校验、代理、.env 读取）
- 注册/运行/心跳/日志/远程指令自定义处理器
- 信号处理（Ctrl+C / SIGTERM）与优雅退出
- 可选系统指标上报（psutil 可选）
- 网络失败的本地降级日志（写入 logs/ 目录）

依赖建议：
- 必需：requests
- 可选：python-dotenv（读取 .env），psutil（系统指标）
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
import asyncio

try:
    from sdk.crawler_client import AsyncCrawlerClient
except Exception as exc:
    print("无法导入 sdk.crawler_client，请确认路径与 Python 版本。", exc)
    sys.exit(2)


def try_load_env(env_file: str = ".env") -> None:
    """尝试用 python-dotenv 加载 .env，不强制依赖。"""
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return
    try:
        load_dotenv(env_file)
    except Exception:
        pass


def parse_kv_list(items: list[str]) -> Dict[str, str]:
    """把 KEY=VALUE 列表解析为 dict。"""
    out: Dict[str, str] = {}
    for it in items:
        if "=" in it:
            k, v = it.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def safe_int(v: Any, default: int | None = None) -> Optional[int]:
    try:
        return int(v)
    except Exception:
        return default


def gather_metrics() -> Dict[str, Any]:
    """可选收集系统指标，依赖 psutil（若缺失则返回空）。"""
    try:
        import psutil  # type: ignore
        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "mem_percent": psutil.virtual_memory().percent,
            "load_avg": tuple(round(x, 2) for x in (os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0))),
        }
    except Exception:
        return {}


def fallback_log(line: str) -> None:
    """网络失败降级到本地日志文件。"""
    try:
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "sdk_demo_fallback.log").open("a", encoding="utf-8") as fp:
            fp.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + line + "\n")
    except Exception:
        pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Crawler SDK 进阶示例")
    p.add_argument("--env-file", default=os.getenv("ENV_FILE", ".env"), help=".env 文件路径（可选）")
    p.add_argument("--base-url", default=os.getenv("SDK_BASE_URL", "http://localhost:9093"), help="服务基地址")
    p.add_argument("--api-key", default=os.getenv("SDK_API_KEY", os.getenv("API_KEY")), help="API Key")
    p.add_argument("--name", default=os.getenv("SDK_NAME", "sdk_demo_advanced"), help="爬虫名称")
    p.add_argument("--timeout", type=float, default=float(os.getenv("SDK_TIMEOUT", "10")), help="请求超时秒")
    p.add_argument("--retries", type=int, default=int(os.getenv("SDK_RETRIES", "2")), help="重试次数")
    p.add_argument("--backoff", type=float, default=float(os.getenv("SDK_BACKOFF", "0.3")), help="退避因子")
    p.add_argument("--interval", type=float, default=float(os.getenv("SDK_INTERVAL", "5")), help="轮询间隔秒")
    p.add_argument("--loops", type=int, default=int(os.getenv("SDK_LOOPS", "0")), help="心跳循环次数（0=无限）")
    p.add_argument("--insecure", action="store_true", help="不校验证书（开发环境用）")
    p.add_argument("--cafile", default=os.getenv("SDK_CAFILE"), help="自定义 CA 证书文件路径")
    p.add_argument(
        "--proxy",
        action="append",
        default=[],
        help="代理 KEY=URL，示例：http=http://127.0.0.1:7890，可多次传递",
    )
    p.add_argument("--run-worker", action="store_true", help="启动后台指令线程")
    p.add_argument("--capture-print", action="store_true", help="把 print 输出同步到服务端日志")
    p.add_argument("--debug", action="store_true", help="打印调试信息")
    return p


def _build_verify(insecure: bool, cafile: Optional[str]) -> bool | str:
    if insecure:
        return False
    if cafile:
        return cafile
    return True


_stop_flag = False


def _install_signal_handlers():
    def _handler(signum, frame):
        global _stop_flag
        _stop_flag = True
    try:
        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
    except Exception:
        pass


def custom_command_handler(cli: AsyncCrawlerClient, crawler_id: int):
    """构造一个自定义的指令处理器函数，覆盖部分默认行为。"""

    async def _handler(cmd: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        name = str(cmd.get("command", "")).strip().lower()
        payload = cmd.get("payload") or {}

        if name == "echo":
            return {"echo": payload or cmd}

        if name == "sleep":
            dur = float(payload.get("seconds", 1))
            await asyncio.sleep(max(0.0, dur))
            return {"slept": dur}

        # 自定义覆盖 run_shell：限制命令白名单，避免危险命令
        if name == "run_shell":
            args = (payload or {}).get("args")
            if isinstance(args, list) and args:
                # 白名单示例：仅允许 "echo", "python --version" 类无副作用命令
                allow = {"echo", "python", "python3"}
                cmd0 = str(args[0]).lower()
                if cmd0 not in allow:
                    return {"error": f"command '{cmd0}' not allowed"}
            # 复用 SDK 内置执行（不传 shell 标志，避免注入）
            res = await cli.run_shell(args if isinstance(args, list) else ["echo", "no-args"], timeout=safe_int(payload.get("timeout")))
            return res

        # 其它指令回落到默认（返回 None 让 SDK 默认流程处理）
        return None

    return _handler


async def main() -> int:
    args = build_parser().parse_args()
    try_load_env(args.env_file)

    if not args.api_key:
        print("缺少 API Key，请通过 --api-key 或环境变量 SDK_API_KEY / API_KEY 传入。")
        return 2

    client = AsyncCrawlerClient(
        base_url=args.base_url,
        api_key=args.api_key,
        timeout=args.timeout,
        retries=args.retries,
        backoff_factor=args.backoff,
        verify=_build_verify(args.insecure, args.cafile),
        proxies=parse_kv_list(args.proxy),
    )
    _install_signal_handlers()

    crawler_id: Optional[int] = None
    run_id: Optional[int] = None

    try:
        crawler = await client.register_crawler(args.name)
        crawler_id = safe_int(crawler.get("id"))
        if args.debug:
            print("已注册：", json.dumps(crawler, ensure_ascii=False))
        if not crawler_id:
            print("注册爬虫失败：缺少 id 字段")
            return 1

        run = await client.start_run(crawler_id=crawler_id)
        run_id = safe_int(run.get("id"))
        if args.debug:
            print("已启动运行：", json.dumps(run, ensure_ascii=False))
        if not run_id:
            print("启动运行失败：缺少 run id")
            return 1

        if args.capture_print:
            with client.capture_print(crawler_id=crawler_id, run_id=run_id, default_level="INFO", mirror=True):
                print("print 输出将同步到服务端日志。")
        else:
            await client.log(crawler_id=crawler_id, run_id=run_id, level="INFO", message="advanced 示例启动")

        if args.run_worker:
            client.start_command_worker(
                crawler_id=crawler_id,
                interval_seconds=args.interval,
                handler=custom_command_handler(client, crawler_id),
            )

        loops = args.loops
        i = 0
        while True:
            if _stop_flag:
                break
            i += 1
            payload = {"seq": i, "metrics": gather_metrics()}
            try:
                hb = await client.heartbeat(crawler_id=crawler_id, status="running", payload=payload)
                if args.debug:
                    print("心跳：", json.dumps(hb, ensure_ascii=False))
            except Exception as exc:
                fallback_log(f"心跳失败：{exc}")

            # 若未启 worker，这里主动拉一次指令并回执
            if not args.run_worker:
                try:
                    cmds = await client.fetch_commands(crawler_id=crawler_id)
                    for cmd in cmds:
                        try:
                            res = await custom_command_handler(client, crawler_id)(cmd)
                            if res is None:
                                # 使用 SDK 默认回执（成功无结果）
                                await client.ack_command(crawler_id=crawler_id, command_id=int(cmd["id"]), status="success")
                            else:
                                await client.ack_command(crawler_id=crawler_id, command_id=int(cmd["id"]), status="success", result=res)
                        except Exception as e:
                            await client.ack_command(crawler_id=crawler_id, command_id=int(cmd["id"]), status="failed", result={"error": str(e)})
                except Exception as exc:
                    fallback_log(f"拉取/回执指令失败：{exc}")

            if loops > 0 and i >= loops:
                break
            await asyncio.sleep(max(1.0, args.interval))

        # 正常结束运行
        try:
            fin = await client.finish_run(crawler_id=crawler_id, run_id=run_id or 0, status="success")
            if args.debug:
                print("运行结束：", json.dumps(fin, ensure_ascii=False))
        except Exception as exc:
            fallback_log(f"结束运行失败：{exc}")

        return 0
    except KeyboardInterrupt:
        fallback_log("收到中断信号，准备退出…")
        try:
            if crawler_id and run_id:
                await client.finish_run(crawler_id=crawler_id, run_id=run_id, status="cancelled")
        except Exception:
            pass
        return 130
    except Exception as exc:
        # 常见错误兜底提示
        msg = str(exc)
        if "401" in msg or "403" in msg:
            print("鉴权失败（401/403），请检查 API Key 是否正确且未过期。")
        else:
            print("示例运行异常：", msg)
        fallback_log(f"异常：{msg}")
        try:
            if crawler_id and run_id:
                await client.finish_run(crawler_id=crawler_id, run_id=run_id, status="failed")
        except Exception:
            pass
        return 1
    finally:
        try:
            await client.stop_command_worker()
        except Exception:
            pass
        await client.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
