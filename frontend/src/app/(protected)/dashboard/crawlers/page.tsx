"use client";

import { useState } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link as LinkIcon, Plus, RefreshCcw, WifiOff } from "lucide-react";

import { useCrawlersQuery } from "@/features/crawlers/queries";
import { useRegisterCrawlerMutation } from "@/features/crawlers/mutations";
import { useToast } from "@/hooks/use-toast";
import type { ApiError } from "@/lib/api/client";
import { buildApiUrl } from "@/lib/env";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

const registerSchema = z.object({
  name: z.string().min(1, "请输入爬虫名称"),
  apiKey: z.string().min(1, "请输入有效的 API Key"),
});

type RegisterFormValues = z.infer<typeof registerSchema>;

export default function CrawlersPage() {
  const { toast } = useToast();
  const crawlersQuery = useCrawlersQuery();
  const registerMutation = useRegisterCrawlerMutation();
  const [isDialogOpen, setDialogOpen] = useState(false);

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
  });

  const handleRegister = async (values: RegisterFormValues) => {
    try {
      await registerMutation.mutateAsync(values);
      toast({ title: "爬虫已登记", description: values.name });
      setDialogOpen(false);
      form.reset();
    } catch (error) {
      toast({
        title: "登记失败",
        description: (error as ApiError)?.payload?.detail ?? "请核对 API Key 是否正确",
        variant: "destructive",
      });
    }
  };

  const crawlers = crawlersQuery.data ?? [];

  return (
    <div className="space-y-8">
      <section className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">爬虫资产</h1>
          <p className="text-sm text-muted-foreground">注册的爬虫、运行历史与心跳状态将展示在这里。</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => crawlersQuery.refetch()}
            disabled={crawlersQuery.isFetching}
          >
            <RefreshCcw className="mr-2 h-4 w-4" /> 刷新
          </Button>
          <Dialog open={isDialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="mr-2 h-4 w-4" /> 登记新爬虫
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>登记爬虫实例</DialogTitle>
              </DialogHeader>
              <form className="space-y-4" onSubmit={form.handleSubmit(handleRegister)}>
                <div className="space-y-2">
                  <Label htmlFor="name">爬虫名称</Label>
                  <Input id="name" placeholder="例如: weibo-spider" {...form.register("name")} />
                  {form.formState.errors.name ? (
                    <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
                  ) : null}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="apiKey">API Key</Label>
                  <Input id="apiKey" placeholder="在令牌管理页面复制" {...form.register("apiKey")} />
                  {form.formState.errors.apiKey ? (
                    <p className="text-xs text-destructive">{form.formState.errors.apiKey.message}</p>
                  ) : null}
                </div>
                <p className="text-xs text-muted-foreground">
                  登记成功后，可使用返回的爬虫 ID 结合 SDK 或 REST API 进行心跳上报和日志推送。
                </p>
                <DialogFooter>
                  <Button variant="outline" type="button" onClick={() => setDialogOpen(false)}>
                    取消
                  </Button>
                  <Button type="submit" disabled={registerMutation.isPending}>
                    {registerMutation.isPending ? "登记中..." : "确认登记"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-foreground">爬虫列表</h2>
          {crawlersQuery.isFetching && <SpinnerLabel label="刷新中" />}
        </div>
        {crawlersQuery.isLoading ? (
          <div className="grid gap-4 md:grid-cols-2">
            {[...Array(4)].map((_, index) => (
              <Skeleton key={index} className="h-32 rounded-2xl" />
            ))}
          </div>
        ) : crawlers.length === 0 ? (
          <div className="flex min-h-[200px] flex-col items-center justify-center gap-3 rounded-2xl border border-border/80 bg-muted/10">
            <WifiOff className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">尚未登记爬虫，点击右上角按钮创建吧。</p>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {crawlers.map((crawler) => (
              <article key={crawler.id} className="space-y-3 rounded-2xl border border-border/80 p-5 shadow-surface">
                <header className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-semibold text-foreground">{crawler.name}</h3>
                    <p className="text-xs text-muted-foreground">本地编号 #{crawler.local_id ?? "-"}</p>
                  </div>
                  {crawler.is_public && crawler.public_slug ? (
                    <a
                      href={buildApiUrl(`/pa/${crawler.public_slug}`)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200"
                    >
                      <LinkIcon className="h-3 w-3" /> 公开页面
                    </a>
                  ) : null}
                </header>
                <dl className="grid grid-cols-2 gap-3 text-xs text-muted-foreground">
                  <div>
                    <dt className="font-medium text-foreground">最后心跳</dt>
                    <dd>{crawler.last_heartbeat ? formatDateTime(crawler.last_heartbeat) : "无"}</dd>
                  </div>
                  <div>
                    <dt className="font-medium text-foreground">来源 IP</dt>
                    <dd>{crawler.last_source_ip ?? "未知"}</dd>
                  </div>
                  <div>
                    <dt className="font-medium text-foreground">创建时间</dt>
                    <dd>{formatDateTime(crawler.created_at)}</dd>
                  </div>
                  <div>
                    <dt className="font-medium text-foreground">公开状态</dt>
                    <dd>{crawler.is_public ? "对外可见" : "仅内部可见"}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function SpinnerLabel({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
      <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
      </svg>
      {label}
    </span>
  );
}
