"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";
import type { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { CrawlerSummary } from "@/lib/api/types";
import { crawlerKeys } from "@/features/crawlers/queries";

interface RegisterCrawlerInput {
  name: string;
  apiKey: string;
}

export function useRegisterCrawlerMutation() {
  const queryClient = useQueryClient();

  return useMutation<CrawlerSummary, ApiError, RegisterCrawlerInput>({
    mutationFn: async ({ name, apiKey }) =>
      apiClient.post<CrawlerSummary>(
        endpoints.crawlers.register,
        { name },
        {
          init: {
            headers: {
              "X-API-Key": apiKey,
            },
          },
        },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: crawlerKeys.list() });
    },
  });
}
