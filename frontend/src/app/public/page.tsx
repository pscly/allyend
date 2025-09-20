import { AppShell } from "@/components/layout/app-shell";
import { Skeleton } from "@/components/ui/skeleton";

export default function PublicPage() {
  return (
    <AppShell className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">公开资源</h1>
        <p className="text-sm text-muted-foreground">对外开放的 API Key 与爬虫链接将在这里呈现。</p>
      </header>
      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-2xl border border-border p-4 shadow-surface">
          <h2 className="text-sm font-medium text-foreground">公开 API Key</h2>
          <Skeleton className="mt-3 h-24 w-full" />
        </section>
        <section className="rounded-2xl border border-border p-4 shadow-surface">
          <h2 className="text-sm font-medium text-foreground">公开爬虫链接</h2>
          <Skeleton className="mt-3 h-24 w-full" />
        </section>
      </div>
    </AppShell>
  );
}
