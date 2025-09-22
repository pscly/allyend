"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";

interface AuthLayoutProps {
  children: ReactNode;
}

/**
 * 登录/注册等公开页的布局，若已登录则自动跳转到仪表盘
 */
export function AuthLayout({ children }: AuthLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const profile = useAuthStore((state) => state.profile);

  useEffect(() => {
    if (profile) {
      router.replace("/dashboard");
    }
  }, [router, profile]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-background via-background to-muted/30 px-4 py-12">
      <div className="w-full max-w-xl space-y-6 rounded-3xl border border-border/80 bg-card/90 p-10 shadow-panel">
        <header className="space-y-1 text-center">
          <p className="text-xs tracking-widest text-muted-foreground">ALLYEND PLATFORM</p>
          <h1 className="text-2xl font-semibold text-foreground">
            {pathname === "/register" ? "创建新账号" : "欢迎回来"}
          </h1>
          <p className="text-sm text-muted-foreground">
            使用前后端分离的新控制台，管理爬虫、文件与审计日志。
          </p>
        </header>
        {children}
      </div>
    </div>
  );
}
