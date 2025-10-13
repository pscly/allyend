import Link from "next/link";

import { AppShell } from "@/components/layout/app-shell";
import { cn } from "@/lib/utils";
import type { FileEntry } from "@/lib/api/types";
import { env } from "@/lib/env";

// 该页面为匿名可访问的公开文件列表，仅展示 visibility = public 的文件
// 注意：/files/* 在 next.config.mjs 中已被代理到后端 FastAPI，无需额外的 API 中转
export const dynamic = "force-dynamic";

async function fetchPublicFiles(limit = 100): Promise<FileEntry[]> {
  // 通过站点基址构造绝对 URL，避免服务端相对路径解析报错
  const url = new URL("/files/public", env.appBaseUrl);
  url.searchParams.set("limit", String(limit));
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) {
    // 失败时返回空数组，避免页面报错
    return [] as FileEntry[];
  }
  const data = (await res.json()) as FileEntry[];
  return Array.isArray(data) ? data : [];
}

function formatSize(bytes?: number | null) {
  if (!Number.isFinite(bytes ?? NaN)) return "-";
  let n = Number(bytes);
  const units = ["B", "KB", "MB", "GB", "TB"] as const;
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(1)} ${units[i]}`;
}

export default async function PublicFilesPage() {
  const files = await fetchPublicFiles(200);

  return (
    <AppShell className="space-y-6">
      <header className="flex flex-col gap-1 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">公开文件</h1>
          <p className="text-sm text-muted-foreground">未登录也可访问。仅显示标记为“公开”的文件，可直接下载。</p>
        </div>
        <div className="text-sm text-muted-foreground">
          <Link href="/dashboard/files" className={cn("hover:underline")}>文件管理</Link>
        </div>
      </header>

      {files.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/70 p-10 text-center text-sm text-muted-foreground">
          暂无公开文件。
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-border/70">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/40 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2 font-medium">文件名</th>
                <th className="px-4 py-2 font-medium">大小</th>
                <th className="px-4 py-2 font-medium">上传时间</th>
                <th className="px-4 py-2 font-medium">下载</th>
              </tr>
            </thead>
            <tbody>
              {files.map((f) => {
                const href = f.download_url || `/files/${encodeURIComponent(String(f.id))}/download`;
                return (
                  <tr key={f.id} className="border-t border-border/60">
                    <td className="px-4 py-2 align-middle text-foreground">{f.original_name}</td>
                    <td className="px-4 py-2 align-middle text-muted-foreground">{formatSize(f.size_bytes)}</td>
                    <td className="px-4 py-2 align-middle text-muted-foreground">
                      {f.created_at ? new Date(f.created_at).toLocaleString() : "-"}
                    </td>
                    <td className="px-4 py-2 align-middle">
                      <a href={href} className="text-primary hover:underline">下载</a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}
