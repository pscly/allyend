"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Download, RefreshCcw, ShieldCheck, Upload } from "lucide-react";

import { useMyFilesQuery, useFileTokensQuery } from "@/features/files/queries";
import {
  useUploadFileMutation,
  useDeleteFileMutation,
  useCreateTokenMutation,
  useUpdateTokenMutation,
} from "@/features/files/mutations";
import { useToast } from "@/hooks/use-toast";
import type { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import { buildApiUrl } from "@/lib/env";
import { cn } from "@/lib/utils";
import { copyToClipboard } from "@/lib/clipboard";
import { Button, buttonVariants } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

const uploadSchema = z.object({
  file: z.instanceof(File, { message: "请选择需要上传的文件" }),
  fileName: z.string().optional(),
  description: z.string().optional(),
  visibility: z.enum(["private", "group", "public", "disabled"]).default("private"),
});

const tokenSchema = z.object({
  token: z.string().trim().optional(),
  name: z.string().trim().optional(),
  description: z.string().trim().optional(),
  allowedIps: z.string().trim().optional(),
  allowedCidrs: z.string().trim().optional(),
});

type UploadFormValues = z.infer<typeof uploadSchema>;
type TokenFormValues = z.infer<typeof tokenSchema>;

type VisibilityOption = {
  value: "private" | "group" | "public" | "disabled";
  label: string;
  description: string;
};

const VISIBILITY_OPTIONS: VisibilityOption[] = [
  { value: "private", label: "仅自己", description: "只有自己可见，最安全" },
  { value: "group", label: "用户组", description: "同组成员可见" },
  { value: "public", label: "公开", description: "任何人可下载" },
  { value: "disabled", label: "停用", description: "临时隐藏文件" },
];

export default function FilesPage() {
  const { toast } = useToast();
  const filesQuery = useMyFilesQuery();
  const tokensQuery = useFileTokensQuery();

  const uploadMutation = useUploadFileMutation();
  const deleteMutation = useDeleteFileMutation();
  const createTokenMutation = useCreateTokenMutation();
  const updateTokenMutation = useUpdateTokenMutation();

  const [isUploadOpen, setUploadOpen] = useState(false);
  const [isTokenOpen, setTokenOpen] = useState(false);

  const uploadForm = useForm<UploadFormValues>({
    resolver: zodResolver(uploadSchema),
    defaultValues: {
      visibility: "private",
    },
  });

  const tokenForm = useForm<TokenFormValues>({
    resolver: zodResolver(tokenSchema),
  });

  const handleUpload = async (values: UploadFormValues) => {
    try {
      await uploadMutation.mutateAsync(values);
      toast({ title: "上传成功", description: values.fileName ?? values.file.name });
      setUploadOpen(false);
      uploadForm.reset({ visibility: values.visibility });
    } catch (error) {
      toast({
        title: "上传失败",
        description: (error as ApiError)?.payload?.detail ?? "请稍后重试",
        variant: "destructive",
      });
    }
  };

  const handleCreateToken = async (values: TokenFormValues) => {
    try {
      await createTokenMutation.mutateAsync(values);
      toast({ title: "令牌已创建" });
      setTokenOpen(false);
      tokenForm.reset();
    } catch (error) {
      toast({
        title: "创建失败",
        description: (error as ApiError)?.payload?.detail ?? "请稍后重试",
        variant: "destructive",
      });
    }
  };

  const handleToggleToken = async (tokenId: number, active: boolean) => {
    try {
      await updateTokenMutation.mutateAsync({ tokenId, isActive: !active });
      toast({ title: !active ? "令牌已启用" : "令牌已禁用" });
    } catch (error) {
      toast({
        title: "操作失败",
        description: (error as ApiError)?.payload?.detail ?? "请稍后再试",
        variant: "destructive",
      });
    }
  };

  const handleDeleteFile = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id);
      toast({ title: "文件已删除" });
    } catch (error) {
      toast({
        title: "删除失败",
        description: (error as ApiError)?.payload?.detail ?? "请稍后再试",
        variant: "destructive",
      });
    }
  };

  const files = filesQuery.data ?? [];
  const tokens = tokensQuery.data ?? [];

  return (
    <div className="space-y-8">
      <section className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">我的文件</h1>
          <p className="text-sm text-muted-foreground">上传记录、快速下载与令牌管理位于此处。</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              filesQuery.refetch();
              tokensQuery.refetch();
            }}
            disabled={filesQuery.isFetching || tokensQuery.isFetching}
          >
            <RefreshCcw className="mr-2 h-4 w-4" /> 刷新
          </Button>
          <Dialog open={isTokenOpen} onOpenChange={setTokenOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                <ShieldCheck className="mr-2 h-4 w-4" /> 新建上传令牌
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>创建上传令牌</DialogTitle>
              </DialogHeader>
              <form
                className="space-y-4"
                onSubmit={tokenForm.handleSubmit(handleCreateToken)}
              >
                <div className="space-y-2">
                  <Label htmlFor="token">令牌编号（可选）</Label>
                  <Input id="token" placeholder="自定义后缀，自动补齐 up-" {...tokenForm.register("token")} />
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="name">名称</Label>
                    <Input id="name" placeholder="展示名称" {...tokenForm.register("name")} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="allowedIps">IP 白名单</Label>
                    <Input id="allowedIps" placeholder="127.0.0.1,192.168.1.2" {...tokenForm.register("allowedIps")} />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="allowedCidrs">CIDR 白名单</Label>
                  <Input id="allowedCidrs" placeholder="10.0.0.0/24,2001:db8::/32" {...tokenForm.register("allowedCidrs")} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="description">描述</Label>
                  <textarea
                    id="description"
                    className="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    placeholder="为该令牌添加备注"
                    {...tokenForm.register("description")}
                  />
                </div>
                <DialogFooter>
                  <Button variant="outline" type="button" onClick={() => setTokenOpen(false)}>
                    取消
                  </Button>
                  <Button type="submit" disabled={createTokenMutation.isPending}>
                    {createTokenMutation.isPending ? "创建中..." : "确认创建"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
          <Dialog open={isUploadOpen} onOpenChange={setUploadOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Upload className="mr-2 h-4 w-4" /> 上传文件
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>上传文件</DialogTitle>
              </DialogHeader>
              <form className="space-y-4" onSubmit={uploadForm.handleSubmit(handleUpload)}>
                <div className="space-y-2">
                  <Label htmlFor="file">选择文件</Label>
                  <Input
                    id="file"
                    type="file"
                    accept="*/*"
                    onChange={(event) => {
                      const [selected] = event.target.files ?? [];
                      uploadForm.setValue("file", selected as File, { shouldValidate: true });
                    }}
                  />
                  {uploadForm.formState.errors.file ? (
                    <p className="text-xs text-destructive">{uploadForm.formState.errors.file.message}</p>
                  ) : null}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="fileName">文件名（可选）</Label>
                  <Input id="fileName" placeholder="默认为原始文件名" {...uploadForm.register("fileName")} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="description">描述</Label>
                  <textarea
                    id="description"
                    className="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    placeholder="为文件添加备注"
                    {...uploadForm.register("description")}
                  />
                </div>
                <div className="space-y-3">
                  <Label>可见性</Label>
                  <div className="grid gap-2">
                    {VISIBILITY_OPTIONS.map((option) => (
                      <label
                        key={option.value}
                        className={cn(
                          "flex cursor-pointer items-start gap-3 rounded-lg border border-border/80 p-3 text-sm hover:bg-muted/40",
                          uploadForm.watch("visibility") === option.value && "border-primary bg-primary/5 text-primary",
                        )}
                      >
                        <input
                          type="radio"
                          className="mt-1 h-3.5 w-3.5"
                          value={option.value}
                          checked={uploadForm.watch("visibility") === option.value}
                          onChange={() => uploadForm.setValue("visibility", option.value)}
                        />
                        <span>
                          <span className="font-medium text-foreground">{option.label}</span>
                          <span className="ml-2 text-xs text-muted-foreground">{option.description}</span>
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" type="button" onClick={() => setUploadOpen(false)}>
                    取消
                  </Button>
                  <Button type="submit" disabled={uploadMutation.isPending}>
                    {uploadMutation.isPending ? "上传中..." : "开始上传"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-foreground">文件列表</h2>
          {filesQuery.isFetching && <SpinnerLabel label="刷新中" />}
        </div>
        <div className="overflow-hidden rounded-2xl border border-border/80">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/40 text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">文件名</th>
                <th className="px-4 py-3 font-medium">大小</th>
                <th className="px-4 py-3 font-medium">可见性</th>
                <th className="px-4 py-3 font-medium">上传时间</th>
                <th className="px-4 py-3 font-medium text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {filesQuery.isLoading ? (
                [...Array(5)].map((_, index) => (
                  <tr key={index} className="border-t border-border/70">
                    <td className="px-4 py-4"><Skeleton className="h-4 w-48" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-16" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-20" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-32" /></td>
                    <td className="px-4 py-4 text-right"><Skeleton className="ml-auto h-8 w-24" /></td>
                  </tr>
                ))
              ) : files.length === 0 ? (
                <tr>
                  <td className="px-4 py-10 text-center text-sm text-muted-foreground" colSpan={5}>
                    暂无文件，点击右上角“上传文件”开始吧。
                  </td>
                </tr>
              ) : (
                files.map((file) => (
                  <tr key={file.id} className="border-t border-border/70">
                    <td className="px-4 py-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-foreground">{file.original_name}</span>
                          <a
                            href={buildApiUrl(endpoints.files.downloadFile(file.id))}
                            className={cn(
                              "inline-flex items-center gap-1 text-xs text-primary hover:underline",
                              buttonVariants({ variant: "ghost" }),
                            )}
                          >
                            <Download className="h-3 w-3" /> 下载
                          </a>
                        </div>
                        {file.description ? (
                          <p className="text-xs text-muted-foreground">{file.description}</p>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">{formatBytes(file.size_bytes)}</td>
                    <td className="px-4 py-3">
                      <span className={cn(
                        "inline-flex items-center rounded-full px-2 py-1 text-xs font-medium",
                        visibilityBadgeClass(file.visibility),
                      )}>
                        {visibilityLabel(file.visibility)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">{formatDateTime(file.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive"
                        onClick={() => handleDeleteFile(file.id)}
                        disabled={deleteMutation.isPending}
                      >
                        删除
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-foreground">上传令牌</h2>
          {tokensQuery.isFetching && <SpinnerLabel label="刷新中" />}
        </div>
        <div className="overflow-hidden rounded-2xl border border-border/80">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/40 text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">令牌</th>
                <th className="px-4 py-3 font-medium">备注</th>
                <th className="px-4 py-3 font-medium">限制</th>
                <th className="px-4 py-3 font-medium">最近使用</th>
                <th className="px-4 py-3 font-medium text-right">状态</th>
              </tr>
            </thead>
            <tbody>
              {tokensQuery.isLoading ? (
                [...Array(3)].map((_, index) => (
                  <tr key={index} className="border-t border-border/70">
                    <td className="px-4 py-4"><Skeleton className="h-4 w-40" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-32" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-48" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-32" /></td>
                    <td className="px-4 py-4 text-right"><Skeleton className="ml-auto h-8 w-20" /></td>
                  </tr>
                ))
              ) : tokens.length === 0 ? (
                <tr>
                  <td className="px-4 py-8 text-center text-sm text-muted-foreground" colSpan={5}>
                    当前尚未创建令牌。
                  </td>
                </tr>
              ) : (
                tokens.map((tokenItem) => (
                  <tr key={tokenItem.id} className="border-t border-border/70">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <code className="rounded bg-muted px-2 py-1 text-xs">{tokenItem.token}</code>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => { void copyToClipboard(tokenItem.token); }}
                        >
                          复制
                        </Button>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      <div className="space-y-1">
                        <p className="text-foreground">{tokenItem.name ?? "-"}</p>
                        {tokenItem.description ? <p className="text-xs">{tokenItem.description}</p> : null}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      <p>IP: {tokenItem.allowed_ips ?? "未限制"}</p>
                      <p>CIDR: {tokenItem.allowed_cidrs ?? "未限制"}</p>
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {tokenItem.last_used_at ? formatDateTime(tokenItem.last_used_at) : "从未使用"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant={tokenItem.is_active ? "outline" : "default"}
                        size="sm"
                        onClick={() => handleToggleToken(tokenItem.id, tokenItem.is_active)}
                        disabled={updateTokenMutation.isPending}
                      >
                        {tokenItem.is_active ? "禁用" : "启用"}
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function formatBytes(bytes: number) {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, exponent);
  return `${value.toFixed(value >= 10 || exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}

function formatDateTime(value: string | undefined | null) {
  if (!value) return "-";
  const date = new Date(value);
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function visibilityLabel(value: string) {
  switch (value) {
    case "public":
      return "公开";
    case "group":
      return "用户组";
    case "disabled":
      return "停用";
    default:
      return "仅自己";
  }
}

function visibilityBadgeClass(value: string) {
  switch (value) {
    case "public":
      return "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200";
    case "group":
      return "bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-200";
    case "disabled":
      return "bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-200";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function SpinnerLabel({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
      <svg
        className="h-3.5 w-3.5 animate-spin"
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
      >
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
      </svg>
      {label}
    </span>
  );
}
