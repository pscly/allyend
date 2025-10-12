"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { endpoints } from "@/lib/api/endpoints";
import { apiClient } from "@/lib/api/client";

const ECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

interface ConfigDetail {
  app: string;
  description?: string | null;
  content: any;
  version: number;
  updated_at: string;
  created_at: string;
}

interface StatsPoint { ts: string; count: number }
interface StatsOut { app: string; range_days: number; granularity: string; series: StatsPoint[]; top_ips: [string, number][] }

export default function ConfigDetailPage({ params, searchParams }: { params: { app: string }; searchParams: Record<string, string> }) {
  const app = decodeURIComponent(params.app);
  const [desc, setDesc] = useState("");
  const [jsonText, setJsonText] = useState("{}");
  const [error, setError] = useState<string | null>(null);
  const defaultTab = searchParams?.tab === "stats" ? "stats" : "edit";
  const [tab, setTab] = useState<"edit" | "stats">(defaultTab);

  const detailQuery = useQuery<ConfigDetail>({
    queryKey: ["configs", app, "detail"],
    queryFn: async () => apiClient.get<ConfigDetail>(endpoints.configs.byApp(app)),
    staleTime: 5_000,
  });

  useEffect(() => {
    if (detailQuery.data) {
      setDesc(detailQuery.data.description || "");
      setJsonText(JSON.stringify(detailQuery.data.content ?? {}, null, 2));
    }
  }, [detailQuery.data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      setError(null);
      let obj: unknown;
      try {
        obj = JSON.parse(jsonText);
      } catch (e) {
        throw new Error("JSON 语法错误");
      }
      return apiClient.put(endpoints.configs.upsert(app), { description: desc || undefined, content: obj });
    },
    onSuccess: () => detailQuery.refetch(),
    onError: (e: any) => setError(e?.message || "保存失败"),
  });

  const statsQuery = useQuery<StatsOut>({
    queryKey: ["configs", app, "stats"],
    queryFn: async () => apiClient.get<StatsOut>(endpoints.configs.stats(app), { searchParams: { days: 7, granularity: "day" } }),
    staleTime: 10_000,
    enabled: tab === "stats",
  });

  const option = useMemo(() => {
    const s = statsQuery.data?.series ?? [];
    return {
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: s.map((p) => new Date(p.ts).toLocaleString()) },
      yAxis: { type: "value" },
      series: [{ type: "line", data: s.map((p) => p.count) }],
    } as any;
  }, [statsQuery.data]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">配置：{app}</h1>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>版本 {detailQuery.data?.version ?? "-"}</span>
          <span>更新 {detailQuery.data ? new Date(detailQuery.data.updated_at).toLocaleString() : "-"}</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button className={`rounded-full px-3 py-1 text-sm ${tab === "edit" ? "bg-primary text-primary-foreground" : "bg-muted"}`} onClick={() => setTab("edit")}>编辑配置</button>
        <button className={`rounded-full px-3 py-1 text-sm ${tab === "stats" ? "bg-primary text-primary-foreground" : "bg-muted"}`} onClick={() => setTab("stats")}>读取统计</button>
      </div>

      {tab === "edit" ? (
        <section className="rounded-xl border border-border/60 bg-card/50 p-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="space-y-2 md:col-span-3">
              <Label htmlFor="desc">描述（可选）</Label>
              <Input id="desc" value={desc} onChange={(e) => setDesc(e.target.value)} />
            </div>
            <div className="space-y-2 md:col-span-3">
              <Label htmlFor="jsonText">JSON 内容</Label>
              <textarea id="jsonText" className="min-h-[320px] w-full rounded-md border bg-background p-3 font-mono text-sm" value={jsonText} onChange={(e) => setJsonText(e.target.value)} spellCheck={false} />
              {error && <div className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">{error}</div>}
              <div className="flex items-center justify-end">
                <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>{saveMutation.isPending ? "保存中..." : "保存"}</Button>
              </div>
            </div>
          </div>
        </section>
      ) : (
        <section className="space-y-4 rounded-xl border border-border/60 bg-card/50 p-4">
          <div className="text-sm text-muted-foreground">近 7 天读取次数</div>
          <div className="h-[320px] w-full">
            <ECharts option={option} notMerge lazyUpdate style={{ height: "100%", width: "100%" }} />
          </div>
          <div>
            <div className="mb-2 text-sm font-medium">Top IP</div>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {(statsQuery.data?.top_ips ?? []).map(([ip, cnt]) => (
                <div key={ip} className="flex items-center justify-between rounded-md border p-2 text-sm">
                  <span className="truncate">{ip}</span>
                  <span className="text-muted-foreground">{cnt}</span>
                </div>
              ))}
              {statsQuery.data?.top_ips?.length === 0 && <div className="text-sm text-muted-foreground">暂无数据</div>}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

