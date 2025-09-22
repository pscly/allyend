import Link from "next/link";

import { LandingHeader } from "@/components/layout/landing-header";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const metadata = {
  title: "开发者文档 | AllYend",
};

export default function DocsPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <LandingHeader />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10">
        <header className="mb-8 space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">开发者文档</h1>
          <p className="text-sm text-muted-foreground">
            这里涵盖接入所需的 SDK、HTTP API 概览与示例代码。项目为全新开发，已去除历史兼容逻辑，接口命名清晰、稳定。
          </p>
        </header>

        <section id="sdk" className="mb-10 space-y-4">
          <h2 className="text-xl font-semibold">SDK 下载</h2>
          <p className="text-sm text-muted-foreground">目前提供 Python SDK，源文件与 ZIP 包均可直接下载。</p>
          <div className="flex flex-wrap gap-3">
            <a
              href="/sdk/crawler_client.py"
              download
              className={cn(buttonVariants({ variant: "default" }))}
            >
              下载 Python SDK 源码
            </a>
            <a
              href="/sdk/crawler_client.zip"
              download
              className={cn(buttonVariants({ variant: "outline" }))}
            >
              下载 ZIP 包
            </a>
            <Link
              href="#quickstart"
              className={cn(buttonVariants({ variant: "ghost" }))}
            >
              查看快速开始
            </Link>
          </div>
        </section>

        <section id="quickstart" className="mb-10 space-y-4">
          <h2 className="text-xl font-semibold">快速开始（Python）</h2>
          <p className="text-sm text-muted-foreground">
            使用 with 语法自动管理连接，示例包含注册爬虫、启动/结束运行、心跳与日志上报。
          </p>
          <pre className="overflow-x-auto rounded-lg border border-border bg-muted p-4 text-xs leading-relaxed">
{`from sdk.crawler_client import CrawlerClient

BASE = "http://localhost:9093"  # 后端地址
API_KEY = "<你的APIKey>"

with CrawlerClient(BASE, API_KEY, retries=2, backoff_factor=0.3) as client:
    crawler = client.register_crawler("news_spider")
    run = client.start_run(crawler_id=crawler["id"])  # 记录一次运行
    client.log(crawler_id=crawler["id"], level="INFO", message="启动")
    client.heartbeat(crawler_id=crawler["id"], payload={"tasks_completed": 12})

    # 轮询远程指令（可在独立线程中运行）
    # client.run_command_loop(crawler_id=crawler["id"], interval_seconds=5.0)

    client.finish_run(crawler_id=crawler["id"], run_id=run["id"], status="success")
`}
          </pre>
        </section>

        <section id="api" className="mb-10 space-y-4">
          <h2 className="text-xl font-semibold">HTTP API 概览</h2>
          <p className="text-sm text-muted-foreground">
            API 基础路径以 <code className="rounded bg-muted px-1">/pa/api</code> 为准（或 <code className="rounded bg-muted px-1">/api</code>）。
          </p>
          <ul className="list-disc space-y-1 pl-6 text-sm">
            <li>POST <code className="rounded bg-muted px-1">/register</code> 注册爬虫</li>
            <li>POST <code className="rounded bg-muted px-1">/{"{crawlerId}"}/heartbeat</code> 心跳上报</li>
            <li>POST <code className="rounded bg-muted px-1">/{"{crawlerId}"}/runs/start</code> 启动运行</li>
            <li>POST <code className="rounded bg-muted px-1">/{"{crawlerId}"}/runs/{"{runId}"}/finish</code> 结束运行</li>
            <li>POST <code className="rounded bg-muted px-1">/{"{crawlerId}"}/commands/next</code> 拉取远程指令</li>
            <li>POST <code className="rounded bg-muted px-1">/{"{crawlerId}"}/commands/{"{commandId}"}/ack</code> 指令回执</li>
            <li>POST <code className="rounded bg-muted px-1">/{"{crawlerId}"}/logs</code> 运行日志</li>
          </ul>
        </section>

        <section id="curl" className="mb-10 space-y-4">
          <h2 className="text-xl font-semibold">示例（cURL）</h2>
          <pre className="overflow-x-auto rounded-lg border border-border bg-muted p-4 text-xs leading-relaxed">
{`BASE="http://localhost:9093/pa/api"
API_KEY="<你的APIKey>"

curl -sS -X POST "$BASE/register" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"news_spider"}'
`}
          </pre>
        </section>
      </main>
    </div>
  );
}
