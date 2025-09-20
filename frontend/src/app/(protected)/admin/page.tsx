import { Skeleton } from "@/components/ui/skeleton";

export default function AdminPage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">后台管理</h1>
        <p className="text-sm text-muted-foreground">用户、邀请与注册策略将在这里维护。</p>
      </header>
      <div className="grid gap-6 md:grid-cols-2">
        <section className="space-y-3 rounded-2xl border border-border p-4 shadow-surface">
          <h2 className="text-sm font-semibold text-foreground">用户列表</h2>
          <Skeleton className="h-40 w-full" />
        </section>
        <section className="space-y-3 rounded-2xl border border-border p-4 shadow-surface">
          <h2 className="text-sm font-semibold text-foreground">邀请码</h2>
          <Skeleton className="h-40 w-full" />
        </section>
      </div>
    </section>
  );
}
