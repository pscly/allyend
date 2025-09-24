"use client";


import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import {
  AlertTriangle,
  BarChart3,
  ChevronRight,
  Copy,
  Edit,
  Filter,
  Globe,
  Layers,
  Link as LinkIcon,
  Loader2,
  MoreVertical,
  Plus,
  RefreshCcw,
  Shield,
  ShieldOff,
  SlidersHorizontal,
  Trash2,
  Users,
} from "lucide-react";

import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";

import { env } from "@/lib/env";
import { cn } from "@/lib/utils";
import { copyToClipboard } from "@/lib/clipboard";
import { ApiError } from "@/lib/api/client";
import type { ApiKey, CrawlerGroup, CrawlerSummary, QuickLink } from "@/lib/api/types";

import {
  useCrawlersQuery,
  useApiKeysQuery,
  useCrawlerGroupsQuery,
  useQuickLinksQuery,
} from "@/features/crawlers/queries";
import {
  useCreateApiKeyMutation,
  useUpdateApiKeyMutation,
  useDeleteApiKeyMutation,
  useRotateApiKeyMutation,
  useCreateCrawlerGroupMutation,
  useUpdateCrawlerGroupMutation,
  useDeleteCrawlerGroupMutation,
  useCreateQuickLinkMutation,
  useUpdateQuickLinkMutation,
  useDeleteQuickLinkMutation,
  useUpdateCrawlerMutation,
} from "@/features/crawlers/mutations";
import {
  createApiKeySchema,
  updateApiKeySchema,
  createQuickLinkSchema,
  updateQuickLinkSchema,
  type CreateApiKeyForm,
  type UpdateApiKeyForm,
  type CreateQuickLinkForm,
  type UpdateQuickLinkForm,
} from "@/features/crawlers/schemas";
import { ApiKeyTable } from "@/features/crawlers/components/api-key-table";
import { QuickLinkTable } from "@/features/crawlers/components/quick-link-table";
import { ConfigAlertPanel } from "@/features/crawlers/components/config-alert-panel";
import { CrawlerStatusBadge } from "@/features/crawlers/components/status-badge";

type StatusFilter = "online" | "warning" | "offline";
type ToastInvoker = ReturnType<typeof useToast>["toast"];

type GroupFilterValue = number | "none";

const STATUS_LABELS: Record<StatusFilter, string> = {
  online: "在线",
  warning: "警告",
  offline: "离线",
};

const STATUS_CARD_STYLE: Record<StatusFilter, string> = {
  online: "border-emerald-500/60 bg-emerald-500/5",
  warning: "border-amber-500/60 bg-amber-500/5",
  offline: "border-rose-500/60 bg-rose-500/5",
};

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.payload?.detail ?? error.message ?? fallback;
  }
  if (error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

function formatRelativeTime(value: string | null | undefined): string {
  if (!value) return "暂无心跳";
  const target = new Date(value);
  if (Number.isNaN(target.getTime())) return "未知时间";
  const diff = Date.now() - target.getTime();
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (Math.abs(diff) < minute) {
    return diff >= 0 ? "刚刚" : "即将";
  }
  if (Math.abs(diff) < hour) {
    const mins = Math.round(diff / minute);
    return `${Math.abs(mins)} 分钟${diff >= 0 ? "前" : "后"}`;
  }
  if (Math.abs(diff) < day) {
    const hours = Math.round(diff / hour);
    return `${Math.abs(hours)} 小时${diff >= 0 ? "前" : "后"}`;
  }
  const days = Math.round(diff / day);
  return `${Math.abs(days)} 天${diff >= 0 ? "前" : "后"}`;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const target = new Date(value);
  if (Number.isNaN(target.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(target);
}

function formatUptime(ratio?: number | null): string {
  if (ratio === undefined || ratio === null) return "—";
  const percent = Math.max(0, Math.min(1, ratio)) * 100;
  return `${percent.toFixed(1)}%`;
}
function extractPayloadMetrics(payload: Record<string, unknown> | null | undefined) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return [] as Array<{ key: string; value: string }>;
  return Object.entries(payload)
    .filter(([_, value]) => {
      if (typeof value === "number") return Number.isFinite(value);
      if (typeof value === "string") return value.length > 0 && value.length <= 40;
      return false;
    })
    .slice(0, 4)
    .map(([key, value]) => ({ key, value: String(value) }));
}

function buildPublicUrl(slug: string): string {
  // 基于当前前端访问域名生成公开地址；在无 window 环境时回退到配置的 appBaseUrl
  if (!slug) return "";
  const base = typeof window !== "undefined" ? window.location.origin : env.appBaseUrl;
  try {
    return new URL(`/pa/${slug}`, base).toString();
  } catch {
    return `/pa/${slug}`;
  }
}

export default function CrawlersPage() {
  const { toast } = useToast();

  const [tab, setTab] = useState("status");
  const [statusFilters, setStatusFilters] = useState<StatusFilter[]>([]);
  const [groupFilters, setGroupFilters] = useState<GroupFilterValue[]>([]);
  const [apiKeyFilters, setApiKeyFilters] = useState<number[]>([]);
  const [searchInput, setSearchInput] = useState("");
  const [keyword, setKeyword] = useState("");

  useEffect(() => {
    const handler = window.setTimeout(() => {
      setKeyword(searchInput.trim());
    }, 400);
    return () => window.clearTimeout(handler);
  }, [searchInput]);

  const crawlersQuery = useCrawlersQuery({
    statuses: statusFilters,
    groupIds: groupFilters,
    apiKeyIds: apiKeyFilters,
    keyword: keyword || undefined,
  });
  const groupsQuery = useCrawlerGroupsQuery();
  const apiKeysQuery = useApiKeysQuery();
  const quickLinksQuery = useQuickLinksQuery();

  // 收敛 React Query 返回的数据类型，避免 never[] 联合类型引发的推断问题
  const crawlers = useMemo<CrawlerSummary[]>(() => crawlersQuery.data ?? [], [crawlersQuery.data]);
  const groups = useMemo<CrawlerGroup[]>(() => groupsQuery.data ?? [], [groupsQuery.data]);
  const apiKeys = useMemo<ApiKey[]>(() => apiKeysQuery.data ?? [], [apiKeysQuery.data]);
  const quickLinks = useMemo<QuickLink[]>(() => quickLinksQuery.data ?? [], [quickLinksQuery.data]);

  const statusSummary = useMemo(() => {
    const base: Record<StatusFilter, number> = { online: 0, warning: 0, offline: 0 };
    crawlers.forEach((crawler) => {
      if (crawler.status === "online" || crawler.status === "warning" || crawler.status === "offline") {
        base[crawler.status as StatusFilter] += 1;
      }
    });
    return base;
  }, [crawlers]);

  const groupUsage = useMemo(() => {
    const map = new Map<number, number>();
    let ungrouped = 0;
    crawlers.forEach((crawler) => {
      const groupId = crawler.group?.id;
      if (groupId) {
        map.set(groupId, (map.get(groupId) ?? 0) + 1);
      } else {
        ungrouped += 1;
      }
    });
    return { map, ungrouped };
  }, [crawlers]);
  const createKeyForm = useForm<CreateApiKeyForm>({
    resolver: zodResolver(createApiKeySchema),
    defaultValues: { name: "", description: "", groupId: "none", allowedIps: "", isPublic: false },
  });
  const editKeyForm = useForm<UpdateApiKeyForm>({
    resolver: zodResolver(updateApiKeySchema),
    defaultValues: { name: "", description: "", groupId: "none", allowedIps: "", isPublic: false },
  });

  const [isCreateKeyDialogOpen, setCreateKeyDialogOpen] = useState(false);
  const [isEditKeyDialogOpen, setEditKeyDialogOpen] = useState(false);
  const [editingKey, setEditingKey] = useState<ApiKey | null>(null);
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [busyKeyId, setBusyKeyId] = useState<number | null>(null);

  const createKeyMutation = useCreateApiKeyMutation();
  const updateKeyMutation = useUpdateApiKeyMutation();
  const deleteKeyMutation = useDeleteApiKeyMutation();
  const rotateKeyMutation = useRotateApiKeyMutation();

  const [isGroupDialogOpen, setGroupDialogOpen] = useState(false);
  const [editingGroup, setEditingGroup] = useState<CrawlerGroup | null>(null);
  const [groupName, setGroupName] = useState("");
  const [groupSlug, setGroupSlug] = useState("");
  const [groupDescription, setGroupDescription] = useState("");
  const [groupColor, setGroupColor] = useState("");
  const [groupForUpdateId, setGroupForUpdateId] = useState<number | null>(null);
  const [groupForDeleteId, setGroupForDeleteId] = useState<number | null>(null);

  const createGroupMutation = useCreateCrawlerGroupMutation();
  const updateGroupMutation = useUpdateCrawlerGroupMutation(groupForUpdateId ?? 0);
  const deleteGroupMutation = useDeleteCrawlerGroupMutation(groupForDeleteId ?? 0);

  const [isQuickLinkDialogOpen, setQuickLinkDialogOpen] = useState(false);
  const [editingQuickLink, setEditingQuickLink] = useState<QuickLink | null>(null);
  const createQuickLinkForm = useForm<CreateQuickLinkForm>({
    resolver: zodResolver(createQuickLinkSchema),
    // targetId 在表单类型中为 number（zod 已 transform），默认用 0 占位，提交时校验 > 0
    defaultValues: { targetType: "crawler", targetId: 0, slug: "", description: "", allowLogs: true },
  });
  const editQuickLinkForm = useForm<UpdateQuickLinkForm>({
    resolver: zodResolver(updateQuickLinkSchema),
    defaultValues: { slug: "", description: "", allowLogs: true, isActive: true },
  });
  const createQuickLinkMutation = useCreateQuickLinkMutation();
  const updateQuickLinkMutation = useUpdateQuickLinkMutation();
  const deleteQuickLinkMutation = useDeleteQuickLinkMutation();
  const [busyLinkId, setBusyLinkId] = useState<number | null>(null);

  const toggleStatus = (status: StatusFilter) => {
    setStatusFilters((prev) =>
      prev.includes(status) ? prev.filter((item) => item !== status) : [...prev, status],
    );
  };

  const toggleGroup = (value: GroupFilterValue, next: boolean) => {
    setGroupFilters((prev) => {
      const exists = prev.includes(value);
      if (next) {
        return exists ? prev : [...prev, value];
      }
      return prev.filter((item) => item !== value);
    });
  };

  const toggleApiKeyFilter = (id: number, next: boolean) => {
    setApiKeyFilters((prev) => {
      const exists = prev.includes(id);
      if (next) {
        return exists ? prev : [...prev, id];
      }
      return prev.filter((item) => item !== id);
    });
  };

  const clearFilters = () => {
    setStatusFilters([]);
    setGroupFilters([]);
    setApiKeyFilters([]);
    setSearchInput("");
    setKeyword("");
  };
  const handleOpenCreateKey = (open: boolean) => {
    setCreateKeyDialogOpen(open);
    if (open) {
      setGeneratedKey(null);
      createKeyForm.reset({ name: "", description: "", groupId: "none", allowedIps: "", isPublic: false });
    }
  };

  const handleCreateKey = createKeyForm.handleSubmit(async (values) => {
    const payload = {
      name: values.name.trim(),
      description: values.description?.trim() || undefined,
      group_id: values.groupId && values.groupId !== "none" ? Number(values.groupId) : null,
      allowed_ips: values.allowedIps?.trim() ? values.allowedIps.trim() : null,
      is_public: values.isPublic,
    };
    try {
      const created = await createKeyMutation.mutateAsync(payload);
      setGeneratedKey(created.key);
      toast({ title: "Key 已创建", description: created.name ?? created.key });
      createKeyForm.reset({ name: "", description: "", groupId: "none", allowedIps: "", isPublic: false });
    } catch (error) {
      toast({ title: "创建失败", description: getErrorMessage(error, "生成 Key 失败"), variant: "destructive" });
    }
  });

  const handleEditKey = (key: ApiKey) => {
    setEditingKey(key);
    setGeneratedKey(null);
    setEditKeyDialogOpen(true);
    editKeyForm.reset({
      name: key.name ?? "",
      description: key.description ?? "",
      groupId: key.group?.id ? String(key.group.id) : "none",
      allowedIps: key.allowed_ips ?? "",
      isPublic: key.is_public,
    });
  };

  const handleUpdateKey = editKeyForm.handleSubmit(async (values) => {
    if (!editingKey) return;
    const payload = {
      name: values.name?.trim() || undefined,
      description: values.description?.trim() || undefined,
      group_id: values.groupId
        ? values.groupId === "none"
          ? null
          : Number(values.groupId)
        : undefined,
      allowed_ips: values.allowedIps?.trim() ? values.allowedIps.trim() : null,
      is_public: values.isPublic,
    };
    setBusyKeyId(editingKey.id);
    try {
      await updateKeyMutation.mutateAsync({ keyId: editingKey.id, payload });
      toast({ title: "Key 已更新", description: editingKey.name ?? `Key #${editingKey.local_id}` });
      setEditKeyDialogOpen(false);
    } catch (error) {
      toast({ title: "更新失败", description: getErrorMessage(error, "更新 Key 失败"), variant: "destructive" });
    } finally {
      setBusyKeyId(null);
    }
  });

  const handleToggleKeyActive = async (key: ApiKey) => {
    setBusyKeyId(key.id);
    try {
      await updateKeyMutation.mutateAsync({ keyId: key.id, payload: { active: !key.active } });
      toast({ title: key.active ? "Key 已禁用" : "Key 已启用", description: key.name ?? `Key #${key.local_id}` });
    } catch (error) {
      toast({ title: "操作失败", description: getErrorMessage(error, "更新 Key 状态失败"), variant: "destructive" });
    } finally {
      setBusyKeyId(null);
    }
  };

  const handleToggleKeyPublic = async (key: ApiKey) => {
    setBusyKeyId(key.id);
    try {
      await updateKeyMutation.mutateAsync({ keyId: key.id, payload: { is_public: !key.is_public } });
      toast({ title: key.is_public ? "已关闭公开" : "已公开 Key", description: key.name ?? `Key #${key.local_id}` });
    } catch (error) {
      toast({ title: "操作失败", description: getErrorMessage(error, "更新公开状态失败"), variant: "destructive" });
    } finally {
      setBusyKeyId(null);
    }
  };

  const handleRotateKey = async (key: ApiKey) => {
    const confirmed = window.confirm(`确定要重置 Key ${key.name ?? `#${key.local_id}`} 吗？旧值将立即失效。`);
    if (!confirmed) return;
    setBusyKeyId(key.id);
    try {
      const rotated = await rotateKeyMutation.mutateAsync(key.id);
      toast({ title: "Key 已重置", description: rotated.key });
    } catch (error) {
      toast({ title: "重置失败", description: getErrorMessage(error, "重置 Key 失败"), variant: "destructive" });
    } finally {
      setBusyKeyId(null);
    }
  };

  const handleDeleteKey = async (key: ApiKey) => {
    const confirmed = window.confirm(`确定要删除 Key ${key.name ?? `#${key.local_id}`} 吗？此操作无法恢复。`);
    if (!confirmed) return;
    setBusyKeyId(key.id);
    try {
      await deleteKeyMutation.mutateAsync(key.id);
      toast({ title: "Key 已删除", description: key.name ?? `Key #${key.local_id}` });
    } catch (error) {
      toast({ title: "删除失败", description: getErrorMessage(error, "删除 Key 失败"), variant: "destructive" });
    } finally {
      setBusyKeyId(null);
    }
  };
  const openGroupDialog = (group?: CrawlerGroup) => {
    setGroupDialogOpen(true);
    if (group) {
      setEditingGroup(group);
      setGroupForUpdateId(group.id);
      setGroupName(group.name);
      setGroupSlug(group.slug ?? "");
      setGroupDescription(group.description ?? "");
      setGroupColor(group.color ?? "");
    } else {
      setEditingGroup(null);
      setGroupForUpdateId(null);
      setGroupName("");
      setGroupSlug("");
      setGroupDescription("");
      setGroupColor("");
    }
  };

  const handleSubmitGroup = async (event: React.FormEvent) => {
    event.preventDefault();
    const payload = {
      name: groupName.trim(),
      slug: groupSlug.trim() || undefined,
      description: groupDescription.trim() || undefined,
      color: groupColor.trim() || undefined,
    };
    if (!payload.name) {
      toast({ title: "请填写分组名称", variant: "destructive" });
      return;
    }
    try {
      if (editingGroup) {
        await updateGroupMutation.mutateAsync(payload);
        toast({ title: "分组已更新", description: editingGroup.name });
      } else {
        await createGroupMutation.mutateAsync(payload);
        toast({ title: "分组已创建", description: payload.name });
      }
      setGroupDialogOpen(false);
    } catch (error) {
      toast({ title: "保存失败", description: getErrorMessage(error, "保存分组失败"), variant: "destructive" });
    }
  };

  const handleDeleteGroup = async (group: CrawlerGroup) => {
    const confirmed = window.confirm(`确定要删除分组 ${group.name} 吗？`);
    if (!confirmed) return;
    setGroupForDeleteId(group.id);
    try {
      await deleteGroupMutation.mutateAsync();
      toast({ title: "分组已删除", description: group.name });
    } catch (error) {
      toast({ title: "删除失败", description: getErrorMessage(error, "删除分组失败"), variant: "destructive" });
    } finally {
      setGroupForDeleteId(null);
    }
  };

  const openCreateQuickLink = (options?: { targetType: "crawler" | "api_key" | "group"; targetId: number; description?: string }) => {
    setEditingQuickLink(null);
    setQuickLinkDialogOpen(true);
    createQuickLinkForm.reset({
      targetType: options?.targetType ?? "crawler",
      targetId: options ? options.targetId : 0,
      slug: "",
      description: options?.description ?? "",
      allowLogs: options?.targetType === "crawler" ? false : true,
    });
  };

  const handleCreateQuickLink = createQuickLinkForm.handleSubmit(async (values) => {
    const targetId = Number(values.targetId);
    if (!Number.isFinite(targetId) || targetId <= 0) {
      toast({ title: "请选择有效的目标", variant: "destructive" });
      return;
    }
    const payload = {
      target_type: values.targetType,
      target_id: targetId,
      slug: values.slug?.trim() || undefined,
      description: values.description?.trim() || undefined,
      allow_logs: values.allowLogs,
    };
    try {
      const created = await createQuickLinkMutation.mutateAsync(payload);
      toast({ title: "公开页已创建", description: created.slug });
      setQuickLinkDialogOpen(false);
    } catch (error) {
      toast({ title: "创建失败", description: getErrorMessage(error, "创建公开页失败"), variant: "destructive" });
    }
  });

  const handleEditQuickLink = (link: QuickLink) => {
    setEditingQuickLink(link);
    setQuickLinkDialogOpen(true);
    editQuickLinkForm.reset({
      slug: link.slug,
      description: link.description ?? "",
      allowLogs: link.allow_logs,
      isActive: link.is_active,
    });
  };

  const handleUpdateQuickLink = editQuickLinkForm.handleSubmit(async (values) => {
    if (!editingQuickLink) return;
    const payload = {
      slug: values.slug?.trim() || undefined,
      description: values.description?.trim() || undefined,
      allow_logs: values.allowLogs,
      is_active: values.isActive,
    };
    setBusyLinkId(editingQuickLink.id);
    try {
      await updateQuickLinkMutation.mutateAsync({ linkId: editingQuickLink.id, payload });
      toast({ title: "公开页已更新", description: editingQuickLink.slug });
      setQuickLinkDialogOpen(false);
    } catch (error) {
      toast({ title: "更新失败", description: getErrorMessage(error, "更新公开页失败"), variant: "destructive" });
    } finally {
      setBusyLinkId(null);
    }
  });

  const handleToggleLinkActive = async (link: QuickLink) => {
    setBusyLinkId(link.id);
    try {
      await updateQuickLinkMutation.mutateAsync({ linkId: link.id, payload: { is_active: !link.is_active } });
      toast({ title: link.is_active ? "已停用公开页" : "已启用公开页", description: link.slug });
    } catch (error) {
      toast({ title: "操作失败", description: getErrorMessage(error, "更新公开页状态失败"), variant: "destructive" });
    } finally {
      setBusyLinkId(null);
    }
  };

  const handleToggleLinkLogs = async (link: QuickLink) => {
    setBusyLinkId(link.id);
    try {
      await updateQuickLinkMutation.mutateAsync({ linkId: link.id, payload: { allow_logs: !link.allow_logs } });
      toast({ title: link.allow_logs ? "已关闭日志" : "已开放日志", description: link.slug });
    } catch (error) {
      toast({ title: "操作失败", description: getErrorMessage(error, "更新日志权限失败"), variant: "destructive" });
    } finally {
      setBusyLinkId(null);
    }
  };

  const handleDeleteQuickLink = async (link: QuickLink) => {
    const confirmed = window.confirm(`确定要删除公开页 ${link.slug} 吗？`);
    if (!confirmed) return;
    setBusyLinkId(link.id);
    try {
      await deleteQuickLinkMutation.mutateAsync(link.id);
      toast({ title: "公开页已删除", description: link.slug });
    } catch (error) {
      toast({ title: "删除失败", description: getErrorMessage(error, "删除公开页失败"), variant: "destructive" });
    } finally {
      setBusyLinkId(null);
    }
  };
  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <h1 className="text-2xl font-semibold text-foreground">爬虫控制台</h1>
        <p className="text-sm text-muted-foreground">
          基于 API Key 的身份体系，集中管理爬虫心跳、运行状态、公开页、配置下发与告警策略。
        </p>
      </header>

      <Tabs value={tab} onValueChange={setTab} className="space-y-6">
        <TabsList className="w-full justify-start overflow-x-auto">
          <TabsTrigger value="status">状态面板</TabsTrigger>
          <TabsTrigger value="keys">Key 管理</TabsTrigger>
          <TabsTrigger value="public">公开页面</TabsTrigger>
          <TabsTrigger value="config">配置与告警</TabsTrigger>
        </TabsList>

        <TabsContent value="status" className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {(Object.keys(STATUS_LABELS) as StatusFilter[]).map((status) => (
              <div
                key={status}
                className={cn(
                  "rounded-2xl border border-border/70 bg-card/70 p-5 shadow-sm",
                  STATUS_CARD_STYLE[status],
                )}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">{STATUS_LABELS[status]}</p>
                    <p className="mt-2 text-3xl font-semibold text-foreground">{statusSummary[status]}</p>
                  </div>
                  <div className="rounded-full bg-background/60 p-3 text-muted-foreground">
                    <BarChart3 className="h-5 w-5" />
                  </div>
                </div>
                <p className="mt-4 text-xs text-muted-foreground">
                  {status === "online" ? "5 分钟内收到心跳" : status === "warning" ? "15 分钟内无心跳" : "超过 15 分钟未在线"}
                </p>
              </div>
            ))}
          </section>

          <section className="space-y-4 rounded-3xl border border-border/70 bg-card/80 p-5 shadow-surface">
            <header className="flex flex-wrap items-center gap-2 text-sm font-medium text-muted-foreground">
              <SlidersHorizontal className="h-4 w-4" />
              条件筛选
            </header>
            <div className="flex flex-wrap items-center gap-2">
              {(Object.keys(STATUS_LABELS) as StatusFilter[]).map((status) => {
                const isActive = statusFilters.includes(status);
                return (
                  <Button
                    key={status}
                    variant={isActive ? "default" : "outline"}
                    size="sm"
                    onClick={() => toggleStatus(status)}
                  >
                    <span
                      className="mr-2 inline-flex h-2 w-2 rounded-full"
                      style={{
                        backgroundColor:
                          status === "online" ? "#10b981" : status === "warning" ? "#f59e0b" : "#ef4444",
                      }}
                    />
                    {STATUS_LABELS[status]}
                  </Button>
                );
              })}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="gap-2">
                    <Layers className="h-4 w-4" />
                    分组
                    {groupFilters.length ? <span className="text-xs text-primary">({groupFilters.length})</span> : null}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-56">
                  <DropdownMenuLabel>选择分组</DropdownMenuLabel>
                  <DropdownMenuCheckboxItem
                    checked={groupFilters.includes("none")}
                    onCheckedChange={(checked) => toggleGroup("none", checked === true)}
                  >
                    未分组
                  </DropdownMenuCheckboxItem>
                  <DropdownMenuSeparator />
                  {groups.map((group) => (
                    <DropdownMenuCheckboxItem
                      key={group.id}
                      checked={groupFilters.includes(group.id)}
                      onCheckedChange={(checked) => toggleGroup(group.id, checked === true)}
                    >
                      {group.name}
                    </DropdownMenuCheckboxItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="gap-2">
                    <LinkIcon className="h-4 w-4" />
                    来源 Key
                    {apiKeyFilters.length ? <span className="text-xs text-primary">({apiKeyFilters.length})</span> : null}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-60">
                  <DropdownMenuLabel>选择 API Key</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {apiKeys.map((key) => (
                    <DropdownMenuCheckboxItem
                      key={key.id}
                      checked={apiKeyFilters.includes(key.id)}
                      onCheckedChange={(checked) => toggleApiKeyFilter(key.id, checked === true)}
                    >
                      {key.name ?? `Key #${key.local_id}`}
                    </DropdownMenuCheckboxItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <Input
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  placeholder="按爬虫名称、Key、IP 搜索"
                  className="w-64"
                />
                <Button variant="ghost" size="sm" onClick={clearFilters}>
                  清空
                </Button>
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Filter className="h-3.5 w-3.5" />
                当前筛选命中 {crawlers.length} 条记录
              </div>
              <div className="flex-1" />
              <Button
                variant="outline"
                size="sm"
                onClick={() => crawlersQuery.refetch()}
                disabled={crawlersQuery.isFetching}
                className="ml-auto"
              >
                {crawlersQuery.isFetching ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 刷新中
                  </>
                ) : (
                  <>
                    <RefreshCcw className="mr-2 h-4 w-4" /> 刷新
                  </>
                )}
              </Button>
            </div>
          </section>
          <section className="space-y-4">
            {crawlersQuery.isLoading ? (
              <div className="grid gap-4 lg:grid-cols-2">
                {Array.from({ length: 4 }).map((_, index) => (
                  <Skeleton key={index} className="h-48 rounded-3xl" />
                ))}
              </div>
            ) : crawlers.length === 0 ? (
              <div className="flex min-h-[220px] flex-col items-center justify-center gap-3 rounded-3xl border border-border/70 bg-card/70 p-8 text-center">
                <AlertTriangle className="h-8 w-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">没有符合条件的爬虫。试试调整筛选条件或创建新的 Key。</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Button
                    size="sm"
                    onClick={() => {
                      setTab("keys");
                      handleOpenCreateKey(true);
                    }}
                  >
                    <Plus className="mr-2 h-4 w-4" /> 去创建 Key
                  </Button>
                  <Button variant="outline" size="sm" onClick={clearFilters}>
                    清空筛选
                  </Button>
                </div>
              </div>
            ) : (
              <div className="grid gap-4 lg:grid-cols-2">
                {crawlers.map((crawler) => (
                  <CrawlerCard
                    key={crawler.id}
                    crawler={crawler}
                    toast={toast}
                    onCreateQuickLink={(target) => openCreateQuickLink({ targetType: "crawler", targetId: target.id, description: `${target.name} 状态页` })}
                  />
                ))}
              </div>
            )}
          </section>
        </TabsContent>
        <TabsContent value="keys" className="space-y-6">
          <section className="space-y-3 rounded-3xl border border-border/70 bg-card/80 p-5 shadow-surface">
            <header className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-foreground">API Key 管理</h2>
                <p className="text-sm text-muted-foreground">Key 是爬虫唯一身份凭据，可分组、禁用、重置并控制公开范围。</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={() => handleOpenCreateKey(true)} className="gap-2">
                  <Plus className="h-4 w-4" /> 新建 Key
                </Button>
                <Button variant="outline" size="sm" onClick={() => openGroupDialog()}>
                  <Users className="mr-2 h-4 w-4" /> 新建分组
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    apiKeysQuery.refetch();
                    groupsQuery.refetch();
                  }}
                  disabled={apiKeysQuery.isFetching || groupsQuery.isFetching}
                >
                  {apiKeysQuery.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
                </Button>
              </div>
            </header>
            <ScrollArea className="max-h-[520px] rounded-2xl border border-border/60">
              <div className="min-w-full p-4">
                <ApiKeyTable
                  keys={apiKeys}
                  groups={groups}
                  busyKeyId={busyKeyId}
                  onEdit={handleEditKey}
                  onRotate={handleRotateKey}
                  onToggleActive={handleToggleKeyActive}
                  onTogglePublic={handleToggleKeyPublic}
                  onDelete={handleDeleteKey}
                  onCopy={(key) => toast({ title: "已复制 Key", description: key.name ?? key.key })}
                />
              </div>
            </ScrollArea>
          </section>

          <section className="space-y-4 rounded-3xl border border-border/70 bg-card/70 p-5 shadow-surface">
            <header className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-medium text-foreground">分组概览</h3>
                <p className="text-xs text-muted-foreground">用于按业务、环境或地域组织 Key 和爬虫。</p>
              </div>
              <Button variant="outline" size="sm" onClick={() => openGroupDialog()}>
                <Plus className="mr-2 h-4 w-4" /> 新增分组
              </Button>
            </header>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {groups.map((group) => (
                <GroupCard
                  key={group.id}
                  group={group}
                  crawlerCount={groupUsage.map.get(group.id) ?? group.crawler_count ?? 0}
                  onEdit={() => openGroupDialog(group)}
                  onDelete={() => handleDeleteGroup(group)}
                />
              ))}
              <div className="rounded-2xl border border-border/60 bg-muted/20 p-4 text-sm text-muted-foreground">
                <p className="font-medium text-foreground">未分组</p>
                <p className="mt-2 text-2xl font-semibold text-foreground">{groupUsage.ungrouped}</p>
                <p className="mt-3 text-xs">建议为常驻爬虫建立分组，方便筛选和授权。</p>
              </div>
            </div>
          </section>
        </TabsContent>
        <TabsContent value="public" className="space-y-6">
          <section className="space-y-3 rounded-3xl border border-border/70 bg-card/80 p-5 shadow-surface">
            <header className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-foreground">公开状态页</h2>
                <p className="text-sm text-muted-foreground">
                  为团队外部或合作方提供无需登录的运行状态视图，敏感信息自动脱敏，可选日志共享。
                </p>
              </div>
              <Button size="sm" className="gap-2" onClick={() => openCreateQuickLink()}>
                <Globe className="h-4 w-4" /> 创建公开页
              </Button>
            </header>
            <ScrollArea className="max-h-[480px] rounded-2xl border border-border/60">
              <div className="min-w-full p-4">
                <QuickLinkTable
                  links={quickLinks}
                  busyLinkId={busyLinkId}
                  onEdit={handleEditQuickLink}
                  onToggleActive={handleToggleLinkActive}
                  onToggleLogs={handleToggleLinkLogs}
                  onDelete={handleDeleteQuickLink}
                  onCopy={(link) => toast({ title: "已复制公开地址", description: buildPublicUrl(link.slug) })}
                  // 使用当前页面的访问域名进行拼接，SSR 时退回配置
                  baseUrl={typeof window !== 'undefined' ? window.location.origin : env.appBaseUrl}
                />
              </div>
            </ScrollArea>
          </section>
        </TabsContent>

        <TabsContent value="config" className="space-y-6">
          <section className="space-y-4 rounded-3xl border border-border/70 bg-card/80 p-5 shadow-surface">
            <header className="space-y-2">
              <h2 className="text-lg font-semibold text-foreground">配置下发与告警策略</h2>
              <p className="text-sm text-muted-foreground">
                通过模板和指派集中维护爬虫配置，并针对离线、指标异常自动推送告警。
              </p>
            </header>
            <ConfigAlertPanel groups={groups} apiKeys={apiKeys} crawlers={crawlers} toast={toast} />
          </section>
        </TabsContent>
      </Tabs>
      <Dialog open={isCreateKeyDialogOpen} onOpenChange={handleOpenCreateKey}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>创建 API Key</DialogTitle>
            <DialogDescription>生成唯一凭证，分配至对应业务分组后可用于爬虫认证。</DialogDescription>
          </DialogHeader>
          <form className="space-y-4" onSubmit={handleCreateKey}>
            <div className="space-y-2">
              <Label htmlFor="keyName">名称</Label>
              <Input id="keyName" placeholder="例如：京东-手机类目" {...createKeyForm.register("name")} />
              {createKeyForm.formState.errors.name ? (
                <p className="text-xs text-destructive">{createKeyForm.formState.errors.name.message}</p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="keyDescription">描述</Label>
              <textarea
                id="keyDescription"
                className="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                placeholder="用途、负责人或目标站点，便于追溯"
                {...createKeyForm.register("description")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="keyGroup">分组</Label>
              <select
                id="keyGroup"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                {...createKeyForm.register("groupId")}
              >
                <option value="none">未分组</option>
                {groups.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="keyIps">IP 白名单（可选）</Label>
              <Input id="keyIps" placeholder="127.0.0.1, 192.168.1.2" {...createKeyForm.register("allowedIps")} />
            </div>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border border-input"
                {...createKeyForm.register("isPublic")}
              />
              允许链接公开查询基础状态
            </label>
            {generatedKey ? (
              <div className="space-y-2 rounded-xl border border-emerald-500/60 bg-emerald-500/5 p-3 text-sm">
                <p className="font-medium text-emerald-600">已生成新的 Key，请立即保存：</p>
                <div className="flex items-center justify-between gap-2 rounded-lg border border-emerald-500/40 bg-background px-3 py-2">
                  <span className="truncate font-mono text-xs text-foreground">{generatedKey}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() =>
                      copyToClipboard(generatedKey)
                        .then((ok) => ok && toast({ title: "已复制 Key" }))
                        .catch(() => undefined)
                    }
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ) : null}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => handleOpenCreateKey(false)}>
                取消
              </Button>
              <Button type="submit" disabled={createKeyMutation.isPending}>
                {createKeyMutation.isPending ? "生成中..." : "确认创建"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={isEditKeyDialogOpen} onOpenChange={(next) => {
        setEditKeyDialogOpen(next);
        if (!next) setEditingKey(null);
      }}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>编辑 Key</DialogTitle>
            <DialogDescription>更新分组、描述或公开范围。</DialogDescription>
          </DialogHeader>
          <form className="space-y-4" onSubmit={handleUpdateKey}>
            <div className="space-y-2">
              <Label htmlFor="editKeyName">名称</Label>
              <Input id="editKeyName" placeholder="Key 名称" {...editKeyForm.register("name")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="editKeyDescription">描述</Label>
              <textarea
                id="editKeyDescription"
                className="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                {...editKeyForm.register("description")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="editKeyGroup">分组</Label>
              <select
                id="editKeyGroup"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                {...editKeyForm.register("groupId")}
              >
                <option value="none">未分组</option>
                {groups.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="editKeyIps">IP 白名单</Label>
              <Input id="editKeyIps" {...editKeyForm.register("allowedIps")} />
            </div>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input type="checkbox" className="h-4 w-4 rounded border border-input" {...editKeyForm.register("isPublic")} />
              允许公开展示基本状态
            </label>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditKeyDialogOpen(false)}>
                取消
              </Button>
              <Button type="submit" disabled={updateKeyMutation.isPending || busyKeyId === editingKey?.id}>
                {updateKeyMutation.isPending || busyKeyId === editingKey?.id ? "保存中..." : "保存"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog open={isGroupDialogOpen} onOpenChange={(next) => {
        setGroupDialogOpen(next);
        if (!next) {
          setEditingGroup(null);
        }
      }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editingGroup ? "编辑分组" : "新建分组"}</DialogTitle>
            <DialogDescription>分组可用于权限隔离、筛选与公开页聚合。</DialogDescription>
          </DialogHeader>
          <form className="space-y-4" onSubmit={handleSubmitGroup}>
            <div className="space-y-2">
              <Label htmlFor="groupName">名称</Label>
              <Input id="groupName" value={groupName} onChange={(event) => setGroupName(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="groupSlug">Slug（可选）</Label>
              <Input id="groupSlug" value={groupSlug} onChange={(event) => setGroupSlug(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="groupColor">颜色（可选）</Label>
              <Input id="groupColor" value={groupColor} onChange={(event) => setGroupColor(event.target.value)} placeholder="#2563eb" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="groupDescription">描述</Label>
              <textarea
                id="groupDescription"
                className="min-h-[64px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                value={groupDescription}
                onChange={(event) => setGroupDescription(event.target.value)}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setGroupDialogOpen(false)}>
                取消
              </Button>
              <Button type="submit" disabled={createGroupMutation.isPending || updateGroupMutation.isPending}>
                {createGroupMutation.isPending || updateGroupMutation.isPending ? "保存中..." : "保存"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={isQuickLinkDialogOpen} onOpenChange={(next) => {
        setQuickLinkDialogOpen(next);
        if (!next) {
          setEditingQuickLink(null);
        }
      }}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingQuickLink ? "编辑公开页" : "创建公开页"}</DialogTitle>
            <DialogDescription>
              自定义访问地址、展示内容和日志权限，可用于对外展示健康状态。
            </DialogDescription>
          </DialogHeader>
          {editingQuickLink ? (
            <form className="space-y-4" onSubmit={handleUpdateQuickLink}>
              <div className="space-y-2 text-sm text-muted-foreground">
                <p>目标：
                  {editingQuickLink.target_type === "crawler"
                    ? ` 爬虫 #${editingQuickLink.crawler_local_id}`
                    : editingQuickLink.target_type === "api_key"
                      ? ` API Key #${editingQuickLink.api_key_local_id}`
                      : ` 分组 ${editingQuickLink.group_name ?? editingQuickLink.group_slug}`}
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="editSlug">Slug</Label>
                <Input id="editSlug" placeholder="自定义访问路径" {...editQuickLinkForm.register("slug")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="editDesc">描述</Label>
                <textarea
                  id="editDesc"
                  className="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  {...editQuickLinkForm.register("description")}
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input type="checkbox" className="h-4 w-4 rounded border border-input" {...editQuickLinkForm.register("allowLogs")} />
                允许公开查看日志
              </label>
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input type="checkbox" className="h-4 w-4 rounded border border-input" {...editQuickLinkForm.register("isActive")} />
                启用访问
              </label>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setQuickLinkDialogOpen(false)}>
                  取消
                </Button>
                <Button type="submit" disabled={updateQuickLinkMutation.isPending || busyLinkId === editingQuickLink.id}>
                  {updateQuickLinkMutation.isPending || busyLinkId === editingQuickLink.id ? "保存中..." : "保存"}
                </Button>
              </DialogFooter>
            </form>
          ) : (
            <form className="space-y-4" onSubmit={handleCreateQuickLink}>
              <div className="space-y-2">
                <Label htmlFor="createTargetType">目标类型</Label>
                <select
                  id="createTargetType"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  {...createQuickLinkForm.register("targetType")}
                >
                  <option value="crawler">爬虫</option>
                  <option value="api_key">API Key</option>
                  <option value="group">分组</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="createTargetId">目标</Label>
                <select
                  id="createTargetId"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  {...createQuickLinkForm.register("targetId")}
                >
                  <option value="">请选择</option>
                  {createQuickLinkForm.watch("targetType") === "crawler"
                    ? crawlers.map((crawler) => (
                        <option key={crawler.id} value={crawler.id}>
                          {crawler.name}（#{crawler.local_id}）
                        </option>
                      ))
                    : createQuickLinkForm.watch("targetType") === "api_key"
                      ? apiKeys.map((key) => (
                          <option key={key.id} value={key.id}>
                            {key.name ?? `Key #${key.local_id}`}
                          </option>
                        ))
                      : groups.map((group) => (
                          <option key={group.id} value={group.id}>
                            {group.name}
                          </option>
                        ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="createSlug">Slug</Label>
                <Input id="createSlug" placeholder="可自定义访问路径" {...createQuickLinkForm.register("slug")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="createDesc">描述</Label>
                <textarea
                  id="createDesc"
                  className="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  {...createQuickLinkForm.register("description")}
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input type="checkbox" className="h-4 w-4 rounded border border-input" {...createQuickLinkForm.register("allowLogs")} />
                允许公开查看日志
              </label>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setQuickLinkDialogOpen(false)}>
                  取消
                </Button>
                <Button type="submit" disabled={createQuickLinkMutation.isPending}>
                  {createQuickLinkMutation.isPending ? "创建中..." : "确认创建"}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
interface CrawlerCardProps {
  crawler: CrawlerSummary;
  toast: ToastInvoker;
  onCreateQuickLink?: (crawler: CrawlerSummary) => void;
}

function CrawlerCard({ crawler, toast, onCreateQuickLink }: CrawlerCardProps) {
  const updateCrawlerMutation = useUpdateCrawlerMutation(crawler.id);

  const metrics = useMemo(() => extractPayloadMetrics(crawler.heartbeat_payload), [crawler.heartbeat_payload]);
  const publicLink = crawler.public_slug ? buildPublicUrl(crawler.public_slug) : null;

  const handleTogglePublic = async () => {
    try {
      await updateCrawlerMutation.mutateAsync({ is_public: !crawler.is_public });
      toast({
        title: crawler.is_public ? "已取消公开" : "已开放公开页",
        description: crawler.name,
      });
    } catch (error) {
      toast({ title: "操作失败", description: getErrorMessage(error, "更新公开状态失败"), variant: "destructive" });
    }
  };

  const handleCopyPublicLink = () => {
    if (!publicLink) return;
    copyToClipboard(publicLink)
      .then((ok) => {
        if (ok) {
          toast({ title: "已复制公开地址", description: publicLink });
        } else {
          toast({ title: "复制失败", variant: "destructive" });
        }
      })
      .catch(() => toast({ title: "复制失败", variant: "destructive" }));
  };

  const statusStyle = crawler.status && STATUS_CARD_STYLE[crawler.status as StatusFilter];

  return (
    <article
      className={cn(
        "space-y-4 rounded-3xl border border-border/70 bg-card/80 p-5 shadow-panel transition hover:border-primary/60",
        statusStyle,
      )}
    >
      <header className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <CrawlerStatusBadge status={crawler.status} />
            <span className="text-xs text-muted-foreground">#{crawler.local_id}</span>
          </div>
          <h3 className="text-lg font-semibold text-foreground">{crawler.name}</h3>
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <LinkIcon className="h-3.5 w-3.5" />
            {crawler.api_key_name}
            {crawler.api_key_active === false ? <span className="rounded bg-rose-500/15 px-2 py-0.5 text-[10px] text-rose-500">Key 已禁用</span> : null}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href={`/dashboard/crawlers/${crawler.id}`} className="flex items-center gap-1">
              <ChevronRight className="h-4 w-4" /> 详情
            </Link>
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                {updateCrawlerMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <MoreVertical className="h-4 w-4" />}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuLabel>操作</DropdownMenuLabel>
              <DropdownMenuItem
                onSelect={(event) => {
                  event.preventDefault();
                  onCreateQuickLink?.(crawler);
                }}
              >
                <Globe className="mr-2 h-4 w-4" /> 创建公开页
              </DropdownMenuItem>
              {publicLink ? (
                <DropdownMenuItem
                  onSelect={(event) => {
                    event.preventDefault();
                    handleCopyPublicLink();
                  }}
                >
                  <Copy className="mr-2 h-4 w-4" /> 复制公开地址
                </DropdownMenuItem>
              ) : null}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onSelect={(event) => {
                  event.preventDefault();
                  handleTogglePublic();
                }}
              >
                {crawler.is_public ? (
                  <>
                    <ShieldOff className="mr-2 h-4 w-4" /> 关闭公开
                  </>
                ) : (
                  <>
                    <Shield className="mr-2 h-4 w-4" /> 设为公开
                  </>
                )}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
      <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground">
        <StatBlock label="最后心跳" value={`${formatRelativeTime(crawler.last_heartbeat)} · ${formatDateTime(crawler.last_heartbeat)}`} />
        <StatBlock label="最后来源 IP" value={crawler.last_source_ip ?? "未知"} />
        <StatBlock label="所在分组" value={crawler.group?.name ?? "未分组"} />
        <StatBlock label="可用性" value={formatUptime(crawler.uptime_ratio)} />
        <StatBlock label="心跳状态" value={crawler.status_changed_at ? `更新于 ${formatRelativeTime(crawler.status_changed_at)}` : "—"} />
        {crawler.config_assignment_name ? (
          <StatBlock label="配置指派" value={`${crawler.config_assignment_name} v${crawler.config_assignment_version ?? "-"}`} />
        ) : (
          <StatBlock label="配置指派" value="未指派" />
        )}
      </div>
      {metrics.length ? (
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground">最新指标</h4>
          <div className="grid gap-2 sm:grid-cols-2">
            {metrics.map((metric) => (
              <div key={metric.key} className="rounded-lg border border-border/60 bg-background/60 px-3 py-2 text-xs">
                <p className="text-muted-foreground">{metric.key}</p>
                <p className="mt-1 font-medium text-foreground">{metric.value}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {publicLink ? (
        <div className="flex items-center justify-between gap-2 rounded-2xl border border-emerald-500/50 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-600">
          <span className="truncate">公开地址：{publicLink}</span>
          <Button variant="ghost" size="icon" onClick={handleCopyPublicLink}>
            <Copy className="h-4 w-4" />
          </Button>
        </div>
      ) : null}
    </article>
  );
}

interface GroupCardProps {
  group: CrawlerGroup;
  crawlerCount: number;
  onEdit: () => void;
  onDelete: () => void;
}

function GroupCard({ group, crawlerCount, onEdit, onDelete }: GroupCardProps) {
  return (
    <div className="space-y-3 rounded-2xl border border-border/60 bg-card/70 p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: group.color ?? "#6366f1" }}
            />
            <p className="font-medium text-foreground">{group.name}</p>
          </div>
          <p className="text-xs text-muted-foreground">Slug：{group.slug}</p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={(event) => { event.preventDefault(); onEdit(); }}>
              <Edit className="mr-2 h-4 w-4" /> 编辑
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={(event) => { event.preventDefault(); onDelete(); }} className="text-destructive">
              <Trash2 className="mr-2 h-4 w-4" /> 删除
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs text-muted-foreground">关联爬虫</p>
          <p className="text-2xl font-semibold text-foreground">{crawlerCount}</p>
        </div>
        <div className="text-xs text-muted-foreground">
          创建于 {formatDateTime(group.created_at)}
        </div>
      </div>
      {group.description ? <p className="text-xs text-muted-foreground">{group.description}</p> : null}
    </div>
  );
}

interface StatBlockProps {
  label: string;
  value: string;
}

function StatBlock({ label, value }: StatBlockProps) {
  return (
    <div className="space-y-1">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-xs text-foreground">{value}</p>
    </div>
  );
}












