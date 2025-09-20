export default function DashboardPage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">概览</h1>
        <p className="text-sm text-muted-foreground">
          登录后这里将展示文件统计、爬虫运行情况等核心指标。
        </p>
      </header>
      <div className="grid gap-4 md:grid-cols-3">
        <PlaceholderCard title="文件总量" description="后续接入后端数据" />
        <PlaceholderCard title="活跃爬虫" description="后续接入后端数据" />
        <PlaceholderCard title="最近审计" description="后续接入后端数据" />
      </div>
    </section>
  );
}

interface PlaceholderCardProps {
  title: string;
  description: string;
}

function PlaceholderCard({ title, description }: PlaceholderCardProps) {
  return (
    <div className="rounded-2xl border border-border/80 bg-card/80 p-6 shadow-panel">
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-2 text-xs text-muted-foreground">{description}</p>
    </div>
  );
}
