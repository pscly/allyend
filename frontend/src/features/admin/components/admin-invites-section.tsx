"use client";

import { useMemo, useState } from "react";
import { CalendarClock, Copy, Plus, Shield, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminInvitesQuery, useAdminGroupsQuery } from "@/features/admin/queries";
import { useCreateInviteMutation, useDeleteInviteMutation } from "@/features/admin/mutations";
import { useToast } from "@/hooks/use-toast";
import { ApiError } from "@/lib/api/client";
import type { InviteCode, UserGroup } from "@/lib/api/types";
import { copyToClipboard } from "@/lib/clipboard";

interface InviteFormState {
  note: string;
  allowAdmin: boolean;
  maxUses: string;
  expiresInMinutes: string;
  targetGroupId: string;
}

const INITIAL_FORM: InviteFormState = {
  note: "",
  allowAdmin: false,
  maxUses: "",
  expiresInMinutes: "",
  targetGroupId: "",
};

function formatDateTime(value: string | null) {
  if (!value) {
    return "长期有效";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatUsage(invite: InviteCode) {
  if (invite.max_uses === null) {
    return `${invite.used_count} / ∞`;
  }
  return `${invite.used_count} / ${invite.max_uses}`;
}

function parsePositiveInt(value: string, field: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`${field} 请输入大于 0 的整数`);
  }
  return Math.floor(parsed);
}

export function AdminInvitesSection() {
  const { toast } = useToast();
  const invitesQuery = useAdminInvitesQuery();
  const groupsQuery = useAdminGroupsQuery();
  const createInvite = useCreateInviteMutation();
  const deleteInvite = useDeleteInviteMutation();

  const [formState, setFormState] = useState<InviteFormState>(INITIAL_FORM);
  const [open, setOpen] = useState(false);

  const invites = invitesQuery.data ?? [];
  const groups = useMemo<UserGroup[]>(() => groupsQuery.data ?? [], [groupsQuery.data]);

  const resetForm = () => setFormState(INITIAL_FORM);

  const handleSubmit = async () => {
    try {
      const payload = {
        note: formState.note.trim() || null,
        allowAdmin: formState.allowAdmin,
        maxUses: parsePositiveInt(formState.maxUses, "可用次数") ?? null,
        expiresInMinutes: parsePositiveInt(formState.expiresInMinutes, "有效期") ?? null,
        targetGroupId: formState.targetGroupId ? Number(formState.targetGroupId) : null,
      };

      if (payload.targetGroupId !== null) {
        const exists = groups.some((group) => group.id === payload.targetGroupId);
        if (!exists) {
          throw new Error("请选择有效的用户组");
        }
      }

      await createInvite.mutateAsync(payload);
      toast({ title: "邀请码已生成" });
      resetForm();
      setOpen(false);
    } catch (error) {
      const message = error instanceof ApiError ? error.payload?.detail ?? "创建失败" : (error as Error).message;
      toast({ title: "操作失败", description: message, variant: "destructive" });
    }
  };

  const handleDelete = async (invite: InviteCode) => {
    const confirmed = window.confirm(`确定要删除邀请码 ${invite.code} 吗？`);
    if (!confirmed) {
      return;
    }
    try {
      await deleteInvite.mutateAsync(invite.id);
      toast({ title: "邀请码已删除", description: invite.code });
    } catch (error) {
      const message = error instanceof ApiError ? error.payload?.detail ?? "删除失败" : "删除失败";
      toast({ title: "操作失败", description: message, variant: "destructive" });
    }
  };

  return (
    <section className="space-y-4 rounded-3xl border border-border/60 bg-card/70 p-6 shadow-surface">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
            <Shield className="h-5 w-5 text-primary" /> 邀请码管理
          </h2>
          <p className="text-sm text-muted-foreground">生成新的邀请码，或管理既有凭证与使用权限。</p>
        </div>
        <Dialog open={open} onOpenChange={(next) => { if (!next) resetForm(); setOpen(next); }}>
          <DialogTrigger asChild>
            <Button size="sm" className="gap-2">
              <Plus className="h-4 w-4" /> 新建邀请码
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-xl">
            <DialogHeader>
              <DialogTitle>创建邀请码</DialogTitle>
              <DialogDescription>可配置使用次数、有效期与默认加入的用户组。</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="note">备注</Label>
                <Input
                  id="note"
                  placeholder="仅内部可见，如：数据团队"
                  value={formState.note}
                  onChange={(event) => setFormState((prev) => ({ ...prev, note: event.target.value }))}
                  maxLength={80}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="group">默认加入用户组</Label>
                <select
                  id="group"
                  className="h-10 rounded-lg border border-border/70 bg-background px-3 text-sm"
                  value={formState.targetGroupId}
                  onChange={(event) => setFormState((prev) => ({ ...prev, targetGroupId: event.target.value }))}
                >
                  <option value="">不指定</option>
                  {groups.map((group) => (
                    <option key={group.id} value={group.id}>
                      {group.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="maxUses">最大使用次数</Label>
                  <Input
                    id="maxUses"
                    type="number"
                    min={1}
                    placeholder="留空为不限"
                    value={formState.maxUses}
                    onChange={(event) => setFormState((prev) => ({ ...prev, maxUses: event.target.value }))}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="expires">有效期（分钟）</Label>
                  <Input
                    id="expires"
                    type="number"
                    min={1}
                    placeholder="留空为不限"
                    value={formState.expiresInMinutes}
                    onChange={(event) => setFormState((prev) => ({ ...prev, expiresInMinutes: event.target.value }))}
                  />
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border border-border/70"
                  checked={formState.allowAdmin}
                  onChange={(event) => setFormState((prev) => ({ ...prev, allowAdmin: event.target.checked }))}
                />
                允许注册为管理员
              </label>
            </div>
            <DialogFooter>
              <Button
                variant="ghost"
                onClick={() => {
                  resetForm();
                  setOpen(false);
                }}
              >
                取消
              </Button>
              <Button onClick={handleSubmit} disabled={createInvite.isPending}>
                {createInvite.isPending ? "创建中..." : "确认创建"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </header>

      <div className="overflow-hidden rounded-2xl border border-border/60">
        <table className="w-full table-auto text-sm">
          <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-4 py-3 font-medium">邀请码</th>
              <th className="px-4 py-3 font-medium">备注</th>
              <th className="px-4 py-3 font-medium">使用情况</th>
              <th className="px-4 py-3 font-medium">有效期</th>
              <th className="px-4 py-3 text-right font-medium">操作</th>
            </tr>
          </thead>
          <tbody className="bg-card/40">
            {invitesQuery.isLoading ? (
              [...Array(3)].map((_, index) => (
                <tr key={index} className="border-t border-border/50">
                  {Array.from({ length: 5 }).map((__, cell) => (
                    <td key={cell} className="px-4 py-4">
                      <Skeleton className="h-4 w-24" />
                    </td>
                  ))}
                </tr>
              ))
            ) : invites.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-sm text-muted-foreground">
                  暂无邀请码，请先创建。
                </td>
              </tr>
            ) : (
              invites.map((invite) => (
                <tr key={invite.id} className="border-t border-border/50">
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2">
                      <code className="rounded-full bg-muted px-3 py-1 text-xs font-medium">{invite.code}</code>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => { void copyToClipboard(invite.code); }}
                        title="复制邀请码"
                      >
                        <Copy className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                    {invite.allow_admin && (
                      <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-1 text-[11px] font-medium text-amber-600 dark:bg-amber-400/20 dark:text-amber-100">
                        <Shield className="h-3 w-3" /> 可注册管理员
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-4 text-sm text-muted-foreground">{invite.note ?? "-"}</td>
                  <td className="px-4 py-4 text-sm text-muted-foreground">{formatUsage(invite)}</td>
                  <td className="px-4 py-4 text-sm text-muted-foreground">
                    <div className="flex items-center gap-2">
                      <CalendarClock className="h-4 w-4 text-primary" />
                      {formatDateTime(invite.expires_at)}
                    </div>
                  </td>
                  <td className="px-4 py-4 text-right">
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1 text-destructive"
                      disabled={deleteInvite.isPending}
                      onClick={() => {
                        void handleDelete(invite);
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5" /> 删除
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {(invitesQuery.isError || createInvite.isError) && (
        <p className="text-xs text-destructive">
          {(invitesQuery.error as ApiError | undefined)?.payload?.detail ?? "操作异常，请稍后再试。"}
        </p>
      )}
    </section>
  );
}
