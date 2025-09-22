const STATUS_TEXT: Record<string, string> = {
  online: "在线",
  warning: "警告",
  offline: "离线",
};

const STATUS_COLOR: Record<string, string> = {
  online: "bg-emerald-500",
  warning: "bg-amber-500",
  offline: "bg-rose-500",
};

export function CrawlerStatusBadge({ status }: { status?: string }) {
  const safeStatus = status ?? "offline";
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
      <span className={`h-2 w-2 rounded-full ${STATUS_COLOR[safeStatus] ?? "bg-muted-foreground"}`} />
      {STATUS_TEXT[safeStatus] ?? safeStatus}
    </span>
  );
}
