"use client";

import type { ReactNode } from "react";
import { useEffect, useMemo } from "react";
import { Loader2 } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";

import { AppShell } from "@/components/layout/app-shell";
import { ApiError } from "@/lib/api/client";
import { useApplyUserTheme } from "@/hooks/use-apply-theme";
import { useCurrentUserQuery } from "@/features/auth/queries";
import { logout, useAuthStore } from "@/store/auth-store";

interface ProtectedLayoutProps {
  children: ReactNode;
}

/**
 * 受保护页面的通用布局：负责鉴权、加载用户信息与渲染主框架
 */
export function ProtectedLayout({ children }: ProtectedLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const token = useAuthStore((state) => state.token);
  const persistedProfile = useAuthStore((state) => state.profile);
  const hydrated = useAuthStore((state) => state.hydrated);

  const {
    data,
    isLoading,
    isError,
    error,
    isFetching,
  } = useCurrentUserQuery({
    enabled: hydrated && Boolean(token),
  });

  const profile = useMemo(() => data ?? persistedProfile ?? null, [data, persistedProfile]);

  useApplyUserTheme(profile);

  useEffect(() => {
    if (!hydrated || token) {
      return;
    }
    const target = pathname && pathname.startsWith("/") ? pathname : "/dashboard";
    router.replace(`/login?from=${encodeURIComponent(target)}`);
  }, [hydrated, pathname, router, token]);

  useEffect(() => {
    if (!hydrated || !isError || !error) {
      return;
    }
    if (error instanceof ApiError && error.status === 401) {
      logout();
      const target = pathname && pathname.startsWith("/") ? pathname : "/dashboard";
      router.replace(`/login?from=${encodeURIComponent(target)}`);
    }
  }, [error, hydrated, isError, pathname, router]);

  const blockingLoader = (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );

  if (!hydrated) {
    return blockingLoader;
  }

  if (!token) {
    return blockingLoader;
  }

  const inlineLoading = (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );

  const showLoading = !profile && (isLoading || isFetching);

  return <AppShell user={profile}>{showLoading ? inlineLoading : children}</AppShell>;
}
