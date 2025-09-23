"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { AlertTriangle, ChevronLeft, Copy, Loader2, PlayCircle, RefreshCcw, Send, Shield, ShieldOff, TriangleAlert, Maximize2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { CrawlerStatusBadge } from "@/features/crawlers/components/status-badge";
import { HeartbeatChart } from "@/features/crawlers/components/heartbeat-chart";
import { copyToClipboard } from "@/lib/clipboard";
import { env } from "@/lib/env";
import {
  useCrawlerDetailQuery,
  useCrawlerHeartbeatsQuery,
  useCrawlerLogsQuery,
  useCrawlerCommandsQuery,
  useCrawlerConfigFetchQuery,
  type HeartbeatQueryOptions,
} from "@/features/crawlers/queries";
import { useCreateCrawlerCommandMutation, useUpdateCrawlerMutation } from "@/features/crawlers/mutations";
import type { CrawlerSummary, CrawlerHeartbeat, CrawlerLog, CrawlerCommand } from "@/lib/api/types";

function formatRelative(value?: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  if (isNaN(d.getTime())) return "—";
  const diff = Date.now() - d.getTime();
  const min = 60_000;
  const hr = 60 * min;
  const day = 24 * hr;
  if (Math.abs(diff) < min) return diff >= 0 ? "刚刚" : "即将";
  if (Math.abs(diff) < hr) return `${Math.round(Math.abs(diff) / min)} 分钟${diff >= 0 ? "前" : "后"}`;
  if (Math.abs(diff) < day) return `${Math.round(Math.abs(diff) / hr)} 小时${diff >= 0 ? "前" : "后"}`;
  return `${Math.round(Math.abs(diff) / day)} 天${diff >= 0 ? "前" : "后"}`;
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  if (isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(d);
}

function formatUptime(ratio?: number | null) {
  if (ratio === undefined || ratio === null) return "—";
  const r = Math.max(0, Math.min(1, ratio)) * 100;
  return `${r.toFixed(1)}%`;
}

function extractMetrics(payload: Record<string, unknown> | null | undefined) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return [] as Array<{ key: string; value: string }>;
  return Object.entries(payload)
    .filter(([_, v]) => (typeof v === "number" && Number.isFinite(v)) || (typeof v === "string" && v.length > 0 && v.length <= 40))
    .slice(0, 6)
    .map(([k, v]) => ({ key: k, value: String(v) }));
}

type HeartbeatRange = "1h" | "12h" | "1d" | "7d" | "all";

const HEARTBEAT_RANGE_OPTIONS: Array<{ value: HeartbeatRange; label: string }> = [
  { value: "1h", label: "1小时" },
  { value: "12h", label: "12小时" },
  { value: "1d", label: "24小时" },
  { value: "7d", label: "7天" },
  { value: "all", label: "全部" },
];

const HEARTBEAT_RANGE_DURATION: Record<HeartbeatRange, number | null> = {
  "1h": 60 * 60 * 1000,
  "12h": 12 * 60 * 60 * 1000,
  "1d": 24 * 60 * 60 * 1000,
  "7d": 7 * 24 * 60 * 60 * 1000,
  all: null,
};

export default function CrawlerDetailPage() {
  const router = useRouter();
  const params = useParams<{ crawlerId?: string }>();
  const { toast } = useToast();

  const idRaw = params?.crawlerId ?? "";
  const crawlerId = Number(idRaw);
  const validId = Number.isFinite(crawlerId) && crawlerId > 0;

  const [heartbeatRange, setHeartbeatRange] = useState<HeartbeatRange>("12h");
  const [selectedMetric, setSelectedMetric] = useState<string>("__status");
  // 放大查看对话框开关
  const [openHb, setOpenHb] = useState(false);
  const [openLogs, setOpenLogs] = useState(false);
  const [openCmds, setOpenCmds] = useState(false);
  const [openCfg, setOpenCfg] = useState(false);

  const detailQuery = useCrawlerDetailQuery(validId ? crawlerId : 0, validId);
  const heartbeatQueryOptions = useMemo<HeartbeatQueryOptions>(() => {
    if (!validId) {
      return { enabled: false };
    }
    const duration = HEARTBEAT_RANGE_DURATION[heartbeatRange];
    const now = Date.now();
    const start = typeof duration === "number" ? new Date(now - duration).toISOString() : undefined;
    const end = typeof duration === "number" ? new Date(now).toISOString() : undefined;
    const limit =
      heartbeatRange === "7d"
        ? 4000
        : heartbeatRange === "1d"
          ? 2400
          : heartbeatRange === "12h"
            ? 1600
            : heartbeatRange === "1h"
              ? 800
              : 600;
    const maxPoints =
      heartbeatRange === "7d"
        ? 600
        : heartbeatRange === "1d"
          ? 500
          : heartbeatRange === "12h"
            ? 400
            : heartbeatRange === "1h"
              ? 320
              : 600;
    return {
      limit,
      start,
      end,
      maxPoints,
      enabled: true,
    };
  }, [heartbeatRange, validId]);
  const hbQuery = useCrawlerHeartbeatsQuery(validId ? crawlerId : 0, heartbeatQueryOptions);
  const logQuery = useCrawlerLogsQuery(validId ? crawlerId : 0, 80, validId);
  const cmdQuery = useCrawlerCommandsQuery(validId ? crawlerId : 0, true, validId, { limit: 200, refetchInterval: 12_000 });
  const cfgQuery = useCrawlerConfigFetchQuery(validId ? crawlerId : 0, validId);

  const updateCrawler = useUpdateCrawlerMutation(validId ? crawlerId : 0);
  const createCommand = useCreateCrawlerCommandMutation(validId ? crawlerId : 0);

  const crawler: CrawlerSummary | undefined = detailQuery.data;
  const metrics = useMemo(() => extractMetrics(crawler?.heartbeat_payload), [crawler?.heartbeat_payload]);

  const metricCandidates = useMemo(() => {
    const keys = new Set<string>();
    const hbList: CrawlerHeartbeat[] = hbQuery.data ?? [];
    hbList.forEach((hb) => {
      if (hb.payload && typeof hb.payload === "object") {
        Object.entries(hb.payload).forEach(([key, value]) => {
          if (typeof value === "number" && Number.isFinite(value)) {
            keys.add(key);
          } else if (typeof value === "string" && value.length > 0 && value.length <= 64) {
            const num = Number(value);
            if (Number.isFinite(num)) {
              keys.add(key);
            }
          }
        });
      }
    });
    return Array.from(keys).sort((a, b) => a.localeCompare(b));
  }, [hbQuery.data]);

  useEffect(() => {
    if (selectedMetric === "__status") return;
    if (!metricCandidates.includes(selectedMetric)) {
      setSelectedMetric(metricCandidates[0] ?? "__status");
    }
  }, [metricCandidates, selectedMetric]);

  const [customCmd, setCustomCmd] = useState("");
  const [sending, setSending] = useState(false);

  if (!validId) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <TriangleAlert className="h-4 w-4" /> 未找到合法的爬虫编号。
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link href="/dashboard/crawlers">返回列表</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" asChild>
            <Link href="/dashboard/crawlers"><ChevronLeft className="h-4 w-4" /> 返回</Link>
          </Button>
          {crawler ? (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <CrawlerStatusBadge status={crawler.status} />
                <span className="text-xs text-muted-foreground">#{crawler.local_id}</span>
              </div>
              <h1 className="text-xl font-semibold text-foreground">{crawler.name}</h1>
              <p className="text-xs text-muted-foreground">
                分组：{crawler.group?.name ?? "未分组"} · Key：{crawler.api_key_name}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-4 w-72" />
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => detailQuery.refetch()}
            disabled={detailQuery.isFetching}
          >
            {detailQuery.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
          </Button>
          {crawler ? (
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                try {
                  await updateCrawler.mutateAsync({ is_public: !crawler.is_public });
                  toast({ title: crawler.is_public ? "已取消公开" : "已设为公开", description: crawler.name });
                } catch (e) {
                  toast({ title: "操作失败", description: "更新公开状态失败", variant: "destructive" });
                }
              }}
            >
              {crawler.is_public ? <ShieldOff className="mr-2 h-4 w-4" /> : <Shield className="mr-2 h-4 w-4" />} {crawler.is_public ? "关闭公开" : "设为公开"}
            </Button>
          ) : null}
        </div>
      </div>

      {/* 概览卡片 */}
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Stat label="最后心跳" value={`${formatRelative(crawler?.last_heartbeat)} · ${formatDate(crawler?.last_heartbeat)}`} />
        <Stat label="最后来源 IP" value={crawler?.last_source_ip ?? "未知"} />
        <Stat label="可用性" value={formatUptime(crawler?.uptime_ratio)} />
        <Stat label="心跳状态变更" value={crawler?.status_changed_at ? formatRelative(crawler?.status_changed_at) : "—"} />
      </section>

      {/* 指标+公开地址 */}
      <section className="grid gap-4 xl:grid-cols-3">
        <div className="space-y-3 rounded-2xl border border-border/70 bg-card/80 p-4 xl:col-span-2">
          <h2 className="text-sm font-medium text-foreground">最新指标</h2>
          {metrics.length ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {metrics.map((m) => (
                <div key={m.key} className="rounded-xl border border-border/60 bg-background/60 px-3 py-2 text-sm">
                  <p className="text-muted-foreground">{m.key}</p>
                  <p className="mt-1 font-medium text-foreground">{m.value}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">无附带指标。可以在心跳 payload 中上报业务数据。</p>
          )}
        </div>
        <div className="space-y-3 rounded-2xl border border-border/70 bg-card/80 p-4">
          <h2 className="text-sm font-medium text-foreground">公开与访问</h2>
          {crawler?.public_slug ? (
            (() => {
              const origin = typeof window !== "undefined" ? window.location.origin : env.appBaseUrl;
              const publicUrl = `${origin}/pa/${crawler.public_slug}`;
              return (
                <div className="flex items-center justify-between gap-2 rounded-xl border border-emerald-500/50 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-600">
                  <a href={publicUrl} target="_blank" rel="noreferrer" className="truncate underline-offset-2 hover:underline">
                    {publicUrl}
                  </a>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() =>
                      copyToClipboard(publicUrl)
                        .then((ok) => ok && toast({ title: "已复制公开地址" }))
                        .catch(() => undefined)
                    }
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              );
            })()
          ) : (
            <p className="text-xs text-muted-foreground">未生成公开页。可在列表页使用“创建公开页”。</p>
          )}
        </div>
      </section>

      {/* 心跳/日志/指令/配置 */}
      <section className="grid gap-4 xl:grid-cols-2">
        <div className="space-y-4 rounded-2xl border border-border/70 bg-card/80 p-4">
          <header className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-medium text-foreground">心跳记录</h2>
              <div className="flex items-center gap-1">
                {HEARTBEAT_RANGE_OPTIONS.map((option) => (
                  <Button
                    key={option.value}
                    variant={heartbeatRange === option.value ? "default" : "outline"}
                    size="sm"
                    className="px-2"
                    onClick={() => setHeartbeatRange(option.value)}
                  >
                    {option.label}
                  </Button>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" className="gap-1" onClick={() => setOpenHb(true)}>
                <Maximize2 className="h-4 w-4" /> 放大
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm">
                    {selectedMetric === "__status" ? "仅显示状态" : `指标：${selectedMetric}`}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onSelect={() => setSelectedMetric("__status")}>
                    仅显示状态
                  </DropdownMenuItem>
                  {metricCandidates.length ? (
                    metricCandidates.map((key) => (
                      <DropdownMenuItem key={key} onSelect={() => setSelectedMetric(key)}>
                        {key}
                      </DropdownMenuItem>
                    ))
                  ) : (
                    <DropdownMenuItem disabled>暂无数值指标</DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
              <Button
                variant="outline"
                size="sm"
                onClick={() => hbQuery.refetch()}
                disabled={hbQuery.isFetching}
              >
                {hbQuery.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
              </Button>
            </div>
          </header>
          <HeartbeatChart
            data={(hbQuery.data ?? []) as CrawlerHeartbeat[]}
            metricKey={selectedMetric}
            loading={hbQuery.isLoading || hbQuery.isFetching}
          />
          {((hbQuery.data ?? []) as CrawlerHeartbeat[]).length ? (
            <div className="rounded-xl border border-border/60">
              <ScrollArea className="h-[220px]">
                <div className="min-w-full divide-y divide-border/60">
                  {((hbQuery.data ?? []) as CrawlerHeartbeat[]).slice().reverse().map((hb) => (
                    <div key={hb.id} className="flex items-center justify-between px-3 py-2 text-xs">
                      <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${hb.status === "online" ? "bg-emerald-500" : hb.status === "warning" ? "bg-amber-500" : "bg-rose-500"}`} />
                        <span className="text-foreground">{hb.status}</span>
                      </div>
                      <div className="text-muted-foreground">{hb.source_ip ?? "-"}</div>
                      <div className="text-muted-foreground">{new Date(hb.created_at).toLocaleString("zh-CN", { hour12: false })}</div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>
          ) : null}
        </div>

        <div className="space-y-3 rounded-2xl border border-border/70 bg-card/80 p-4">
          <header className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-foreground">运行日志</h2>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" className="gap-1" onClick={() => setOpenLogs(true)}>
                <Maximize2 className="h-4 w-4" /> 放大
              </Button>
              <Button variant="outline" size="sm" onClick={() => logQuery.refetch()} disabled={logQuery.isFetching}>
                {logQuery.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
              </Button>
            </div>
          </header>
          <ScrollArea className="h-[280px] rounded-xl border border-border/60">
            <div className="min-w-full divide-y divide-border/60">
              {((logQuery.data ?? []) as CrawlerLog[]).map((log) => (
                <div key={log.id} className="flex items-center justify-between px-3 py-2 text-xs">
                  <span className="font-medium text-foreground">{log.level}</span>
                  <span className="mx-3 flex-1 truncate text-foreground">{log.message}</span>
                  <span className="text-muted-foreground">{new Date(log.ts).toLocaleString("zh-CN", { hour12: false })}</span>
                </div>
              ))}
              {!((logQuery.data ?? []) as CrawlerLog[]).length ? (
                <div className="flex h-[220px] items-center justify-center gap-2 text-sm text-muted-foreground">
                  <AlertTriangle className="h-4 w-4" /> 暂无日志
                </div>
              ) : null}
            </div>
          </ScrollArea>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="space-y-4 rounded-2xl border border-border/70 bg-card/80 p-4">
          <header className="space-y-1">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-medium text-foreground">远程指令</h2>
                <p className="text-xs text-muted-foreground">爬虫在下次心跳时拉取待执行指令并回执结果。</p>
              </div>
              <Button variant="outline" size="sm" className="gap-1" onClick={() => setOpenCmds(true)}>
                <Maximize2 className="h-4 w-4" /> 放大
              </Button>
            </div>
          </header>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => sendQuickCommand("pause")}>暂停</Button>
            <Button size="sm" onClick={() => sendQuickCommand("resume")}>恢复</Button>
            <Button size="sm" onClick={() => sendQuickCommand("restart")} className="gap-1">
              <PlayCircle className="h-4 w-4" /> 重启
            </Button>
            <Button size="sm" variant="secondary" onClick={() => sendQuickCommand("hot_update_config")}>热更新配置</Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                const task = typeof window !== "undefined" ? window.prompt("输入要切换的任务标识（task）:") : "";
                if (task && task.trim()) {
                  sendCommand(`switch_task ${task.trim()}`);
                }
              }}
            >
              切换任务
            </Button>
            <Button size="sm" variant="destructive" onClick={() => sendQuickCommand("graceful_shutdown")}>
              平滑停机
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Input value={customCmd} onChange={(e) => setCustomCmd(e.target.value)} placeholder="自定义指令，如: set_rate 2.0" />
            <Button size="sm" disabled={!customCmd || sending} onClick={() => sendCommand(customCmd)}>
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} 发送
            </Button>
          </div>
          <div className="rounded-xl border border-border/60">
            <div className="flex items-center justify-between border-b border-border/60 px-3 py-2 text-xs text-muted-foreground">
              <span>指令历史</span>
              <Button variant="ghost" size="sm" onClick={() => cmdQuery.refetch()} disabled={cmdQuery.isFetching}>
                {cmdQuery.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
              </Button>
            </div>
            <ScrollArea className="h-[220px]">
              <div className="min-w-full divide-y divide-border/60">
                {((cmdQuery.data ?? []) as CrawlerCommand[]).map((cmd) => (
                  <div key={cmd.id} className="grid grid-cols-12 items-center gap-2 px-3 py-2 text-xs">
                    <div className="col-span-3 truncate text-foreground">{cmd.command}</div>
                    <div className="col-span-2 text-muted-foreground">{cmd.status}</div>
                    <div className="col-span-4 truncate text-muted-foreground">{cmd.result ? JSON.stringify(cmd.result) : "—"}</div>
                    <div className="col-span-3 text-muted-foreground">{new Date(cmd.created_at).toLocaleString("zh-CN", { hour12: false })}</div>
                  </div>
                ))}
                {!((cmdQuery.data ?? []) as CrawlerCommand[]).length ? (
                  <div className="flex h-[200px] items-center justify-center gap-2 text-sm text-muted-foreground">
                    <AlertTriangle className="h-4 w-4" /> 暂无指令
                  </div>
                ) : null}
              </div>
            </ScrollArea>
          </div>
        </div>

        <div className="space-y-4 rounded-2xl border border-border/70 bg-card/80 p-4">
          <header className="space-y-1">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-medium text-foreground">配置下发</h2>
                <p className="text-xs text-muted-foreground">爬虫通过 Key 拉取生效配置，支持模板/指派版本化。</p>
              </div>
              <Button variant="outline" size="sm" className="gap-1" onClick={() => setOpenCfg(true)}>
                <Maximize2 className="h-4 w-4" /> 放大
              </Button>
            </div>
          </header>
          <div className="rounded-xl border border-border/60 p-3 text-sm">
            {cfgQuery.isLoading ? (
              <Skeleton className="h-10 w-full" />
            ) : cfgQuery.data?.has_config ? (
              <div className="space-y-1 text-sm">
                <p className="text-foreground">{cfgQuery.data.name} · v{cfgQuery.data.version}</p>
                <p className="text-xs text-muted-foreground">{cfgQuery.data.format?.toUpperCase()} · 更新于 {cfgQuery.data.updated_at ? new Date(cfgQuery.data.updated_at).toLocaleString("zh-CN", { hour12: false }) : "—"}</p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">未发现生效配置。可在“配置与告警”页进行指派。</p>
            )}
          </div>
        </div>
      </section>

      {/* 放大查看对话框 */}
      <Dialog open={openHb} onOpenChange={setOpenHb}>
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>心跳记录</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <HeartbeatChart
              data={(hbQuery.data ?? []) as CrawlerHeartbeat[]}
              metricKey={selectedMetric}
              loading={hbQuery.isLoading || hbQuery.isFetching}
            />
            <div className="rounded-xl border border-border/60">
              <ScrollArea className="h-[60vh]">
                <div className="min-w-full divide-y divide-border/60">
                  {((hbQuery.data ?? []) as CrawlerHeartbeat[]).slice().reverse().map((hb) => (
                    <div key={hb.id} className="flex items-center justify-between px-3 py-2 text-xs">
                      <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${hb.status === "online" ? "bg-emerald-500" : hb.status === "warning" ? "bg-amber-500" : "bg-rose-500"}`} />
                        <span className="text-foreground">{hb.status}</span>
                      </div>
                      <div className="text-muted-foreground">{hb.source_ip ?? "-"}</div>
                      <div className="text-muted-foreground">{new Date(hb.created_at).toLocaleString("zh-CN", { hour12: false })}</div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={openLogs} onOpenChange={setOpenLogs}>
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>运行日志</DialogTitle>
          </DialogHeader>
          <ScrollArea className="h-[70vh] rounded-xl border border-border/60">
            <div className="min-w-full divide-y divide-border/60">
              {((logQuery.data ?? []) as CrawlerLog[]).map((log) => (
                <div key={log.id} className="flex items-center justify-between px-3 py-2 text-xs">
                  <span className="font-medium text-foreground">{log.level}</span>
                  <span className="mx-3 flex-1 truncate text-foreground">{log.message}</span>
                  <span className="text-muted-foreground">{new Date(log.ts).toLocaleString("zh-CN", { hour12: false })}</span>
                </div>
              ))}
              {!((logQuery.data ?? []) as CrawlerLog[]).length ? (
                <div className="flex h-[50vh] items-center justify-center gap-2 text-sm text-muted-foreground">
                  <AlertTriangle className="h-4 w-4" /> 暂无日志
                </div>
              ) : null}
            </div>
          </ScrollArea>
        </DialogContent>
      </Dialog>
      <Dialog open={openCmds} onOpenChange={setOpenCmds}>
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>远程指令</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => sendQuickCommand("pause")}>暂停</Button>
              <Button size="sm" onClick={() => sendQuickCommand("resume")}>恢复</Button>
              <Button size="sm" onClick={() => sendQuickCommand("restart")} className="gap-1">
                <PlayCircle className="h-4 w-4" /> 重启
              </Button>
              <Button size="sm" variant="secondary" onClick={() => sendQuickCommand("hot_update_config")}>热更新配置</Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  const task = typeof window !== "undefined" ? window.prompt("输入要切换的任务标识（task）:") : "";
                  if (task && task.trim()) {
                    sendCommand(`switch_task ${task.trim()}`);
                  }
                }}
              >
                切换任务
              </Button>
              <Button size="sm" variant="destructive" onClick={() => sendQuickCommand("graceful_shutdown")}>
                平滑停机
              </Button>
            </div>
            <div className="flex items-center gap-2">
              <Input value={customCmd} onChange={(e) => setCustomCmd(e.target.value)} placeholder="自定义指令，如: set_rate 2.0" />
              <Button size="sm" disabled={!customCmd || sending} onClick={() => sendCommand(customCmd)}>
                {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} 发送
              </Button>
            </div>
            <div className="rounded-xl border border-border/60">
              <div className="flex items-center justify-between border-b border-border/60 px-3 py-2 text-xs text-muted-foreground">
                <span>指令历史</span>
                <Button variant="ghost" size="sm" onClick={() => cmdQuery.refetch()} disabled={cmdQuery.isFetching}>
                  {cmdQuery.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
                </Button>
              </div>
              <ScrollArea className="h-[60vh]">
                <div className="min-w-full divide-y divide-border/60">
                  {((cmdQuery.data ?? []) as CrawlerCommand[]).map((cmd) => (
                    <div key={cmd.id} className="grid grid-cols-12 items-center gap-2 px-3 py-2 text-xs">
                      <div className="col-span-3 truncate text-foreground">{cmd.command}</div>
                      <div className="col-span-2 text-muted-foreground">{cmd.status}</div>
                      <div className="col-span-4 truncate text-muted-foreground">{cmd.result ? JSON.stringify(cmd.result) : "—"}</div>
                      <div className="col-span-3 text-muted-foreground">{new Date(cmd.created_at).toLocaleString("zh-CN", { hour12: false })}</div>
                    </div>
                  ))}
                  {!((cmdQuery.data ?? []) as CrawlerCommand[]).length ? (
                    <div className="flex h-[40vh] items-center justify-center gap-2 text-sm text-muted-foreground">
                      <AlertTriangle className="h-4 w-4" /> 暂无指令
                    </div>
                  ) : null}
                </div>
              </ScrollArea>
            </div>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={openCfg} onOpenChange={setOpenCfg}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>配置下发</DialogTitle>
          </DialogHeader>
          <div className="rounded-xl border border-border/60 p-3 text-sm">
            {cfgQuery.isLoading ? (
              <Skeleton className="h-10 w-full" />
            ) : cfgQuery.data?.has_config ? (
              <div className="space-y-1 text-sm">
                <p className="text-foreground">{cfgQuery.data.name} · v{cfgQuery.data.version}</p>
                <p className="text-xs text-muted-foreground">{cfgQuery.data.format?.toUpperCase()} · 更新于 {cfgQuery.data.updated_at ? new Date(cfgQuery.data.updated_at).toLocaleString("zh-CN", { hour12: false }) : "—"}</p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">未发现生效配置。可在“配置与告警”页进行指派。</p>
            )}
          </div>
        </DialogContent>
      </Dialog>

    </div>
  );

  async function sendQuickCommand(command: string) {
    await sendCommand(command);
  }
  async function sendCommand(command: string) {
    if (!command.trim()) return;
    setSending(true);
    try {
      await createCommand.mutateAsync({ command: command.trim() });
      setCustomCmd("");
      toast({ title: "指令已下发", description: command });
      await cmdQuery.refetch();
    } catch (e) {
      toast({ title: "发送失败", description: "创建远程指令失败", variant: "destructive" });
    } finally {
      setSending(false);
    }
  }
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1 rounded-2xl border border-border/70 bg-card/80 p-4">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-sm text-foreground">{value}</p>
    </div>
  );
}

