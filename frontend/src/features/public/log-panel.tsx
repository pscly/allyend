"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Loader2, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { CrawlerLog } from "@/lib/api/types";
import { buildApiUrl } from "@/lib/env";
import { cn } from "@/lib/utils";

import type { PublicLinkSummary } from "./types";

interface FiltersState {
  start: string;
  end: string;
  minLevel: number;
  maxLevel: number;
  limit: number;
}

const LOG_LEVEL_OPTIONS = [
  { code: 0, label: "TRACE" },
  { code: 10, label: "DEBUG" },
  { code: 20, label: "INFO" },
  { code: 30, label: "WARNING" },
  { code: 40, label: "ERROR" },
  { code: 50, label: "CRITICAL" },
];

const LEVEL_CLASSNAME: Record<number, string> = {
  0: "bg-slate-500/15 text-slate-500",
  10: "bg-sky-500/15 text-sky-500",
  20: "bg-emerald-500/15 text-emerald-500",
  30: "bg-amber-500/15 text-amber-500",
  40: "bg-rose-500/15 text-rose-500",
  50: "bg-red-600/15 text-red-600",
};

function createDefaultFilters(): FiltersState {
  return {
    start: "",
    end: "",
    minLevel: 0,
    maxLevel: 50,
    limit: 200,
  };
}

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

function getLevelLabel(code: number) {
  return LOG_LEVEL_OPTIONS.find((item) => item.code === code)?.label ?? `LEVEL ${code}`;
}

function getLevelClass(code: number) {
  return LEVEL_CLASSNAME[code] ?? "bg-slate-500/15 text-slate-500";
}

function buildOwnerLabel(summary: PublicLinkSummary, log: CrawlerLog) {
  if (summary.type === "crawler") {
    const local = log.crawler_local_id ?? summary.local_id;
    const name = summary.name ?? "爬虫";
    return local ? `${name} #${local}` : name;
  }
  if (summary.type === "api_key") {
    if (log.crawler_name) return log.crawler_name;
    if (summary.crawler_name) return summary.crawler_name;
    const local = summary.local_id;
    return summary.name ? `${summary.name}${local ? ` #${local}` : ""}` : `API Key #${local}`;
  }
  const local = log.crawler_local_id;
  const crawlerName = log.crawler_name ?? (local ? `爬虫 #${local}` : "成员");
  const groupName = summary.group_name ?? summary.name ?? "公开分组";
  return `${groupName} · ${crawlerName}`;
}

interface PublicLogPanelProps {
  slug: string;
  summary: PublicLinkSummary;
}

export function PublicLogPanel({ slug, summary }: PublicLogPanelProps) {
  const [filters, setFilters] = useState<FiltersState>(() => createDefaultFilters());
  const [logs, setLogs] = useState<CrawlerLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allowLogs = summary.allow_logs;

  const loadLogs = useCallback(
    async (current: FiltersState) => {
      setLoading(true);
      setError(null);
      try {
        const url = new URL(buildApiUrl(`/pa/${slug}/api/logs`));
        const min = Math.min(current.minLevel, current.maxLevel);
        const max = Math.max(current.minLevel, current.maxLevel);
        if (current.start) url.searchParams.set("start", current.start);
        if (current.end) url.searchParams.set("end", current.end);
        url.searchParams.set("min_level", String(min));
        url.searchParams.set("max_level", String(max));
        url.searchParams.set("limit", String(Math.min(Math.max(current.limit, 1), 1000)));
        const response = await fetch(url.toString(), { cache: "no-store" });
        if (!response.ok) {
          throw new Error("日志加载失败，请稍后重试。");
        }
        const data: CrawlerLog[] = await response.json();
        setLogs(data);
        if (!data.length) {
          setError("暂无日志，可调整筛选后再次查询。");
        }
      } catch (err) {
        setLogs([]);
        setError(err instanceof Error ? err.message : "日志加载失败，请稍后重试。");
      } finally {
        setLoading(false);
      }
    },
    [slug],
  );

  useEffect(() => {
    if (!allowLogs) return;
    void loadLogs(filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allowLogs, loadLogs]);

  const levelOptions = useMemo(() => LOG_LEVEL_OPTIONS, []);

  if (!allowLogs) {
    return (
      <div className="rounded-2xl border border-border/70 bg-card/80 p-6 text-sm text-muted-foreground">
        该链接未开放日志访问。
      </div>
    );
  }

  const handleRefresh = () => {
    void loadLogs(filters);
  };

  const handleReset = () => {
    const next = createDefaultFilters();
    setFilters(next);
    void loadLogs(next);
  };

  return (
    <div className="space-y-4 rounded-2xl border border-border/70 bg-card/80 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium text-foreground">实时日志</h2>
          <p className="text-xs text-muted-foreground">支持日期与等级筛选，最多可拉取最近 1000 条。</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={handleReset} disabled={loading}>
            重置
          </Button>
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
            <span className="ml-1">刷新</span>
          </Button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-5">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground" htmlFor="public-log-start">
            开始日期
          </label>
          <Input
            id="public-log-start"
            type="date"
            value={filters.start}
            onChange={(event) => setFilters((prev) => ({ ...prev, start: event.target.value }))}
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground" htmlFor="public-log-end">
            结束日期
          </label>
          <Input
            id="public-log-end"
            type="date"
            value={filters.end}
            onChange={(event) => setFilters((prev) => ({ ...prev, end: event.target.value }))}
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground" htmlFor="public-log-min">
            最小等级
          </label>
          <select
            id="public-log-min"
            className="h-9 w-full rounded-md border border-border bg-background px-2 text-sm"
            value={filters.minLevel}
            onChange={(event) => setFilters((prev) => ({ ...prev, minLevel: Number(event.target.value) }))}
          >
            {levelOptions.map((item) => (
              <option key={item.code} value={item.code}>
                {item.code} - {item.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground" htmlFor="public-log-max">
            最大等级
          </label>
          <select
            id="public-log-max"
            className="h-9 w-full rounded-md border border-border bg-background px-2 text-sm"
            value={filters.maxLevel}
            onChange={(event) => setFilters((prev) => ({ ...prev, maxLevel: Number(event.target.value) }))}
          >
            {levelOptions.map((item) => (
              <option key={item.code} value={item.code}>
                {item.code} - {item.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground" htmlFor="public-log-limit">
            最多条数
          </label>
          <Input
            id="public-log-limit"
            type="number"
            min={1}
            max={1000}
            value={filters.limit}
            onChange={(event) => setFilters((prev) => ({ ...prev, limit: Number(event.target.value) }))}
          />
        </div>
      </div>

      {error && !logs.length ? (
        <div className="flex items-center gap-2 rounded-xl border border-border/60 bg-muted/10 p-4 text-sm text-muted-foreground">
          <AlertTriangle className="h-4 w-4" />
          {error}
        </div>
      ) : null}

      <ScrollArea className="max-h-[420px]">
        <div className="space-y-3">
          {logs.map((log) => (
            <div key={log.id} className="rounded-xl border border-border/60 bg-muted/5 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                <span>{formatDateTime(log.ts)}</span>
                <div className="flex flex-wrap items-center gap-2">
                  <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium", getLevelClass(log.level_code))}>
                    {getLevelLabel(log.level_code)}
                  </span>
                  <span>{buildOwnerLabel(summary, log)}</span>
                  {log.source_ip ? <span className="text-muted-foreground/80">IP: {log.source_ip}</span> : null}
                </div>
              </div>
              <p className="mt-2 text-sm text-foreground">{log.message}</p>
            </div>
          ))}
          {!logs.length && !error && !loading ? (
            <div className="flex items-center gap-2 rounded-xl border border-border/60 bg-muted/10 p-4 text-sm text-muted-foreground">
              <AlertTriangle className="h-4 w-4" /> 暂无日志，可调整筛选后再次查询。
            </div>
          ) : null}
        </div>
      </ScrollArea>
    </div>
  );
}
