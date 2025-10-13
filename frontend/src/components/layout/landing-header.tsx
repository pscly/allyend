"use client";

import type { ReactNode } from "react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { logout, useAuthStore } from "@/store/auth-store";
import { useApplyUserTheme } from "@/hooks/use-apply-theme";

// 登录后在首页展示的导航项（保持与受保护区一致）
const AUTH_NAV_ITEMS = [
  { href: "/dashboard", label: "概览" },
  // 弃用，现在该用 /files
  { href: "/dashboard/files", label: "文件" },
  // { href: "/files", label: "文件" },
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
  const { profile } = useAuthStore();
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
          {loggedIn ? (
            <DropdownMenu>
              <DropdownMenuTrigger className="rounded-full">
                <Avatar className="h-9 w-9">
                  {profile?.avatar_url ? (
                    <AvatarImage src={profile.avatar_url} alt={profile.display_name || profile.username || "头像"} />
                  ) : (
                    <AvatarFallback>{(profile?.display_name || profile?.username || "U").slice(0, 1).toUpperCase()}</AvatarFallback>
                  )}
                </Avatar>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>
                  <p className="text-sm font-medium text-foreground">{profile?.display_name || profile?.username}</p>
                  <p className="text-xs text-muted-foreground">{profile?.email ?? `${profile?.role} 用户`}</p>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href="/dashboard">概览</Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link href="/settings">个人设置</Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link href="/settings/sessions">登录设备</Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onSelect={(e) => {
                    e.preventDefault();
                    logout();
                  }}
                >
                  退出登录
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <LandingAuthButton className="h-9 px-4 text-sm" />
          )}
        </nav>
      </div>
    </header>
  );
}
