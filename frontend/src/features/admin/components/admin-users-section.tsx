"use client";

import { CheckCircle2, MoreHorizontal, ShieldAlert, ShieldCheck, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminUsersQuery, useAdminGroupsQuery } from "@/features/admin/queries";
import { useUpdateAdminUserMutation } from "@/features/admin/mutations";
import { useToast } from "@/hooks/use-toast";
import { ApiError } from "@/lib/api/client";
import type { AdminUserRole, AdminUserSummary } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";

const ROLE_LABEL: Record<AdminUserRole, string> = {
  superadmin: "超级管理员",
  admin: "管理员",
  user: "普通用户",
};

const ROLE_DESCRIPTION: Record<AdminUserRole, string> = {
  superadmin: "拥有全部权限，可管理其他管理员",
  admin: "可管理系统资源与成员",
  user: "普通成员，拥有基础权限",
};

function formatDateTime(value: string) {
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

function statusBadge(active: boolean) {
  return active
    ? "inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2.5 py-1 text-xs font-medium text-emerald-600 dark:bg-emerald-400/15 dark:text-emerald-200"
    : "inline-flex items-center gap-1 rounded-full bg-rose-500/15 px-2.5 py-1 text-xs font-medium text-rose-600 dark:bg-rose-400/15 dark:text-rose-200";
}

function roleBadge(role: AdminUserRole) {
  switch (role) {
    case "superadmin":
      return "inline-flex items-center gap-1 rounded-full bg-purple-500/15 px-2.5 py-1 text-xs font-medium text-purple-600 dark:bg-purple-400/15 dark:text-purple-200";
    case "admin":
      return "inline-flex items-center gap-1 rounded-full bg-sky-500/15 px-2.5 py-1 text-xs font-medium text-sky-600 dark:bg-sky-400/15 dark:text-sky-200";
    default:
      return "inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground";
  }
}

interface GroupLookup {
  id: number;
  name: string;
}

export function AdminUsersSection() {
  const { toast } = useToast();
  const currentUser = useAuthStore((state) => state.profile);
  const usersQuery = useAdminUsersQuery();
  const groupsQuery = useAdminGroupsQuery();
  const updateUser = useUpdateAdminUserMutation();

  const groups = groupsQuery.data ?? [];
  const users = usersQuery.data ?? [];
  const isSuperAdmin = currentUser?.role === "superadmin";

  const groupLookup: GroupLookup[] = groups.map((group) => ({ id: group.id, name: group.name } satisfies GroupLookup));

  const handleError = (error: unknown, fallback: string) => {
    const message = error instanceof ApiError ? error.payload?.detail ?? fallback : fallback;
    toast({ title: "操作失败", description: message, variant: "destructive" });
  };

  const handleToggleActive = async (user: AdminUserSummary) => {
    if (user.is_root_admin && !isSuperAdmin) {
      toast({ title: "权限不足", description: "无法修改根管理员状态", variant: "destructive" });
      return;
    }
    try {
      await updateUser.mutateAsync({ userId: user.id, isActive: !user.is_active });
      toast({ title: user.is_active ? "已停用" : "已启用", description: user.username });
    } catch (error) {
      handleError(error, "请稍后重试");
    }
  };

  const handleRoleChange = async (user: AdminUserSummary, role: AdminUserRole) => {
    if (user.role === role) {
      return;
    }
    if (!isSuperAdmin && role === "superadmin") {
      toast({ title: "权限不足", description: "仅超级管理员可授予该角色", variant: "destructive" });
      return;
    }
    if (user.is_root_admin && !isSuperAdmin) {
      toast({ title: "权限不足", description: "无法调整根管理员角色", variant: "destructive" });
      return;
    }
    try {
      await updateUser.mutateAsync({ userId: user.id, role });
      toast({ title: "角色已更新", description: `${user.username} → ${ROLE_LABEL[role]}` });
    } catch (error) {
      handleError(error, "角色更新失败");
    }
  };

  const handleGroupChange = async (user: AdminUserSummary, groupId: number | null) => {
    if (user.group?.id === groupId) {
      return;
    }
    try {
      await updateUser.mutateAsync({ userId: user.id, groupId });
      const label = groupId ? groups.find((group) => group.id === groupId)?.name ?? "目标用户组" : "未分组";
      toast({ title: "用户组已调整", description: `${user.username} → ${label}` });
    } catch (error) {
      handleError(error, "用户组调整失败");
    }
  };

  return (
    <section className="space-y-4 rounded-3xl border border-border/70 bg-card/70 p-6 shadow-panel">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
            <Users className="h-5 w-5 text-primary" /> 成员管理
          </h2>
          <p className="text-sm text-muted-foreground">查看成员状态、快速调整角色与归属用户组。</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {usersQuery.isFetching && <span className="animate-pulse">正在同步...</span>}
          <span>共 {users.length} 人</span>
        </div>
      </header>

      <div className="overflow-hidden rounded-2xl border border-border/60">
        <table className="w-full min-w-[720px] table-auto">
          <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-5 py-3 font-medium">用户</th>
              <th className="px-5 py-3 font-medium">角色</th>
              <th className="px-5 py-3 font-medium">所属用户组</th>
              <th className="px-5 py-3 font-medium">状态</th>
              <th className="px-5 py-3 font-medium">邀请人</th>
              <th className="px-5 py-3 font-medium">注册时间</th>
              <th className="px-5 py-3 text-right font-medium">操作</th>
            </tr>
          </thead>
          <tbody className="bg-card/30 text-sm">
            {usersQuery.isLoading ? (
              [...Array(5)].map((_, index) => (
                <tr key={index} className="border-t border-border/50">
                  {Array.from({ length: 7 }).map((__, cell) => (
                    <td key={cell} className="px-5 py-4">
                      <Skeleton className="h-4 w-28" />
                    </td>
                  ))}
                </tr>
              ))
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-5 py-8 text-center text-sm text-muted-foreground">
                  暂无用户数据。
                </td>
              </tr>
            ) : (
              users.map((user) => (
                <tr key={user.id} className="border-t border-border/50">
                  <td className="px-5 py-4">
                    <div className="space-y-1">
                      <p className="font-medium text-foreground">{user.username}</p>
                      <p className="text-xs text-muted-foreground">ID：{user.id}</p>
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className={cn(
                            "group w-full justify-start gap-2 rounded-full border border-border/60 bg-background/80 px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-primary/10",
                            updateUser.isPending && "pointer-events-none opacity-70",
                          )}
                        >
                          <span className={roleBadge(user.role)}>
                            {user.role === "superadmin" ? <CrownIcon /> : <ShieldCheck className="h-3.5 w-3.5" />} {ROLE_LABEL[user.role]}
                          </span>
                          <MoreHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start" className="w-56">
                        <DropdownMenuLabel>调整角色</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        {(Object.keys(ROLE_LABEL) as AdminUserRole[]).map((role) => (
                          <DropdownMenuItem
                            key={role}
                            disabled={
                              updateUser.isPending ||
                              user.role === role ||
                              (!isSuperAdmin && role === "superadmin") ||
                              (user.is_root_admin && !isSuperAdmin)
                            }
                            onSelect={() => {
                              void handleRoleChange(user, role);
                            }}
                          >
                            <div className="flex flex-col">
                              <span className="text-sm text-foreground">{ROLE_LABEL[role]}</span>
                              <span className="text-xs text-muted-foreground">{ROLE_DESCRIPTION[role]}</span>
                            </div>
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </td>
                  <td className="px-5 py-4">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className={cn(
                            "w-full justify-start rounded-full border border-border/60 bg-background/80 px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-primary/10",
                            updateUser.isPending && "pointer-events-none opacity-70",
                          )}
                        >
                          {user.group ? user.group.name : "未分组"}
                          <MoreHorizontal className="ml-2 h-3.5 w-3.5 text-muted-foreground" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start" className="w-52">
                        <DropdownMenuLabel>选择用户组</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          disabled={updateUser.isPending || user.group === null}
                          onSelect={() => {
                            void handleGroupChange(user, null);
                          }}
                        >
                          未分组
                        </DropdownMenuItem>
                        {groupLookup.map((group) => (
                          <DropdownMenuItem
                            key={group.id}
                            disabled={updateUser.isPending || user.group?.id === group.id}
                            onSelect={() => {
                              void handleGroupChange(user, group.id);
                            }}
                          >
                            {group.name}
                          </DropdownMenuItem>
                        ))}
                        {groupLookup.length === 0 && (
                          <DropdownMenuItem disabled>暂无可用用户组</DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </td>
                  <td className="px-5 py-4">
                    <span className={statusBadge(user.is_active)}>
                      {user.is_active ? (
                        <>
                          <CheckCircle2 className="h-3.5 w-3.5" /> 正常
                        </>
                      ) : (
                        <>
                          <ShieldAlert className="h-3.5 w-3.5" /> 停用
                        </>
                      )}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-sm text-muted-foreground">{user.invited_by ?? "-"}</td>
                  <td className="px-5 py-4 text-sm text-muted-foreground">{formatDateTime(user.created_at)}</td>
                  <td className="px-5 py-4 text-right">
                    <Button
                      variant={user.is_active ? "outline" : "default"}
                      size="sm"
                      disabled={updateUser.isPending || (user.is_root_admin && !isSuperAdmin)}
                      onClick={() => {
                        void handleToggleActive(user);
                      }}
                    >
                      {user.is_active ? "停用" : "启用"}
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {usersQuery.isError && (
        <p className="text-xs text-destructive">
          加载用户列表失败：{(usersQuery.error as ApiError)?.payload?.detail ?? "请稍后重试"}
        </p>
      )}
    </section>
  );
}

function CrownIcon() {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      className="h-3.5 w-3.5"
      viewBox="0 0 24 24"
      fill="currentColor"
    >
      <path d="M5 19h14l1-10-4.5 3.5L12 5 8.5 12.5 4 9z" />
    </svg>
  );
}



