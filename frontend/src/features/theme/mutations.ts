"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { authKeys } from "@/features/auth/queries";
import { apiClient } from "@/lib/api/client";
import type { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { ThemeSetting, ThemeSettingUpdateInput, UserProfile } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";

function buildThemeBody(payload: ThemeSettingUpdateInput) {
  const body: Record<string, unknown> = {};
  if (payload.themeName !== undefined) {
    body.theme_name = payload.themeName ?? null;
  }
  if (payload.themePrimary !== undefined) {
    body.theme_primary = payload.themePrimary ?? null;
  }
  if (payload.themeSecondary !== undefined) {
    body.theme_secondary = payload.themeSecondary ?? null;
  }
  if (payload.themeBackground !== undefined) {
    body.theme_background = payload.themeBackground ?? null;
  }
  if (payload.isDarkMode !== undefined) {
    body.is_dark_mode = payload.isDarkMode;
  }
  return body;
}

function mergeTheme(profile: UserProfile | null, theme: ThemeSetting): UserProfile | null {
  if (!profile) {
    return profile;
  }
  return {
    ...profile,
    theme_name: theme.theme_name,
    theme_primary: theme.theme_primary,
    theme_secondary: theme.theme_secondary,
    theme_background: theme.theme_background,
    is_dark_mode: theme.is_dark_mode,
  };
}

export function useUpdateThemeMutation() {
  const queryClient = useQueryClient();

  return useMutation<ThemeSetting, ApiError, ThemeSettingUpdateInput>({
    mutationFn: async (payload) => apiClient.patch<ThemeSetting>(endpoints.dashboard.theme, buildThemeBody(payload)),
    onSuccess: async (data) => {
      const store = useAuthStore.getState();
      const nextProfile = mergeTheme(store.profile, data);
      if (nextProfile) {
        store.setProfile(nextProfile);
      }
      await queryClient.invalidateQueries({ queryKey: authKeys.me() });
    },
  });
}
