"use client";

import type { ReactNode } from "react";
import { QueryProvider } from "@/components/providers/query-provider";
import { ThemeProvider } from "@/components/providers/theme-provider";
import { Toaster } from "@/components/ui/toaster";
import { HomeGlassInit } from "@/components/providers/home-glass-init";

interface Props {
  children: ReactNode;
}

/**
 * 全局 Provider 组合，统一注入主题、数据缓存等上下文
 */
export function AppProviders({ children }: Props) {
  return (
    <ThemeProvider>
      <QueryProvider>
        {children}
        <Toaster />
        {/* 初始化主页雾化玻璃染色参数（来自本地存储） */}
        <HomeGlassInit />
      </QueryProvider>
    </ThemeProvider>
  );
}

