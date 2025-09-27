"use client";

import { Suspense, useMemo } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { useLoginMutation } from "@/features/auth/queries";
import { useToast } from "@/hooks/use-toast";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const schema = z.object({
  username: z.string().min(1, "请输入用户名"),
  password: z.string().min(1, "请输入密码"),
});

type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="text-center text-sm text-muted-foreground">正在加载登录页...</p>}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const loginMutation = useLoginMutation();

  const redirectTo = useMemo(() => {
    const target = searchParams?.get("from");
    if (!target) return "/";
    try {
      return decodeURIComponent(target);
    } catch {
      return "/";
    }
  }, [searchParams]);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      username: "",
      password: "",
    },
  });

  const onSubmit = async (values: FormValues) => {
    try {
      await loginMutation.mutateAsync({
        username: values.username.trim(),
        password: values.password,
      });
      toast({ title: "登录成功", description: "正在跳转首页" });
      router.replace(redirectTo);
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.payload?.detail ?? "用户名或密码错误"
          : "登录失败，请稍后重试";
      toast({ title: "登录失败", description: message, variant: "destructive" });
    }
  };

  return (
    <form className="space-y-5" onSubmit={form.handleSubmit(onSubmit)}>
      <div className="space-y-2">
        <Label htmlFor="username">用户名</Label>
        <Input id="username" autoComplete="username" {...form.register("username")} />
        <FormMessage message={form.formState.errors.username?.message} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">密码</Label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          {...form.register("password")}
        />
        <FormMessage message={form.formState.errors.password?.message} />
      </div>
      <button
        type="submit"
        className={cn(buttonVariants({ size: "lg" }), "w-full")}
        disabled={loginMutation.isPending}
      >
        {loginMutation.isPending ? "登录中..." : "登录"}
      </button>
      <p className="text-center text-xs text-muted-foreground">
        尚未拥有账号？
        <Link href="/register" className="ml-1 text-primary underline-offset-2 hover:underline">
          立即注册
        </Link>
      </p>
    </form>
  );
}

interface FormMessageProps {
  message?: string;
}

function FormMessage({ message }: FormMessageProps) {
  if (!message) return null;
  return <p className="text-xs text-destructive">{message}</p>;
}
