"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw, Search, Eye, EyeOff, Pin, PinOff, Trash2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { CopyTextButton } from "@/features/public/copy-button";
import { apiClient } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { AppConfigDetail, AppConfigListItem } from "@/lib/api/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

// 本地存储键名，避免与其它设置冲突
const LS_KEYS = {
  baseUrl: "remote_config.base_url",
  appId: "remote_config.app_id",
} as const;

// 预留：自定义解密逻辑占位（默认原样返回）
// 你可以在这里替换为自己的解密算法，例如 AES/Base64/SM4 等
function decryptConfig<T extends JsonValue>(data: T): T {
  // TODO: 根据你的加密方案实现解密
  return data;
}

export default function RemoteConfigPage() {
  // 表单状态
  const [baseUrl, setBaseUrl] = useState("");
  const [appId, setAppId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<JsonValue | null>(null);

  const mountedRef = useRef(false);

  // 首次挂载时，从本地恢复最近一次输入
  useEffect(() => {
    if (mountedRef.current) return;
    mountedRef.current = true;
    try {
      const savedBase = localStorage.getItem(LS_KEYS.baseUrl) || "";
      const savedApp = localStorage.getItem(LS_KEYS.appId) || "";
      if (savedBase) setBaseUrl(savedBase);
      if (savedApp) setAppId(savedApp);
    } catch {
      // 忽略本地存储异常
    }
  }, []);

  // 组合最终请求 URL
  const requestUrl = useMemo(() => {
    try {
      if (!baseUrl) return "";
      // 允许用户直接粘贴完整 URL（含查询）或仅粘贴基础路径
      const url = new URL(baseUrl);
      if (appId) {
        url.searchParams.set("app", appId);
      }
      return url.toString();
    } catch {
      return "";
    }
  }, [baseUrl, appId]);

  const canFetch = requestUrl.length > 0;

  const doFetch = useCallback(async () => {
    if (!canFetch) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      // 持久化最近一次输入
      try {
        localStorage.setItem(LS_KEYS.baseUrl, baseUrl);
        localStorage.setItem(LS_KEYS.appId, appId);
      } catch {
        // 忽略本地存储异常
      }

      // 超时控制，避免长时间挂起
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 10000);

      const resp = await fetch(requestUrl, {
        method: "GET",
        signal: controller.signal,
        // 如需附加鉴权头，可在此扩展 headers
        // headers: { Authorization: `Bearer ${token}` },
        credentials: "omit",
        cache: "no-store",
      });
      clearTimeout(timer);

      if (!resp.ok) {
        const text = await resp.text().catch(() => "");
        throw new Error(`请求失败：${resp.status} ${resp.statusText}${text ? `\n${text}` : ""}`);
      }

      // 支持 JSON 与纯文本两种返回
      const contentType = resp.headers.get("content-type") || "";
      let payload: JsonValue | string;
      if (contentType.includes("application/json")) {
        payload = (await resp.json()) as JsonValue;
      } else {
        const text = await resp.text();
        try {
          payload = JSON.parse(text) as JsonValue;
        } catch {
          payload = text;
        }
      }

      // 预留解密
      const decrypted = decryptConfig(payload as JsonValue);
      setResult(decrypted);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [canFetch, requestUrl, baseUrl, appId]);

  const prettyJson = useMemo(() => {
    try {
      if (result == null) return "";
      return JSON.stringify(result, null, 2);
    } catch {
      return String(result);
    }
  }, [result]);

  // ============
  // 管理：列表、搜索、置顶、禁用、删除、创建
  // ============
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [onlyEnabled, setOnlyEnabled] = useState(false);

  const listQuery = useQuery<AppConfigListItem[]>({
    queryKey: ["configs", { q, onlyEnabled }],
    queryFn: async () =>
      apiClient.get<AppConfigListItem[]>(endpoints.configs.list, {
        searchParams: { q: q || undefined, only_enabled: onlyEnabled },
      }),
    staleTime: 10_000,
  });

  // 注意：新建时需要对“全部 App”做重复校验，不能受当前搜索/筛选影响
  const allAppsQuery = useQuery<AppConfigListItem[]>({
    queryKey: ["configs_all"],
    queryFn: async () => apiClient.get<AppConfigListItem[]>(endpoints.configs.list),
    staleTime: 30_000,
  });

  const toggleEnabledMutation = useMutation({
    mutationFn: async ({ app, enabled }: { app: string; enabled: boolean }) =>
      apiClient.patch<AppConfigDetail>(endpoints.configs.meta(app), undefined, {
        searchParams: { enabled },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["configs"] });
    },
  });

  const togglePinnedMutation = useMutation({
    mutationFn: async ({ app, pinned }: { app: string; pinned: boolean }) =>
      apiClient.patch<AppConfigDetail>(endpoints.configs.meta(app), undefined, {
        searchParams: { pinned },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["configs"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: async (app: string) => apiClient.delete<{ ok: boolean }>(endpoints.configs.remove(app)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["configs"] }),
  });

  // 创建对话框
  const [openCreate, setOpenCreate] = useState(false);
  const [newApp, setNewApp] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newJson, setNewJson] = useState("{\n  \"example\": true\n}");
  const existingApps = (allAppsQuery.data || []).map((i) => i.app);
  const isDup = newApp && existingApps.includes(newApp);
  const canSubmit = newApp && !isDup && newJson.trim().length > 0;

  const createMutation = useMutation({
    mutationFn: async () => {
      // 验证 JSON
      let obj: unknown;
      try {
        obj = JSON.parse(newJson);
      } catch (e) {
        throw new Error("JSON 格式无效，请检查");
      }
      return apiClient.put<AppConfigDetail, { description: string | null; content: Record<string, unknown> }>(
        endpoints.configs.upsert(newApp),
        { description: newDesc || null, content: obj as Record<string, unknown> },
      );
    },
    onSuccess: () => {
      setOpenCreate(false);
      setNewApp("");
      setNewDesc("");
      setNewJson("{\n  \"example\": true\n}");
      qc.invalidateQueries({ queryKey: ["configs"] });
    },
  });

  return (
    <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">在线配置获取</h1>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setResult(null);
                setError(null);
              }}
            >
              清空结果
            </Button>
            <Button
              size="sm"
              onClick={doFetch}
              disabled={!canFetch || loading}
              className={cn(loading && "opacity-80")}
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 正在获取
                </>
              ) : (
                <>
                  <RefreshCw className="mr-2 h-4 w-4" /> 立即获取
                </>
              )}
            </Button>
          </div>
        </div>

        <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="space-y-2 md:col-span-2">
            <Label htmlFor="baseUrl">配置服务地址（支持完整 URL 或基础路径）</Label>
            <Input
              id="baseUrl"
              placeholder="例如：https://hosts/pz 或 https://hosts/pz?app=001"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="appId">应用标识 app（可选）</Label>
            <Input
              id="appId"
              placeholder="例如：001"
              value={appId}
              onChange={(e) => setAppId(e.target.value)}
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
            />
          </div>
        </section>

        <section className="rounded-xl border border-border/60 bg-card/50 p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              请求地址：<span className="select-all text-foreground">{requestUrl || "无效地址"}</span>
            </div>
            {prettyJson && <CopyTextButton value={prettyJson} label="复制 JSON" />}
          </div>

          {error ? (
            <div className="whitespace-pre-wrap rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-destructive">
              {error}
            </div>
          ) : loading ? (
            <div className="flex min-h-[160px] items-center justify-center text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 加载中...
            </div>
          ) : prettyJson ? (
            <pre className="max-h-[420px] overflow-auto rounded-lg bg-muted/40 p-3 text-xs leading-5">
{prettyJson}
            </pre>
          ) : (
            <div className="text-sm text-muted-foreground">
              在上方填写地址与 app，点击“立即获取”拉取配置。默认通过 GET 请求，无需登录；若服务端有 CORS 限制，请改为通过后端代理。
            </div>
          )}
        </section>

        <section className="text-xs text-muted-foreground">
          <p className="mb-1 font-medium">提示</p>
          <ul className="list-inside list-disc space-y-1">
            <li>若服务端返回加密内容，可在本页顶部的 <code>decryptConfig</code> 函数中加入解密逻辑。</li>
            <li>涉及敏感参数请在服务端加密，客户端仅做解密与呈现，避免泄露明文。</li>
            <li>如遇跨域（CORS）拦截，可在后端新增转发接口再由前端调用。</li>
          </ul>
        </section>

        {/* 管理区块 */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">我的应用配置</h2>
            <Dialog open={openCreate} onOpenChange={setOpenCreate}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="mr-2 h-4 w-4" /> 新建配置
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>新建应用配置</DialogTitle>
                  <DialogDescription>应用标识必须唯一，内容为合法 JSON。</DialogDescription>
                </DialogHeader>
                <div className="grid gap-3">
                  <div className="grid gap-2">
                    <Label htmlFor="newApp">应用标识 app（唯一）</Label>
                    <Input id="newApp" value={newApp} onChange={(e) => setNewApp(e.target.value.trim())} placeholder="例如：my_app_001" />
                    {isDup && <p className="text-xs text-destructive">该标识已存在，请更换</p>}
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="newDesc">描述（可选）</Label>
                    <Input id="newDesc" value={newDesc} onChange={(e) => setNewDesc(e.target.value)} placeholder="简要说明" />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="newJson">配置 JSON</Label>
                    <textarea id="newJson" className="min-h-[160px] w-full rounded-md border border-border bg-background p-2 text-sm font-mono" value={newJson} onChange={(e) => setNewJson(e.target.value)} spellCheck={false} />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="secondary" onClick={() => setOpenCreate(false)} disabled={createMutation.isPending}>取消</Button>
                  <Button onClick={() => createMutation.mutate()} disabled={!canSubmit || createMutation.isPending}>
                    {createMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    提交
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          <div className="flex flex-col gap-3 rounded-xl border border-border/60 bg-card/50 p-3">
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input className="pl-8" placeholder="搜索 app 或描述..." value={q} onChange={(e) => setQ(e.target.value)} />
              </div>
              <Button
                variant={onlyEnabled ? "default" : "secondary"}
                size="sm"
                onClick={() => setOnlyEnabled((v) => !v)}
                title={onlyEnabled ? "显示全部" : "仅看已启用"}
              >
                {onlyEnabled ? <Eye className="mr-2 h-4 w-4" /> : <EyeOff className="mr-2 h-4 w-4" />} {onlyEnabled ? "仅启用" : "全部"}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => listQuery.refetch()} disabled={listQuery.isFetching}>
                {listQuery.isFetching ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />} 刷新
              </Button>
            </div>

            <div className="overflow-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th className="p-2">App</th>
                    <th className="p-2">描述</th>
                    <th className="p-2 whitespace-nowrap">读取次数</th>
                    <th className="p-2 whitespace-nowrap">更新时间</th>
                    <th className="p-2 w-[220px]">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {listQuery.isLoading ? (
                    <tr><td className="p-3 text-muted-foreground" colSpan={5}>加载中...</td></tr>
                  ) : (listQuery.data || []).length === 0 ? (
                    <tr><td className="p-3 text-muted-foreground" colSpan={5}>暂无数据</td></tr>
                  ) : (
                    (listQuery.data || []).map((item) => (
                      <tr key={item.app} className="border-t border-border/60">
                        <td className="p-2 font-mono">{item.app}</td>
                        <td className="p-2 text-muted-foreground">{item.description || "-"}</td>
                        <td className="p-2">{item.read_count}</td>
                        <td className="p-2">{new Date(item.updated_at).toLocaleString()}</td>
                        <td className="p-2">
                          <div className="flex items-center gap-2">
                            <Button
                              variant={item.pinned ? "default" : "secondary"}
                              size="sm"
                              onClick={() => togglePinnedMutation.mutate({ app: item.app, pinned: !item.pinned })}
                              disabled={togglePinnedMutation.isPending}
                              title={item.pinned ? "取消置顶" : "置顶"}
                            >
                              {item.pinned ? <Pin className="mr-2 h-4 w-4" /> : <PinOff className="mr-2 h-4 w-4" />} {item.pinned ? "已置顶" : "置顶"}
                            </Button>
                            <Button
                              variant={item.enabled ? "secondary" : "destructive"}
                              size="sm"
                              onClick={() => toggleEnabledMutation.mutate({ app: item.app, enabled: !item.enabled })}
                              disabled={toggleEnabledMutation.isPending}
                              title={item.enabled ? "禁用" : "启用"}
                            >
                              {item.enabled ? <EyeOff className="mr-2 h-4 w-4" /> : <Eye className="mr-2 h-4 w-4" />} {item.enabled ? "禁用" : "启用"}
                            </Button>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => {
                                if (confirm(`确认删除配置 ${item.app} ？此操作不可恢复`)) {
                                  deleteMutation.mutate(item.app);
                                }
                              }}
                              disabled={deleteMutation.isPending}
                            >
                              <Trash2 className="mr-2 h-4 w-4" /> 删除
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>
    
  );
}
