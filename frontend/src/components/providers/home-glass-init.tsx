"use client";

import { useEffect } from "react";

/**
 * 主页毛玻璃染色参数初始化：
 * 从 localStorage 读取并应用 CSS 变量 `--home-glass-alpha`（0~0.6）。
 */
export function HomeGlassInit() {
  useEffect(() => {
    try {
      const enabled = localStorage.getItem("home.glass.enabled");
      const alpha = localStorage.getItem("home.glass.alpha");
      const value = enabled === "1" ? Number(alpha ?? "0.18") : 0;
      const clamped = Math.max(0, Math.min(0.6, Number.isFinite(value) ? value : 0));
      document.documentElement.style.setProperty("--home-glass-alpha", String(clamped));
    } catch {
      // 忽略
    }
  }, []);
  return null;
}

