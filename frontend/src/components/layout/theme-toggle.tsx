"use client";

import { useEffect, useMemo, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { useUpdateThemeMutation } from "@/features/theme/mutations";
import { useToast } from "@/hooks/use-toast";
import { ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/auth-store";

/**
 * 主题切换按钮，支持亮/暗/系统模式互换，并同步服务端偏好
 */
export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const { toast } = useToast();
  const [mounted, setMounted] = useState(false);
  const profile = useAuthStore((state) => state.profile);
  const updateTheme = useUpdateThemeMutation();

  useEffect(() => {
    setMounted(true);
  }, []);

  const currentTheme = useMemo(() => {
    if (theme === "system") {
      return resolvedTheme ?? "light";
    }
    return theme ?? "light";
  }, [resolvedTheme, theme]);

  const handleToggle = async () => {
    if (!mounted || updateTheme.isPending) {
      return;
    }
    const previous = currentTheme;
    const next = currentTheme === "dark" ? "light" : "dark";
    setTheme(next);

    if (!profile) {
      return;
    }

    try {
      await updateTheme.mutateAsync({ isDarkMode: next === "dark" });
    } catch (error) {
      setTheme(previous);
      const message =
        error instanceof ApiError
          ? error.payload?.detail ?? "与服务器同步主题失败"
          : "与服务器同步主题失败";
      toast({ title: "主题切换失败", description: message, variant: "destructive" });
    }
  };

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      onClick={handleToggle}
      className="relative h-9 w-9 rounded-full"
      aria-label="切换主题"
      disabled={!mounted || updateTheme.isPending}
    >
      <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
      <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
      <span className="sr-only">切换主题</span>
    </Button>
  );
}
