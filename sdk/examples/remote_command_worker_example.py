"""
远程指令后台线程示例（逐行中文注释）

使用说明：
- 本示例展示如何在独立线程中循环获取远程指令，并在收到指令时执行自定义处理逻辑；
- 线程化的好处：不会阻塞主业务（如爬虫抓取循环），同时可随时停止；
- 请根据你的后端服务地址与 API Key 替换 base_url 与 api_key。
- 默认内置指令（无需自定义 handler）：
  - restart：客户端先回执 accepted，然后跨平台可靠重启进程（Windows 会新起进程后退出当前进程）；
  - shutdown / graceful_shutdown：回执 accepted 后平滑退出；
  - run_shell：在客户端执行 payload 指定的命令，例如 payload={"cmd":"echo hello"} 或 {"args":["python","-V"]}；
  - hot_update_config / switch_task / pause / resume：默认仅回执，具体业务可在自定义 handler 中实现。
"""
from __future__ import annotations

# 导入标准库
import time  # 用于演示心跳与主循环的 sleep
from typing import Any, Dict, Optional  # 类型注解更清晰

# 从 SDK 导入客户端
from sdk.crawler_client import CrawlerClient  # SDK 主入口


def my_command_handler(cmd: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    自定义指令处理函数（可选）。

    约定：
    - 入参 cmd 为服务端下发的指令对象（包含 id/command/payload 等字段）；
    - 返回值将作为回执的 result 字段发送至服务端；
    - 如果抛出异常，SDK 会自动回执失败（failed）。
    """
    # 读取指令名并转为小写，便于匹配
    name = str(cmd.get("command", "")).strip().lower()
    # 提取自定义负载（如果服务端携带）
    payload = cmd.get("payload") or {}

    # 依据指令名执行不同逻辑
    if name == "ping":
        # 简单应答，回执一个 pong
        return {"reply": "pong"}
    if name == "set_rate":
        # 示例：设置抓取速率（实际可以替换为你的业务逻辑）
        rate = payload.get("rate", 1)
        # 在此处保存/应用你的速率参数...
        return {"applied_rate": rate}

    # 未识别的指令，返回 no-op 说明
    return {"note": f"unhandled command: {name}"}


def main() -> None:
    """演示完整生命周期：注册 → 启动 run → 开启指令后台线程 → 心跳 → 停止线程 → 结束 run。"""
    # 1) 创建 SDK 客户端（只需提供基础地址与 API Key）
    client = CrawlerClient(
        base_url="http://localhost:9093",  # 你的后端地址（SDK 会自动拼接 /pa/api）
        api_key="REPLACE_WITH_YOUR_API_KEY",  # 替换为你的 API Key
    )

    # 2) 注册一个爬虫（仅需提供名称，返回对象包含 id 等信息）
    crawler = client.register_crawler(name="demo_spider")

    # 3) 启动一次运行（返回 run_id，便于日志归档与统计）
    run = client.start_run(crawler_id=crawler["id"])  # type: ignore[index]

    # 4) 可选：把 print 重定向到后台日志（也可以直接调用 client.log）
    with client.capture_print(crawler_id=crawler["id"], run_id=run["id"], default_level="INFO"):
        print("运行启动...")

        # 5) 启动后台指令线程（收到指令时调用自定义处理函数）
        client.start_command_worker(
            crawler_id=crawler["id"],  # 目标爬虫 ID
            interval_seconds=3.0,       # 轮询间隔秒数
            handler=my_command_handler, # 自定义指令处理器（可选）
        )

        # 6) 主业务循环（示例中仅发送心跳并等待一段时间）
        try:
            for i in range(5):
                # 周期性心跳上报（携带业务指标）
                client.heartbeat(crawler_id=crawler["id"], payload={"tick": i})
                print("心跳发送", {"tick": i})
                time.sleep(2)
        finally:
            # 7) 停止后台线程并结束本次运行
            client.stop_command_worker()
            client.finish_run(crawler_id=crawler["id"], run_id=run["id"], status="success")
            print("运行结束。")

    # 8) 关闭客户端连接（可不显式调用，with 中会自动关闭）
    client.close()


if __name__ == "__main__":
    main()

