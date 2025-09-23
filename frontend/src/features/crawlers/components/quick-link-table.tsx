"use client";

import { useState } from "react";
import { ExternalLink, Eye, EyeOff, Globe, Loader2, MoreVertical, Trash2 } from "lucide-react";

import type { QuickLink } from "@/lib/api/types";
import { copyToClipboard } from "@/lib/clipboard";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface QuickLinkTableProps {
  links: QuickLink[];
  busyLinkId?: number | null;
  onEdit: (link: QuickLink) => void;
  onToggleActive: (link: QuickLink) => Promise<void> | void;
  onToggleLogs: (link: QuickLink) => Promise<void> | void;
  onDelete: (link: QuickLink) => Promise<void> | void;
  onCopy?: (link: QuickLink) => void;
  baseUrl?: string;
}

function resolveTargetLabel(link: QuickLink): string {
  if (link.target_type === "crawler") {
    return `Crawler #${link.crawler_local_id}`;
  }
  if (link.target_type === "api_key") {
    return `API Key #${link.api_key_local_id}`;
  }
  return `Group ${link.group_slug ?? ""} (#${link.group_id ?? "-"})`;
}

export function QuickLinkTable({
  links,
  busyLinkId,
  onEdit,
  onToggleActive,
  onToggleLogs,
  onDelete,
  onCopy,
  baseUrl,
}: QuickLinkTableProps) {
  const [copiedId, setCopiedId] = useState<number | null>(null);

  if (!links.length) {
    return (
      <div className="rounded-2xl border border-border/80 bg-muted/10 p-6 text-sm text-muted-foreground">
        暂未创建公开页，可在下方选择目标后生成访问地址。
      </div>
    );
  }

  const handleCopy = (link: QuickLink, linkUrl: string) => {
    copyToClipboard(linkUrl)
      .then((ok) => {
        if (ok) {
          setCopiedId(link.id);
          onCopy?.(link);
          setTimeout(() => setCopiedId((prev) => (prev === link.id ? null : prev)), 2000);
        }
      })
      .catch(() => undefined);
  };

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-4 py-2 text-left">Slug</th>
            <th className="px-4 py-2 text-left">目标</th>
            <th className="px-4 py-2 text-left">日志</th>
            <th className="px-4 py-2 text-left">状态</th>
            <th className="px-4 py-2 text-left">创建时间</th>
            <th className="px-4 py-2 text-left">操作</th>
          </tr>
        </thead>
        <tbody>
          {links.map((link) => {
            const linkUrl = baseUrl ? new URL(`/pa/${link.slug}`, baseUrl).toString() : `/pa/${link.slug}`;
            const isBusy = busyLinkId === link.id;
            return (
              <tr key={link.id} className="border-b border-border/70 last:border-0">
                <td className="px-4 py-2">
                  <a href={linkUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-primary hover:underline">
                    <Globe className="h-4 w-4" />
                    {link.slug}
                  </a>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="ml-2 h-6 px-2 text-xs"
                    onClick={() => handleCopy(link, linkUrl)}
                  >
                    {copiedId === link.id ? "已复制" : "复制"}
                  </Button>
                </td>
                <td className="px-4 py-2 text-foreground">{resolveTargetLabel(link)}</td>
                <td className="px-4 py-2 text-foreground">{link.allow_logs ? "开启" : "关闭"}</td>
                <td className="px-4 py-2">
                  <span className={link.is_active ? "text-emerald-600" : "text-rose-500"}>
                    {link.is_active ? "启用" : "禁用"}
                  </span>
                </td>
                <td className="px-4 py-2 text-xs text-muted-foreground">
                  {link.created_at ? new Date(link.created_at).toLocaleString("zh-CN", { hour12: false }) : "—"}
                </td>
                <td className="px-4 py-2">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" disabled={isBusy}>
                        {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <MoreVertical className="h-4 w-4" />}
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-44">
                      <DropdownMenuItem onClick={() => onEdit(link)}>编辑</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onToggleActive(link)}>
                        {link.is_active ? <EyeOff className="mr-2 h-4 w-4" /> : <Eye className="mr-2 h-4 w-4" />}
                        {link.is_active ? "停用" : "启用"}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onToggleLogs(link)}>
                        <ExternalLink className="mr-2 h-4 w-4" />
                        {link.allow_logs ? "关闭日志" : "开放日志"}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onDelete(link)} className="text-destructive">
                        <Trash2 className="mr-2 h-4 w-4" /> 删除
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
