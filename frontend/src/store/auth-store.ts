import { create } from "zustand";
import { persist } from "zustand/middleware";
import { apiClient } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";

import type { UserProfile } from "@/lib/api/types";

const isServer = typeof window === "undefined";

interface AuthState {
  profile: UserProfile | null;
  hydrated: boolean;
  setProfile: (profile: UserProfile | null) => void;
  clear: () => void;
  setHydrated: (value: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      profile: null,
      hydrated: isServer,
      setProfile: (profile) => set({ profile: profile ?? null }),
      clear: () => set({ profile: null }),
      setHydrated: (value) => set({ hydrated: value }),
    }),
    {
      name: "allyend-auth",
      version: 1,
      partialize: (state) => ({ profile: state.profile }),
      onRehydrateStorage: () => (state, error) => {
        if (error) {
          console.error("auth-store 持久化恢复失败", error);
          return;
        }
        state?.setHydrated(true);
      },
    },
  ),
);

export async function logout() {
  try {
    await apiClient.post(endpoints.auth.logout, {});
  } catch (e) {
    // 忽略网络错误，尽量完成本地清理
  } finally {
    useAuthStore.getState().clear();
  }
}
