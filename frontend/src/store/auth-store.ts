import { create } from "zustand";
import { persist } from "zustand/middleware";

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

export function logout() {
  useAuthStore.getState().clear();
}
