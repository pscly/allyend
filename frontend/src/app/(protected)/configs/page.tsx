"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { endpoints } from "@/lib/api/endpoints";
import { apiClient } from "@/lib/api/client";
import { CopyTextButton } from "@/features/public/copy-button";

interface AppConfigItem {
  app: string;
  description?: string | null;
  updated_at: string;
  read_count: number;
}

export default function ConfigsIndexPage() {
  const [appId, setAppId] = useState("");
  const [desc, setDesc] = useState("");
  const [jsonText, setJsonText] = useState("{\n  \"hello\": \"world\"\n}");
  const [error, setError] = useState<string | null>(null);

  const fileRef = useRef<HTMLInputElement | null>(null);

  const listQuery = useQuery<AppConfigItem[]>({
    queryKey: ["configs", "list"],
    queryFn: async () => apiClient.get<AppConfigItem[]>(endpoints.configs.list),
    staleTime: 10_000,
  });

  const upsertMutation = useMutation({
    mutationFn: async () => {
      setError(null);
      // 校验 JSON
      let obj: unknown;
      try {
        obj = JSON.parse(jsonText);
      } catch (e) {
        throw new Error("JSON 语法错误，请检查后再提交");
      }
      if (!appId.trim()) throw new Error("请填写 app 标识");
      return apiClient.put(endpoints.configs.upsert(appId.trim()), { description: desc || undefined, content: obj });
    },
    onSuccess: () => {
      listQuery.refetch();
    },
    onError: (e: any) => setError(e?.message || "保存失败"),
  });

  const onPickFile = () => fileRef.current?.click();
  const onFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const text = await f.text();
    try {
      const obj = JSON.parse(text);
      setJsonText(JSON.stringify(obj, null, 2));
    } catch (err) {
      setError("上传的文件不是有效 JSON");
    } finally {
      e.target.value = "";
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">公开配置管理</h1>
        <div className="text-sm text-muted-foreground">通过 /pz?app=xxx 无需登录读取</div>
      </div>

      <section className="rounded-xl border border-border/60 bg-card/50 p-4">
        <h2 className="mb-3 text-base font-medium">新增 / 更新配置</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="appId">app 标识</Label>
            <Input id="appId" placeholder="例如：001" value={appId} onChange={(e) => setAppId(e.target.value)} />
          </div>
          <div className="space-y-2 md:col-span-2">
            <Label htmlFor="desc">描述（可选）</Label>
            <Input id="desc" placeholder="例如：Windows 客户端配置" value={desc} onChange={(e) => setDesc(e.target.value)} />
          </div>
          <div className="space-y-2 md:col-span-3">
            <div className="flex items-center justify-between">
              <Label htmlFor="jsonText">JSON 内容</Label>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" onClick={onPickFile}>上传 JSON 文件</Button>
                <input ref={fileRef} type="file" accept="application/json" className="hidden" onChange={onFileChange} />
              </div>
            </div>
            <textarea
              id="jsonText"
              className="min-h-[200px] w-full rounded-md border bg-background p-3 font-mono text-sm"
              value={jsonText}
              onChange={(e) => setJsonText(e.target.value)}
              spellCheck={false}
            />
            {error && <div className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">{error}</div>}
            <div className="flex items-center justify-end">
              <Button onClick={() => upsertMutation.mutate()} disabled={upsertMutation.isPending}>
                {upsertMutation.isPending ? "保存中..." : "保存配置"}
              </Button>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border/60 bg-card/50 p-4">
        <h2 className="mb-3 text-base font-medium">配置列表</h2>
        <div className="divide-y rounded-md border">
          {(listQuery.data ?? []).map((it) => (
            <div key={it.app} className="flex items-center justify-between gap-3 p-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{it.app}</div>
                <div className="truncate text-xs text-muted-foreground">{it.description || "-"}</div>
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>读取 {it.read_count}</span>
                <span>更新 {new Date(it.updated_at).toLocaleString()}</span>
              </div>
              <div className="flex items-center gap-2">
                <Link className="text-sm text-primary hover:underline" href={`/configs/${encodeURIComponent(it.app)}`}>编辑</Link>
                <Link className="text-sm text-primary hover:underline" href={`/configs/${encodeURIComponent(it.app)}?tab=stats`}>统计</Link>
                {(() => {
                  const origin = typeof window !== "undefined" ? window.location.origin : "";
                  const url = `${origin}/pz?app=${encodeURIComponent(it.app)}`;
                  return <CopyTextButton value={url} label="复制URL" />;
                })()}
              </div>
            </div>
          ))}
          {listQuery.data?.length === 0 && <div className="p-4 text-center text-sm text-muted-foreground">暂无配置</div>}
        </div>
      </section>
    </div>
  );
}
