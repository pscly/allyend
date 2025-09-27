"use client";

import type { ReactNode } from "react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";
import { useApplyUserTheme } from "@/hooks/use-apply-theme";

// 登录后在首页展示的导航项（保持与受保护区一致）
const AUTH_NAV_ITEMS = [
  { href: "/dashboard", label: "概览" },
  { href: "/dashboard/files", label: "文件" },
  { href: "/dashboard/crawlers", label: "爬虫" },
  { href: "/public", label: "公开空间" },
  { href: "/docs", label: "文档" },
];

interface LandingAuthState {
  loggedIn: boolean;
  ctaHref: string;
  ctaLabel: string;
  welcomeName?: string;
}

function useLandingAuthState(): LandingAuthState {
  const { hydrated, profile } = useAuthStore((state) => ({
    hydrated: state.hydrated,
    profile: state.profile,
  }));

  const loggedIn = hydrated && Boolean(profile);
  // 在首页也应用用户选择的主题
  useApplyUserTheme(profile ?? null);
  return {
    loggedIn,
    ctaHref: loggedIn ? "/dashboard" : "/login",
    ctaLabel: loggedIn ? "进入控制台" : "立即登录",
    welcomeName: loggedIn ? profile?.display_name || profile?.username || undefined : undefined,
  };
}

interface LandingAuthButtonProps {
  className?: string;
  size?: "default" | "sm" | "lg";
  prefix?: ReactNode;
  suffix?: ReactNode;
}

export function LandingAuthButton({
  className,
  size = "default",
  prefix,
  suffix,
}: LandingAuthButtonProps) {
  const { loggedIn, ctaHref, ctaLabel } = useLandingAuthState();

  return (
    <Link
      href={ctaHref}
      className={cn(buttonVariants({ variant: loggedIn ? "secondary" : "default", size }), className)}
    >
      {prefix}
      <span>{ctaLabel}</span>
      {suffix}
    </Link>
  );
}

interface LandingWelcomeProps {
  className?: string;
}

export function LandingWelcome({ className }: LandingWelcomeProps) {
  const { welcomeName } = useLandingAuthState();
  if (!welcomeName) {
    return null;
  }
  return <span className={cn("text-xs text-muted-foreground", className)}>欢迎，{welcomeName}</span>;
}

export function LandingHeader() {
  const { loggedIn } = useLandingAuthState();
  return (
    <header className="border-b border-border bg-card/70 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4">
        <Link href="/" className="font-semibold tracking-wide text-primary">
          AllYend
        </Link>
        <nav className="flex items-center gap-4 text-sm text-muted-foreground">
          {loggedIn &&
            AUTH_NAV_ITEMS.map((item) => (
              <Link key={item.href} href={item.href} className="hover:text-foreground">
                {item.label}
              </Link>
            ))}
          <LandingWelcome />
          <LandingAuthButton className="h-9 px-4 text-sm" />
        </nav>
      </div>
    </header>
  );
}
