"use client";

import { useEffect } from "react";
import { ShieldCheck, Users, KeySquare, Settings2 } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuthStore } from "@/store/auth-store";

/**
 * /admin 作为“仿真后台”入口：
 * - 管理员/超级管理员：自动跳转到真实后台 /hjxgl
 * - 非管理员：展示与后台相似的只读界面，控件禁用、不触发真实请求
 */
export default function AdminEntryPage() {
  const router = useRouter();
  const profile = useAuthStore((s) => s.profile);

  useEffect(() => {
    if (profile && (profile.role === "admin" || profile.role === "superadmin")) {
      router.replace("/hjxgl");
    }
  }, [profile, router]);

  const fakeUsers = [
    { id: 101, username: "alice", role: "user", group: "默认组", is_active: true, created_at: "2025-09-01 10:12" },
    { id: 102, username: "admin", role: "user", group: "管理员", is_active: true, created_at: "2025-09-10 09:20" },
    { id: 103, username: "aaaa", role: "user", group: "运营", is_active: false, created_at: "2025-09-20 18:42" },
  ] as const;

  const fakeInvites = [
    { code: "v7gKQ1xA", note: "运营团队", allow_admin: false, limit: "2/5", expire: "2025-10-31 23:59" },
    { code: "cJ9Pz3LM", note: "测试账号", allow_admin: false, limit: "1/3", expire: "永久有效" },
    { code: "mH2tN0Wd", note: "临时协作", allow_admin: true, limit: "0/1", expire: "2025-09-30 12:00" },
  ] as const;

  return (
    <section className="space-y-8">
      <header className="space-y-3">
        <span className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
          <ShieldCheck className="h-4 w-4" /> 系统控制中心
        </span>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">后台管理</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          统一管理成员、注册策略与授权。当前为概览视图，部分功能暂不可用。
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-[1.1fr_1fr]">
        {/* 注册策略（只读外观） */}
        <section className="space-y-4 rounded-lg border border-border/50 bg-card p-5">
          <div className="flex items-center gap-2 text-foreground">
            <Settings2 className="h-4 w-4" />
            <h2 className="text-base font-semibold">注册策略</h2>
          </div>
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">当前模式</span>
              <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground">仅限邀请码</span>
            </div>
            <div className="flex items-center gap-2">
              <Button size="sm"  variant="secondary">保存</Button>
            </div>
          </div>
        </section>

        {/* 邀请码管理（仿真数据） */}
        <section className="space-y-4 rounded-lg border border-border/50 bg-card p-5">
          <div className="flex items-center gap-2 text-foreground">
            <KeySquare className="h-4 w-4" />
            <h2 className="text-base font-semibold">邀请码管理</h2>
          </div>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Button size="sm" >生成邀请码</Button>
              <Button size="sm" variant="secondary" disabled>
                刷新
              </Button>
              <span className="text-xs text-muted-foreground"></span>
            </div>
            <div className="overflow-hidden rounded-md border border-border/60">
              <div className="grid grid-cols-6 gap-0 border-b border-border/60 bg-muted/40 p-3 text-xs text-muted-foreground">
                <span>邀请码</span>
                <span>说明</span>
                <span>管理员</span>
                <span>使用情况</span>
                <span>过期时间</span>
                <span>操作</span>
              </div>
              <div className="divide-y divide-border/60">
                {fakeInvites.map((it) => (
                  <div key={it.code} className="grid grid-cols-6 items-center gap-0 p-3 text-sm">
                    <code className="font-mono text-xs">{it.code}</code>
                    <span className="text-foreground/90">{it.note}</span>
                    <span className="text-muted-foreground">{it.allow_admin ? "是" : "否"}</span>
                    <span className="text-muted-foreground">{it.limit}</span>
                    <span className="text-muted-foreground">{it.expire}</span>
                    <div className="text-right">
                      <Button size="sm" variant="ghost" disabled>
                        删除
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* 用户与分组（仿真数据） */}
      <section className="space-y-4 rounded-lg border border-border/50 bg-card p-5">
        <div className="flex items-center gap-2 text-foreground">
          <Users className="h-4 w-4" />
          <h2 className="text-base font-semibold">成员与分组</h2>
        </div>
        <div className="overflow-hidden rounded-md border border-border/60">
          <div className="grid grid-cols-6 gap-0 border-b border-border/60 bg-muted/40 p-3 text-xs text-muted-foreground">
            <span>ID</span>
            <span>用户名</span>
            <span>角色</span>
            <span>分组</span>
            <span>状态</span>
            <span>创建时间</span>
          </div>
          <div className="divide-y divide-border/60">
            {fakeUsers.map((u) => (
              <div key={u.id} className="grid grid-cols-6 items-center gap-0 p-3 text-sm">
                <span className="text-muted-foreground">{u.id}</span>
                <span className="text-foreground/90">{u.username}</span>
                <span className="text-muted-foreground">{u.role === "user" ? "普通用户" : u.role}</span>
                <span className="text-muted-foreground">{u.group}</span>
                <span className="text-muted-foreground">{u.is_active ? "正常" : "停用"}</span>
                <span className="text-muted-foreground">{u.created_at}</span>
              </div>
            ))}
          </div>
        </div>
        <p className="text-xs text-muted-foreground">别看了，你没有管理员权限……</p>
      </section>
    </section>
  );
}
