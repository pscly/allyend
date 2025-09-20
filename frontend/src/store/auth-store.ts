import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { TokenResponse, UserProfile } from "@/lib/api/types";

const isServer = typeof window === "undefined";

interface AuthState {
  token: string | null;
  profile: UserProfile | null;
  hydrated: boolean;
  setCredentials: (token: string, profile?: UserProfile | null) => void;
  setProfile: (profile: UserProfile | null) => void;
  clear: () => void;
  setHydrated: (value: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      profile: null,
      hydrated: isServer,
      setCredentials: (token, profile) =>
        set({
          token,
          profile: profile ?? null,
          hydrated: true,
        }),
      setProfile: (profile) => set({ profile: profile ?? null }),
      clear: () => set({ token: null, profile: null }),
      setHydrated: (value) => set({ hydrated: value }),
    }),
    {
      name: "allyend-auth",
      version: 1,
      partialize: (state) => ({ token: state.token, profile: state.profile }),
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

export function persistToken(response: TokenResponse, profile?: UserProfile) {
  useAuthStore.getState().setCredentials(response.access_token, profile ?? null);
}

export function logout() {
  useAuthStore.getState().clear();
}
