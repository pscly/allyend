"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { buttonVariants } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { UserProfile } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";

export default function SettingsPage() {
  const { profile } = useAuthStore();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);

  const meQuery = useQuery<UserProfile>({
    queryKey: ["auth", "me"],
    queryFn: async () => apiClient.get<UserProfile>(endpoints.auth.profile),
    staleTime: 60_000,
  });

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return apiClient.post<UserProfile, FormData>(endpoints.auth.avatar, form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
    },
    onSuccess: (res) => {
      useAuthStore.getState().setProfile(res as unknown as UserProfile);
      meQuery.refetch();
    },
  });

  const onPick = () => inputRef.current?.click();
  const onFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      await uploadMutation.mutateAsync(f);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const user = meQuery.data ?? profile;
  const initial = (user?.display_name || user?.username || "U").slice(0, 1).toUpperCase();

  return (
    <AppShell user={user ?? null}>
      <div className="space-y-6">
        <h1 className="text-xl font-semibold">个人设置</h1>

        <section className="flex items-center gap-4">
          <Avatar className="h-16 w-16">
            {user?.avatar_url ? (
              <AvatarImage src={user.avatar_url} alt={user?.display_name || user?.username || "头像"} />
            ) : (
              <AvatarFallback>{initial}</AvatarFallback>
            )}
          </Avatar>
          <div className="space-x-3">
            <button
              className={cn(buttonVariants({ size: "sm" }))}
              onClick={onPick}
              disabled={uploading}
            >
              {uploading ? "上传中..." : "上传头像"}
            </button>
            {user?.avatar_url && (
              <button
                className={cn(buttonVariants({ size: "sm", variant: "secondary" }))}
                onClick={async () => {
                  await apiClient.delete(endpoints.auth.avatar);
                  useAuthStore.getState().setProfile({ ...(user as UserProfile), avatar_url: null });
                  meQuery.refetch();
                }}
              >
                移除头像
              </button>
            )}
            <input ref={inputRef} onChange={onFileChange} type="file" accept="image/*" className="hidden" />
          </div>
        </section>

        {/* 预留更多设置项：昵称、邮箱、主题等已在其它入口提供 */}
      </div>
    </AppShell>
  );
}

