"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { UserProfile } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";

interface SessionItem {
  id: number;
  session_id: string;
  user_agent?: string | null;
  ip_address?: string | null;
  remember_me: boolean;
  created_at: string;
  last_active_at?: string | null;
  expires_at?: string | null;
  current: boolean;
}

export default function SessionsPage() {
  const { profile } = useAuthStore();
  const meQuery = useQuery<UserProfile>({
    queryKey: ["auth", "me"],
    queryFn: async () => apiClient.get<UserProfile>(endpoints.auth.profile),
    staleTime: 60_000,
  });

  const sessionsQuery = useQuery<SessionItem[]>({
    queryKey: ["auth", "sessions"],
    queryFn: async () => apiClient.get<SessionItem[]>(endpoints.auth.sessions),
    staleTime: 10_000,
  });

  const revokeMutation = useMutation({
    mutationFn: async (sid: string) => apiClient.delete(endpoints.auth.sessionById(sid)),
    onSuccess: () => sessionsQuery.refetch(),
  });

  const user = meQuery.data ?? profile;

  return (
    <AppShell user={user ?? null}>
      <div className="space-y-6">
        <h1 className="text-xl font-semibold">登录设备</h1>
        <p className="text-sm text-muted-foreground">在这里查看已登录的设备，并可手动将其他设备下线。</p>

        <div className="divide-y rounded-md border">
          {(sessionsQuery.data ?? []).map((s) => (
            <div key={s.session_id} className="flex items-center justify-between gap-4 p-3">
              <div className="space-y-1">
                <div className="text-sm font-medium">
                  {s.current ? (
                    <span className="mr-2 rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-800">当前设备</span>
                  ) : null}
                  {s.user_agent || "未知设备"}
                </div>
                <div className="text-xs text-muted-foreground">
                  IP: {s.ip_address || "-"} • 最近活跃: {s.last_active_at || s.created_at} • 到期: {s.expires_at || "-"}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {s.remember_me && <span className="rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">记住我</span>}
                {!s.current && (
                  <button
                    className={cn(buttonVariants({ variant: "destructive", size: "sm" }))}
                    onClick={() => revokeMutation.mutate(s.session_id)}
                  >
                    下线该设备
                  </button>
                )}
              </div>
            </div>
          ))}
          {sessionsQuery.data?.length === 0 && (
            <div className="p-4 text-center text-sm text-muted-foreground">暂无其他设备会话</div>
          )}
        </div>
      </div>
    </AppShell>
  );
}

