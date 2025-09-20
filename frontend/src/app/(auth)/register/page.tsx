"use client";

import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useRegisterMutation } from "@/features/auth/queries";
import { useToast } from "@/hooks/use-toast";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const schema = z
  .object({
    username: z.string().min(3, "至少 3 个字符"),
    password: z.string().min(6, "至少 6 位密码"),
    confirm: z.string().min(6, "再次输入密码"),
    display_name: z.string().optional(),
    email: z.string().email("请输入有效邮箱").optional().or(z.literal("")),
    invite_code: z.string().optional(),
  })
  .refine((values) => values.password === values.confirm, {
    message: "两次输入的密码不一致",
    path: ["confirm"],
  });

type FormValues = z.infer<typeof schema>;

export default function RegisterPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const registerMutation = useRegisterMutation();

  const redirectTo = useMemo(() => {
    const target = searchParams?.get("from");
    if (!target) return "/dashboard";
    try {
      return decodeURIComponent(target);
    } catch {
      return "/dashboard";
    }
  }, [searchParams]);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      username: "",
      password: "",
      confirm: "",
      display_name: "",
      email: "",
      invite_code: "",
    },
  });

  const onSubmit = async (values: FormValues) => {
    try {
      await registerMutation.mutateAsync({
        username: values.username.trim(),
        password: values.password,
        display_name: values.display_name?.trim() || undefined,
        email: values.email?.trim() || undefined,
        invite_code: values.invite_code?.trim() || undefined,
      });
      toast({ title: "注册成功", description: "欢迎加入 AllYend" });
      router.replace(redirectTo);
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.payload?.detail ?? "注册失败，请检查信息"
          : "注册失败，请稍晚再试";
      toast({ title: "注册失败", description: message, variant: "destructive" });
    }
  };

  return (
    <form className="space-y-5" onSubmit={form.handleSubmit(onSubmit)}>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="用户名" error={form.formState.errors.username?.message}>
          <Input placeholder="your.name" {...form.register("username")} />
        </Field>
        <Field label="显示名称" error={form.formState.errors.display_name?.message}>
          <Input placeholder="可选" {...form.register("display_name")} />
        </Field>
      </div>
      <Field label="邮箱" error={form.formState.errors.email?.message}>
        <Input type="email" placeholder="可选" {...form.register("email")} />
      </Field>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="密码" error={form.formState.errors.password?.message}>
          <Input type="password" autoComplete="new-password" {...form.register("password")} />
        </Field>
        <Field label="确认密码" error={form.formState.errors.confirm?.message}>
          <Input type="password" autoComplete="new-password" {...form.register("confirm")} />
        </Field>
      </div>
      <Field label="邀请码" error={form.formState.errors.invite_code?.message}>
        <Input placeholder="管理员提供的邀请码" {...form.register("invite_code")} />
      </Field>
      <button
        type="submit"
        className={cn(buttonVariants({ size: "lg" }), "w-full")}
        disabled={registerMutation.isPending}
      >
        {registerMutation.isPending ? "注册中..." : "提交注册"}
      </button>
      <p className="text-center text-xs text-muted-foreground">
        已经拥有账号？
        <Link href="/login" className="ml-1 text-primary underline-offset-2 hover:underline">
          前往登录
        </Link>
      </p>
    </form>
  );
}

interface FieldProps {
  label: string;
  children: React.ReactNode;
  error?: string;
}

function Field({ label, children, error }: FieldProps) {
  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium text-foreground">{label}</Label>
      {children}
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
