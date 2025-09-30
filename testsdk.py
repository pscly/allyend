"""
最小化 SDK 自测脚本：更详细地打印每一步的响应，便于定位 401/403/500。

注意：
- 将 base_url 与 api_key 替换为你的内网后端与真实 Key；
- 文件编码 UTF-8（无 BOM）。
"""
from sdk.crawler_client import CrawlerClient
import time


def main():
    sdkclient = CrawlerClient(
        base_url="http://192.168.3.10:9093",
        api_key="TmSzebusbwpRCYnYnxjn1bxwxTxoyHgDjNAHvDOB5YSw6pFWnc0TBy91FHqt7eLT",
        suppress_errors=False,
    )

    print("[1] 注册...")
    try:
        crawler = sdkclient.register_crawler("四川人员住建厅_gs1")
        print("register =>", crawler)
    except Exception as e:
        print("register error:", repr(e))
        return

    cid = crawler.get("id")
    print("[2] start_run...")
    try:
        run = sdkclient.start_run(crawler_id=cid)
        print("start_run =>", run)
    except Exception as e:
        print("start_run error:", repr(e))

    print("[3] 首条日志...")
    try:
        resp = sdkclient.log(crawler_id=cid, level="INFO", message="启动")
        print("log =>", resp)
    except Exception as e:
        print("log error:", repr(e))

    print("[4] 心跳...")
    try:
        hb = sdkclient.heartbeat(crawler_id=cid, payload={"tasks_completed": 1})
        print("heartbeat =>", hb)
    except Exception as e:
        print("heartbeat error:", repr(e))

    print("[5] 循环写日志 5 次...")
    for i in range(5):
        time.sleep(1)
        try:
            a = sdkclient.log(crawler_id=cid, level="INFO", message=f"循环#{i+1}")
            print(a)
        except Exception as e:
            print("loop log error:", repr(e))


if __name__ == "__main__":
    main()
