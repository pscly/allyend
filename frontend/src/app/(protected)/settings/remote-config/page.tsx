"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { CopyTextButton } from "@/features/public/copy-button";

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
      </div>
    
  );
}
