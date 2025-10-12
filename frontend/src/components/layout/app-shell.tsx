"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Menu } from "lucide-react";
import type { ReactNode } from "react";

import { ThemePresets } from "@/components/layout/theme-presets";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import type { UserProfile } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { logout } from "@/store/auth-store";

interface AppShellProps {
  children: ReactNode;
  className?: string;
  user?: UserProfile | null;
}

const NAV_ITEMS = [
  { href: "/dashboard", label: "概览" },
  { href: "/dashboard/files", label: "文件" },
  { href: "/dashboard/crawlers", label: "爬虫" },
  { href: "/public", label: "公开空间" },
];

function getInitial(user?: UserProfile | null) {
  const source = user?.display_name || user?.username || "U";
  return source.slice(0, 1).toUpperCase();
}

function hasAdminCapability(user?: UserProfile | null) {
  return user?.role === "admin" || user?.role === "superadmin";
}

function normalizePath(path?: string | null) {
  if (!path || path === "/") {
    return "/";
  }
  return path.replace(/\/+$/, "");
}

function getMatchScore(currentPath: string, targetHref: string): number {
  const target = normalizePath(targetHref);
  if (target === "/") {
    return currentPath === "/" ? 1 : 0;
  }
  if (currentPath === target) {
    return target.length + 1;
  }
  if (currentPath.startsWith(`${target}/`)) {
    return target.length;
  }
  return 0;
}

/**
 * 应用整体布局，包含顶部导航、主题切换与用户菜单
 */
export function AppShell({ children, className, user }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();

  const items = [...NAV_ITEMS];
  if (hasAdminCapability(user)) {
    items.push({ href: "/admin", label: "管理" });
  }

  const handleLogout = () => {
    logout().finally(() => {
      router.replace("/login");
    });
  };

  const currentPath = normalizePath(pathname);
  const activeHref =
    items.reduce<{ href: string; score: number } | null>((best, item) => {
      const score = getMatchScore(currentPath, item.href);
      if (score === 0) {
        return best;
      }
      if (!best || score > best.score) {
        return { href: item.href, score };
      }
      return best;
    }, null)?.href;

  const desktopNav = items.map((item) => {
    const active = activeHref === item.href;
    return (
      <Link
        key={item.href}
        href={item.href}
        className={cn(
          "group relative overflow-hidden rounded-full px-3.5 py-1.5 text-sm font-medium transition-all duration-200",
          active
            ? "bg-gradient-to-r from-primary/90 via-primary/80 to-secondary/80 text-primary-foreground shadow-surface"
            : "text-muted-foreground hover:bg-primary/10 hover:text-foreground",
        )}
      >
        {item.label}
      </Link>
    );
  });

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-30 bg-transparent">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <Sheet>
              <SheetTrigger asChild>
                <button className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "md:hidden")}>
                  <Menu className="h-5 w-5" />
                  <span className="sr-only">展开菜单</span>
                </button>
              </SheetTrigger>
              <SheetContent side="left" className="w-72">
                <SheetHeader>
                  <SheetTitle>AllYend 控制台</SheetTitle>
                </SheetHeader>
                <nav className="mt-6 flex flex-col gap-2">
                  {items.map((item) => (
                    <SheetClose asChild key={item.href}>
                      <Link
                        href={item.href}
                        className={cn(
                          "group relative overflow-hidden rounded-xl px-3.5 py-2.5 text-base font-semibold transition-all duration-200",
                          activeHref === item.href
                            ? "bg-gradient-to-r from-primary/90 via-primary/80 to-secondary/80 text-primary-foreground shadow-surface"
                            : "text-muted-foreground hover:bg-primary/10 hover:text-foreground",
                        )}
                      >
                        {item.label}
                      </Link>
                    </SheetClose>
                  ))}
                </nav>
              </SheetContent>
            </Sheet>
            <Link href="/" className="font-semibold tracking-tight">
              <span className="bg-gradient-to-r from-primary via-primary/80 to-secondary/90 bg-clip-text text-transparent">AllYend</span>
            </Link>
            <div className="hidden items-center md:flex">
              <div className="flex items-center gap-1 rounded-full border border-border/70 bg-card/70 px-1 py-1 shadow-surface backdrop-blur">
                {desktopNav}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <ThemePresets />
            <DropdownMenu>
              <DropdownMenuTrigger className="rounded-full">
                <Avatar className="h-9 w-9">
                  {user?.avatar_url ? (
                    <AvatarImage src={user.avatar_url} alt={user?.display_name || user?.username || "头像"} />
                  ) : (
                    <AvatarFallback>{getInitial(user)}</AvatarFallback>
                  )}
                </Avatar>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>
                  <p className="text-sm font-medium text-foreground">
                    {user?.display_name || user?.username || "访客"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {user?.email ?? (user ? `${user.role} 用户` : "未登录")}
                  </p>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => router.push("/dashboard")}>概览</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => router.push("/dashboard/files")}>文件</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => router.push("/public")}>公开空间</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => router.push("/settings")}>个人设置</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => router.push("/settings/sessions")}>登录设备</DropdownMenuItem>
                {hasAdminCapability(user) && (
                  <DropdownMenuItem onSelect={() => router.push("/admin")}>管理中心</DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onSelect={(event) => {
                    event.preventDefault();
                    handleLogout();
                  }}
                >
                  <LogOut className="h-4 w-4" />
                  退出登录
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>
      <main className={cn("mx-auto w-full max-w-6xl flex-1 px-4 py-6", className)}>{children}</main>
      <footer className="border-t border-border/60 py-6 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} AllYend • FastAPI + Next.js 全栈方案
      </footer>
    </div>
  );
}

