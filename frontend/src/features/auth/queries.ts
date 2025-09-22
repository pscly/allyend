"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { UserProfile } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";

export const authKeys = {
  all: ["auth"] as const,
  me: () => [...authKeys.all, "me"] as const,
};

interface LoginPayload {
  username: string;
  password: string;
}

interface RegisterPayload extends LoginPayload {
  display_name?: string | null;
  email?: string | null;
  invite_code?: string | null;
}

interface QueryOptions {
  enabled?: boolean;
}

/**
 * 当前登录用户信息查询
 */
export function useCurrentUserQuery(options?: QueryOptions) {
  return useQuery<UserProfile, ApiError>({
    queryKey: authKeys.me(),
    queryFn: async () => {
      const profile = await apiClient.get<UserProfile>(endpoints.auth.profile);
      useAuthStore.getState().setProfile(profile);
      return profile;
    },
    enabled: options?.enabled ?? true,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.status === 401) {
        return false;
      }
      return failureCount < 1;
    },
    staleTime: 60 * 1000,
  });
}

/**
 * 登录操作
 */
export function useLoginMutation() {
  const queryClient = useQueryClient();

  return useMutation<UserProfile, ApiError, LoginPayload>({
    mutationFn: async (payload) => {
      return apiClient.post<UserProfile, LoginPayload>(endpoints.auth.login, payload);
    },
    onSuccess: async (response) => {
      useAuthStore.getState().setProfile(response);
      await queryClient.invalidateQueries({ queryKey: authKeys.all });
    },
  });
}

/**
 * 注册操作
 */
export function useRegisterMutation() {
  const queryClient = useQueryClient();

  return useMutation<UserProfile, ApiError, RegisterPayload>({
    mutationFn: async (payload) => {
      return apiClient.post<UserProfile, RegisterPayload>(endpoints.auth.register, payload);
    },
    onSuccess: async (response) => {
      useAuthStore.getState().setProfile(response);
      await queryClient.invalidateQueries({ queryKey: authKeys.all });
    },
  });
}
