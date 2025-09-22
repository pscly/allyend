"use client";

import { useState } from "react";
import { Copy, Loader2, MoreVertical, RotateCcw, Shield, ShieldOff } from "lucide-react";

import type { ApiKey, CrawlerGroup } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface ApiKeyTableProps {
  keys: ApiKey[];
  groups: CrawlerGroup[];
  busyKeyId?: number | null;
  onEdit: (key: ApiKey) => void;
  onRotate: (key: ApiKey) => Promise<void> | void;
  onToggleActive: (key: ApiKey) => Promise<void> | void;
  onTogglePublic: (key: ApiKey) => Promise<void> | void;
  onDelete: (key: ApiKey) => Promise<void> | void;
  onCopy?: (key: ApiKey) => void;
}

function formatKeyPreview(value: string): string {
  if (!value) return "-";
  if (value.length <= 12) return value;
  return `${value.slice(0, 6)}…${value.slice(-4)}`;
}

export function ApiKeyTable({
  keys,
  groups,
  busyKeyId,
  onEdit,
  onRotate,
  onToggleActive,
  onTogglePublic,
  onDelete,
  onCopy,
}: ApiKeyTableProps) {
  const [copiedId, setCopiedId] = useState<number | null>(null);

  if (!keys.length) {
    return (
      <div className="rounded-2xl border border-border/80 bg-muted/10 p-6 text-sm text-muted-foreground">
        暂无 API Key，可先创建后分发给爬虫客户端。
      </div>
    );
  }

  const handleCopy = async (key: ApiKey) => {
    try {
      await navigator.clipboard.writeText(key.key);
      setCopiedId(key.id);
      onCopy?.(key);
      setTimeout(() => setCopiedId((prev) => (prev === key.id ? null : prev)), 2000);
    } catch {
      // ignore clipboard errors silently
    }
  };

  const resolveGroupName = (groupId: number | null, group?: ApiKey["group"]) => {
    if (group?.name) return group.name;
    const matched = groups.find((item) => item.id === groupId);
    return matched?.name ?? "未分组";
  };

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-4 py-2 text-left">本地编号</th>
            <th className="px-4 py-2 text-left">名称</th>
            <th className="px-4 py-2 text-left">Key</th>
            <th className="px-4 py-2 text-left">分组</th>
            <th className="px-4 py-2 text-left">公开</th>
            <th className="px-4 py-2 text-left">状态</th>
            <th className="px-4 py-2 text-left">最近使用</th>
            <th className="px-4 py-2 text-left">操作</th>
          </tr>
        </thead>
        <tbody>
          {keys.map((key) => {
            const isBusy = busyKeyId === key.id;
            return (
              <tr key={key.id} className="border-b border-border/70 last:border-0">
                <td className="px-4 py-2 font-medium text-foreground">#{key.local_id}</td>
                <td className="px-4 py-2 text-foreground">{key.name ?? "未命名"}</td>
                <td className="px-4 py-2">
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 text-primary hover:underline"
                    onClick={() => handleCopy(key)}
                  >
                    <Copy className="h-4 w-4" />
                    {copiedId === key.id ? "已复制" : formatKeyPreview(key.key)}
                  </button>
                </td>
                <td className="px-4 py-2 text-foreground">{resolveGroupName(key.group?.id ?? null, key.group)}</td>
                <td className="px-4 py-2 text-foreground">{key.is_public ? "已公开" : "未公开"}</td>
                <td className="px-4 py-2">
                  <span className={key.active ? "text-emerald-600" : "text-rose-500"}>
                    {key.active ? "启用" : "禁用"}
                  </span>
                </td>
                <td className="px-4 py-2 text-muted-foreground text-xs">
                  {key.last_used_at ? new Date(key.last_used_at).toLocaleString("zh-CN", { hour12: false }) : "—"}
                </td>
                <td className="px-4 py-2">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" disabled={isBusy}>
                        {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <MoreVertical className="h-4 w-4" />}
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-44">
                      <DropdownMenuItem onClick={() => onEdit(key)}>编辑</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onRotate(key)}>
                        <RotateCcw className="mr-2 h-4 w-4" /> 重置 Key
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onToggleActive(key)}>
                        {key.active ? "禁用" : "启用"} Key
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onTogglePublic(key)}>
                        {key.is_public ? (
                          <span className="inline-flex items-center"><ShieldOff className="mr-2 h-4 w-4" /> 关闭公开</span>
                        ) : (
                          <span className="inline-flex items-center"><Shield className="mr-2 h-4 w-4" /> 开启公开</span>
                        )}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onDelete(key)} className="text-destructive">
                        删除
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

