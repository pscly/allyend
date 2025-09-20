"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Menu } from "lucide-react";
import type { ReactNode } from "react";

import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
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
    logout();
    router.replace("/login");
  };

  const desktopNav = items.map((item) => {
    const active = pathname?.startsWith(item.href);
    return (
      <Link
        key={item.href}
        href={item.href}
        className={cn(
          "rounded-full px-3 py-1.5 text-sm transition-colors",
          active ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground",
        )}
      >
        {item.label}
      </Link>
    );
  });

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-30 border-b border-border/70 bg-card/80 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-4">
          <div className="flex items-center gap-2">
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
                          "rounded-lg px-3 py-2 text-base font-medium transition-colors",
                          pathname?.startsWith(item.href)
                            ? "bg-primary/15 text-primary"
                            : "text-muted-foreground hover:text-foreground",
                        )}
                      >
                        {item.label}
                      </Link>
                    </SheetClose>
                  ))}
                </nav>
              </SheetContent>
            </Sheet>
            <Link href="/dashboard" className="font-semibold tracking-tight text-foreground">
              AllYend
            </Link>
            <div className="hidden items-center gap-2 md:flex">{desktopNav}</div>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <DropdownMenu>
              <DropdownMenuTrigger className="rounded-full">
                <Avatar className="h-9 w-9">
                  <AvatarFallback>{getInitial(user)}</AvatarFallback>
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
                <DropdownMenuItem onSelect={() => router.push("/dashboard/files")}>我的文件</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => router.push("/public")}>公开空间</DropdownMenuItem>
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
