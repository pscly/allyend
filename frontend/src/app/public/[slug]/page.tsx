import { cache } from "react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { buildApiUrl, env } from "@/lib/env";
import { cn } from "@/lib/utils";

import { CopyTextButton } from "@/features/public/copy-button";
import { PublicLogPanel } from "@/features/public/log-panel";
import type { PublicGroupCrawlerEntry, PublicLinkSummary } from "@/features/public/types";

function formatDateTime(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function statusBadge(status?: string | null) {
  if (!status) return "-";
  const normalized = status.toLowerCase();
  const labelMap: Record<string, string> = {
    online: "在线",
    warning: "预警",
    offline: "离线",
  };
  const classMap: Record<string, string> = {
    online: "bg-emerald-500/15 text-emerald-500",
    warning: "bg-amber-500/15 text-amber-500",
    offline: "bg-rose-500/15 text-rose-500",
  };
  return (
    <span className={cn(
      "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
      classMap[normalized] ?? "bg-slate-500/15 text-slate-500",
    )}>
      {labelMap[normalized] ?? status}
    </span>
  );
}

const fetchSummary = cache(async (slug: string): Promise<PublicLinkSummary | null> => {
  const response = await fetch(buildApiUrl(`/pa/${slug}/api`), {
    next: { revalidate: 60 },
    cache: "no-store",
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`无法加载公开链接 ${slug}`);
  }
  return response.json();
});

interface PublicPageProps {
  params: { slug: string };
}

export async function generateMetadata({ params }: PublicPageProps): Promise<Metadata> {
  const slug = params.slug;
  try {
    const summary = await fetchSummary(slug);
    if (!summary) {
      return { title: `公开资源 ${slug}` };
    }
    const typeLabel = summary.type === "crawler" ? "爬虫" : summary.type === "api_key" ? "API Key" : "分组";
    const baseTitle = summary.name?.trim() || slug;
    return { title: `${baseTitle} · 公开${typeLabel}` };
  } catch (error) {
    console.error("generateMetadata", error);
    return { title: `公开资源 ${slug}` };
  }
}

function buildDetailItems(summary: PublicLinkSummary) {
  const baseItems = [
    { label: "类型", value: summary.type === "crawler" ? "爬虫" : summary.type === "api_key" ? "API Key" : "分组" },
    { label: "公开说明", value: summary.link_description || "未填写" },
    { label: "创建时间", value: formatDateTime(summary.link_created_at) },
    { label: "日志开放", value: summary.allow_logs ? "已开放" : "已关闭" },
  ];
  if (summary.owner_name) {
    baseItems.push({ label: "归属", value: summary.owner_name });
  }
  if (summary.type === "crawler") {
    baseItems.push(
      { label: "内部 ID", value: summary.local_id ?? summary.crawler_id },
      { label: "当前状态", value: statusBadge(summary.status) },
      { label: "最后心跳", value: formatDateTime(summary.last_heartbeat) },
      { label: "来源 IP", value: summary.last_source_ip || "-" },
    );
  } else if (summary.type === "api_key") {
    baseItems.push(
      { label: "内部 ID", value: summary.local_id ?? summary.api_key_id },
      { label: "最后使用时间", value: formatDateTime(summary.last_used_at) },
      { label: "来源 IP", value: summary.last_used_ip || "-" },
      {
        label: "关联爬虫",
        value: summary.crawler_name ? (
          <span className="inline-flex items-center gap-2">
            {summary.crawler_name}
            {statusBadge(summary.crawler_status)}
          </span>
        ) : (
          "-"
        ),
      },
    );
  } else {
    baseItems.push(
      { label: "成员总数", value: summary.crawler_total },
      {
        label: "状态统计",
        value: (
          <div className="flex flex-wrap items-center gap-2">
            {Object.entries(summary.status_breakdown ?? {}).map(([key, count]) => (
              <span
                key={key}
                className="inline-flex items-center gap-1 rounded-full bg-muted/40 px-2 py-0.5 text-xs"
              >
                {statusBadge(key)}
                <span>{count}</span>
              </span>
            ))}
          </div>
        ),
      },
    );
  }
  return baseItems;
}

function renderGroupMembers(summary: PublicLinkSummary) {
  if (summary.type !== "group") return null;
  if (!summary.crawlers?.length) {
    return (
      <div className="rounded-2xl border border-border/70 bg-card/80 p-6 text-sm text-muted-foreground">
        该分组暂无公开成员。
      </div>
    );
  }
  const entries = summary.crawlers as PublicGroupCrawlerEntry[];
  return (
    <div className="rounded-2xl border border-border/70 bg-card/80">
      <div className="flex items-center justify-between border-b border-border/60 px-6 py-4">
        <h2 className="text-sm font-medium text-foreground">公开成员</h2>
        <span className="text-xs text-muted-foreground">共 {summary.crawler_total} 个爬虫</span>
      </div>
      <ScrollArea className="max-h-[320px]">
        <div className="divide-y divide-border/60">
          {entries.map((crawler) => (
            <div key={crawler.id} className="grid gap-2 px-6 py-3 md:grid-cols-4">
              <div>
                <p className="text-sm font-medium text-foreground">
                  {crawler.name || `爬虫 #${crawler.local_id ?? crawler.id}`}
                </p>
                <p className="text-xs text-muted-foreground">内部 ID：{crawler.local_id ?? crawler.id}</p>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-xs text-muted-foreground">状态</span>
                {statusBadge(crawler.status)}
              </div>
              <div className="text-sm text-muted-foreground">
                最后心跳：{formatDateTime(crawler.last_heartbeat)}
              </div>
              <div className="text-sm text-muted-foreground">
                来源 IP：{crawler.last_source_ip || "-"}
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}

export default async function PublicLinkPage({ params }: PublicPageProps) {
  const { slug } = params;
  let summary: PublicLinkSummary | null = null;
  try {
    summary = await fetchSummary(slug);
  } catch (error) {
    console.error("public slug page", error);
    throw error;
  }

  if (!summary) {
    notFound();
  }

  const detailItems = buildDetailItems(summary);
  const publicUrl = `${env.appBaseUrl.replace(/\/$/, "")}/public/${slug}`;

  return (
    <AppShell className="space-y-6" user={null}>
      <section className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold text-foreground">
            {summary.name || `公开链接 ${slug}`}
          </h1>
          <p className="text-sm text-muted-foreground">
            访问路径 <code className="rounded-md bg-muted px-1.5 py-0.5">/pa/{slug}</code>
            {summary.link_description ? ` · ${summary.link_description}` : " · 未填写说明"}
          </p>
          {summary.owner_name ? (
            <p className="text-xs text-muted-foreground">归属用户：{summary.owner_name}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" size="sm" asChild>
            <a href={`/pa/${slug}`}>后端直达</a>
          </Button>
          <CopyTextButton value={publicUrl} label="复制公开地址" />
        </div>
      </section>

      <section className="rounded-2xl border border-border/70 bg-card/80 p-6">
        <h2 className="text-sm font-medium text-foreground">基础信息</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {detailItems.map(({ label, value }) => (
            <div key={label} className="space-y-1">
              <p className="text-xs text-muted-foreground">{label}</p>
              <div className="text-sm text-foreground">{value}</div>
            </div>
          ))}
        </div>
      </section>

      {summary.type === "group" ? renderGroupMembers(summary) : null}

      <PublicLogPanel slug={slug} summary={summary} />
    </AppShell>
  );
}
