import Link from "next/link";
import { ArrowRight, ShieldCheck, Cloud, Network } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="border-b border-border bg-card/70 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4">
          <Link href="/" className="font-semibold tracking-wide text-primary">
            AllYend
          </Link>
          <nav className="flex items-center gap-4 text-sm text-muted-foreground">
            <Link href="/dashboard" className="hover:text-foreground">
              控制台
            </Link>
            <Link href="/public" className="hover:text-foreground">
              公开空间
            </Link>
            <Link href="/docs" className="hover:text-foreground">
              文档
            </Link>
            <Link
              href="/login"
              className={cn(buttonVariants({ variant: "default" }), "h-9 px-4 text-sm")}
            >
              立即登录
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-16">
        <section className="grid gap-12 lg:grid-cols-[3fr_2fr] lg:items-center">
          <div className="space-y-6">
            <span className="inline-flex items-center rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
              数据团队的一站式运营平台
            </span>
            <h1 className="text-4xl font-bold leading-tight text-foreground md:text-5xl">
              采集、同步、分发，一套后端搞定
            </h1>
            <p className="max-w-xl text-base leading-relaxed text-muted-foreground">
              AllYend 提供爬虫调度、文件中转、令牌审核、访问审计等核心能力，帮助数据团队快速落地前后端分离方案，同时兼顾安全、合规与可观测性。
            </p>
            <div className="flex flex-wrap gap-4">
              <Link
                href="/login"
                className={cn(buttonVariants({ size: "lg" }), "gap-2")}
              >
                进入控制台
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/docs"
                className={cn(buttonVariants({ variant: "outline", size: "lg" }))}
              >
                查看接入指南
              </Link>
            </div>
          </div>
          <div className="grid gap-4 rounded-2xl border border-border bg-card p-6 shadow-surface">
            <FeatureCard
              icon={<ShieldCheck className="h-5 w-5 text-primary" />}
              title="多重安全防护"
              description="JWT、API Key、上传令牌、IP 白名单全覆盖，审计日志实时追踪。"
            />
            <FeatureCard
              icon={<Cloud className="h-5 w-5 text-primary" />}
              title="文件快传"
              description="令牌上传、分组授权、公开资源一体化，支持对象存储对接。"
            />
            <FeatureCard
              icon={<Network className="h-5 w-5 text-primary" />}
              title="爬虫调度"
              description="心跳监测、运行日志、快捷分享链接，让爬虫状态一目了然。"
            />
          </div>
        </section>
      </main>

      <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} AllYend • FastAPI + Next.js 全栈方案
      </footer>
    </div>
  );
}

interface FeatureCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
}

function FeatureCard({ icon, title, description }: FeatureCardProps) {
  return (
    <div className="rounded-xl border border-border/60 bg-background/70 p-4">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
          {icon}
        </span>
        <div>
          <p className="text-sm font-semibold text-foreground">{title}</p>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
    </div>
  );
}
