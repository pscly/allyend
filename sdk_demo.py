"""
SDK 使用示例（中文注释，UTF-8 无 BOM）

功能演示：
- 创建 `AsyncCrawlerClient`（异步不阻塞主线程）
- 注册爬虫 → 启动一次运行（run）
- 上报日志、心跳，并演示获取/回执远程指令
- 可选启动后台指令任务（asyncio，不阻塞）

运行前提：
- 需要安装依赖：`pip install httpx`（仓库依赖已在 pyproject 中声明）
- 服务默认监听在 `.env` 中的 `PORT=9093`，示例默认使用 `http://localhost:9093`
- 需要服务端颁发的 API Key（HTTP 头：`X-API-Key`），以环境变量或命令行传入

使用示例：
    # 环境变量方式
    $env:SDK_API_KEY = "<你的APIKey>"
    python sdk_demo.py --name demo_sdk --loop 3

    # 命令行参数方式
    python sdk_demo.py --base-url http://localhost:9093 --api-key <你的APIKey> --loop 5 --run-worker
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import asyncio
from typing import Any, Dict, Optional

try:
    from sdk.crawler_client import AsyncCrawlerClient
except Exception as exc:  # 兜底提示
    print("无法导入 sdk.crawler_client，请确认当前目录下存在 sdk/crawler_client.py 并使用 Python 3.8+ 运行。")
    print("错误信息:", exc)
    sys.exit(2)


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="Crawler SDK 示例")
    parser.add_argument(
        "--base-url",
        default=os.getenv("SDK_BASE_URL", os.getenv("BASE_URL", "http://localhost:9093")),
        help="服务基地址（不需要带 /pa/api）",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("SDK_API_KEY", os.getenv("API_KEY")),
        help="服务端颁发的 API Key（亦可用环境变量 SDK_API_KEY / API_KEY）",
    )
    parser.add_argument("--name", default="sdk_demo", help="爬虫名称（用于服务端注册标识）")
    parser.add_argument(
        "--loop",
        type=int,
        default=3,
        help="心跳循环次数（>0 时演示循环心跳；=0 表示不循环）",
    )
    parser.add_argument("--interval", type=float, default=3.0, help="心跳/指令轮询间隔秒数")
    parser.add_argument(
        "--run-worker",
        action="store_true",
        help="启动后台指令线程（自动轮询远程指令并按默认规则回执）",
    )
    parser.add_argument(
        "--capture-print",
        action="store_true",
        help="演示将 print 输出同步到服务端日志（with 上下文）",
    )
    return parser


async def main() -> int:
    args = build_parser().parse_args()

    base_url = str(args.base_url).strip()
    api_key = (args.api_key or "").strip()
    name = str(args.name).strip() or "sdk_demo"
    loop_times = int(args.loop or 0)
    interval = max(1.0, float(args.interval or 3.0))

    if not api_key:
        print("缺少 API Key，请通过 --api-key 或环境变量 SDK_API_KEY / API_KEY 传入。")
        return 2

    # 创建客户端（会自动将 base_url 规范为 {base}/pa/api）
    client = AsyncCrawlerClient(base_url=base_url, api_key=api_key)

    try:
        # 1) 注册爬虫
        crawler: Dict[str, Any] = await client.register_crawler(name)
        crawler_id = int(crawler.get("id"))
        print(f"已注册爬虫：id={crawler_id}, name={crawler.get('name')}")

        # 2) 启动一次运行（run）
        run: Dict[str, Any] = await client.start_run(crawler_id=crawler_id)
        run_id = int(run.get("id"))
        print(f"已启动运行：run_id={run_id}")

        # 3) 演示：日志上报 & 可选 capture_print
        if args.capture_print:
            with client.capture_print(crawler_id=crawler_id, run_id=run_id, default_level="INFO", mirror=True):
                print("这是一条会同步到服务端日志的 print 输出。")
                print("你也可以通过 level 参数覆盖日志级别。", level="WARN")
        else:
            await client.log(crawler_id=crawler_id, run_id=run_id, level="INFO", message="SDK 示例启动完成")

        # 4) 可选：启动后台指令线程（处理 restart / shutdown / run_shell 等演示）
        if args.run_worker:
            client.start_command_worker(crawler_id=crawler_id, interval_seconds=interval)
            print("已启动后台指令任务（asyncio），支持 restart / shutdown / run_shell / pause / resume / switch_task 等指令。")

        # 5) 心跳与远程指令演示
        if loop_times > 0:
            for i in range(1, loop_times + 1):
                hb = await client.heartbeat(
                    crawler_id=crawler_id,
                    status="running",
                    payload={"loop": i, "note": "hello from sdk_demo"},
                )
                print(f"心跳[{i}/{loop_times}] 回执：{hb}")

                # 主动获取一次远程指令并回执（若启用后台任务，这里可略）
                cmds = await client.fetch_commands(crawler_id=crawler_id)
                if cmds:
                    print(f"收到远程指令 {len(cmds)} 条，逐条回执…")
                for cmd in cmds:
                    await client.ack_command(
                        crawler_id=crawler_id,
                        command_id=int(cmd["id"]),
                        status="success",
                        result={"handled_by": "sdk_demo"},
                    )

                await asyncio.sleep(interval)
        else:
            # 仅演示一次心跳与一次指令获取
            hb = await client.heartbeat(crawler_id=crawler_id, status="idle", payload={"demo": True})
            print(f"心跳回执：{hb}")
            cmds = await client.fetch_commands(crawler_id=crawler_id)
            print(f"一次性获取远程指令：{len(cmds)} 条")
            for cmd in cmds:
                await client.ack_command(crawler_id=crawler_id, command_id=int(cmd["id"]), status="success", result={"handled_by": "sdk_demo"})

        # 6) 结束运行
        fin = await client.finish_run(crawler_id=crawler_id, run_id=run_id, status="success")
        print(f"运行结束：{fin}")

        return 0
    except KeyboardInterrupt:
        print("收到中断，准备退出…")
        return 1
    except Exception as exc:  # 保底错误信息
        print("示例运行失败：", exc)
        return 1
    finally:
        # 若开启了后台线程，这里确保请求停止并关闭连接
        try:
            await client.stop_command_worker()
        except Exception:
            pass
        await client.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
