"use client";

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";
import type { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { FileAccessLog, FileEntry, FileToken } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";

export const filesKeys = {
  all: ["files"] as const,
  list: () => [...filesKeys.all, "list"] as const,
  tokens: () => [...filesKeys.all, "tokens"] as const,
  logs: () => [...filesKeys.all, "logs"] as const,
};

export function useMyFilesQuery() {
  const token = useAuthStore((state) => state.token);

  return useQuery<FileEntry[], ApiError>({
    queryKey: filesKeys.list(),
    queryFn: async () => {
      return apiClient.get<FileEntry[]>(endpoints.files.listMine, { token });
    },
    enabled: Boolean(token),
    staleTime: 30 * 1000,
  });
}

export function useFileTokensQuery() {
  const token = useAuthStore((state) => state.token);

  return useQuery<FileToken[], ApiError>({
    queryKey: filesKeys.tokens(),
    queryFn: async () => {
      return apiClient.get<FileToken[]>(endpoints.files.tokens, { token });
    },
    enabled: Boolean(token),
    staleTime: 30 * 1000,
  });
}

export function useFileLogsQuery(limit = 50) {
  const token = useAuthStore((state) => state.token);

  return useQuery<FileAccessLog[], ApiError>({
    queryKey: [...filesKeys.logs(), limit],
    queryFn: async () =>
      apiClient.get<FileAccessLog[]>(endpoints.files.logs, {
        token,
        searchParams: { limit },
      }),
    enabled: Boolean(token),
    staleTime: 30 * 1000,
  });
}
