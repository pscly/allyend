"use client";

import { useMemo, useState } from "react";
import { Palette, Check } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useUpdateThemeMutation } from "@/features/theme/mutations";
import { ApiError } from "@/lib/api/client";
import { useToast } from "@/hooks/use-toast";
import { useAuthStore } from "@/store/auth-store";

type Preset = {
  key: string;
  name: string;
  primary: string; // Hex 颜色，如 #7C3AED
  secondary: string; // Hex 颜色
  background: string; // Hex 颜色
  dark?: boolean; // 是否建议暗色
};

// 预置主题，偏向干净的 Dashboard 风格
const PRESETS: Preset[] = [
  { key: "aurora", name: "极光", primary: "#7C3AED", secondary: "#22D3EE", background: "#F3F4F6" },
  { key: "ocean", name: "海洋", primary: "#2563EB", secondary: "#06B6D4", background: "#EFF6FF" },
  { key: "sunset", name: "暮光", primary: "#F97316", secondary: "#EF4444", background: "#FFF7ED" },
  { key: "forest", name: "森林", primary: "#16A34A", secondary: "#65A30D", background: "#F0FDF4" },
  { key: "sakura", name: "樱花", primary: "#EC4899", secondary: "#8B5CF6", background: "#FFF1F2" },
  { key: "graphite", name: "石墨", primary: "#111827", secondary: "#374151", background: "#F9FAFB" },
  { key: "night", name: "夜空", primary: "#60A5FA", secondary: "#22D3EE", background: "#0B1220", dark: true },
];

// 与 use-apply-theme 同步的小工具：即时预览（无需等待服务端）
function normalizeHex(input: string | null | undefined): string | null {
  if (!input) return null;
  const value = input.trim();
  if (!value.startsWith("#")) return null;
  const hex = value.slice(1);
  if (!/^([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(hex)) return null;
  const normalized = hex.length === 3 ? hex.split("").map((c) => c + c).join("") : hex;
  return `#${normalized.toLowerCase()}`;
}

function hexToHsl(input: string | null | undefined): string | null {
  const normalized = normalizeHex(input);
  if (!normalized) return null;
  const r = parseInt(normalized.slice(1, 3), 16) / 255;
  const g = parseInt(normalized.slice(3, 5), 16) / 255;
  const b = parseInt(normalized.slice(5, 7), 16) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r:
        h = (g - b) / d + (g < b ? 6 : 0);
        break;
      case g:
        h = (b - r) / d + 2;
        break;
      case b:
        h = (r - g) / d + 4;
        break;
      default:
        h = 0;
    }
    h /= 6;
  }
  const hue = Math.round(h * 360);
  const saturation = Math.round(s * 100);
  const lightness = Math.round(l * 100);
  return `${hue} ${saturation}% ${lightness}%`;
}

function applyVariable(name: string, value: string | null) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (!value) {
    root.style.removeProperty(name);
    return;
  }
  root.style.setProperty(name, value);
}

function deriveForeground(hslValue: string | null, fallback: string): string {
  if (!hslValue) return fallback;
  const parts = hslValue.split(" ");
  if (parts.length < 3) return fallback;
  const lightness = Number(parts[2].replace("%", ""));
  if (Number.isNaN(lightness)) return fallback;
  return lightness > 55 ? `${parts[0]} ${parts[1]} 15%` : `${parts[0]} ${parts[1]} 95%`;
}

export function ThemePresets() {
  const { setTheme } = useTheme();
  const profile = useAuthStore((s) => s.profile);
  const { toast } = useToast();
  const updateTheme = useUpdateThemeMutation();
  const [open, setOpen] = useState(false);

  const currentKey = useMemo(() => profile?.theme_name ?? null, [profile?.theme_name]);

  const applyInstantly = (preset: Preset) => {
    const primary = hexToHsl(preset.primary);
    const secondary = hexToHsl(preset.secondary);
    const background = hexToHsl(preset.background);
    applyVariable("--primary", primary);
    applyVariable("--primary-foreground", deriveForeground(primary, "0 0% 100%"));
    applyVariable("--secondary", secondary);
    applyVariable("--secondary-foreground", deriveForeground(secondary, "0 0% 100%"));
    applyVariable("--background", background);
    applyVariable("--card", background);
    applyVariable("--popover", background);
    applyVariable("--card-foreground", deriveForeground(background, "225 35% 12%"));
    applyVariable("--popover-foreground", deriveForeground(background, "225 35% 12%"));
    setTheme(preset.dark ? "dark" : "light");
  };

  const handlePick = async (preset: Preset) => {
    applyInstantly(preset);
    if (!profile) {
      return; // 未登录只即时预览
    }
    try {
      await updateTheme.mutateAsync({
        themeName: preset.name,
        themePrimary: preset.primary,
        themeSecondary: preset.secondary,
        themeBackground: preset.background,
        isDarkMode: preset.dark ?? profile?.is_dark_mode ?? false,
      });
    } catch (error) {
      const message = error instanceof ApiError ? error.payload?.detail ?? "保存主题失败" : "保存主题失败";
      toast({ title: "主题保存失败", description: message, variant: "destructive" });
    } finally {
      setOpen(false);
    }
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <DropdownMenuTrigger asChild>
              <Button type="button" variant="ghost" size="icon" className="relative h-9 w-9 rounded-full">
                <Palette className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
          </TooltipTrigger>
          <TooltipContent>主题预设</TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <DropdownMenuContent align="end" className="w-72 p-0">
        <DropdownMenuLabel className="px-4 py-3 text-xs text-muted-foreground">选择主题（即时生效，登录后自动保存）</DropdownMenuLabel>
        <ScrollArea className="max-h-[320px] px-3 pb-3 pt-1">
          <div className="grid grid-cols-3 gap-3">
            {PRESETS.map((preset) => (
              <button
                key={preset.key}
                onClick={() => void handlePick(preset)}
                className={cn(
                  "group relative overflow-hidden rounded-xl border bg-card p-2 text-left transition-all hover:shadow-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  currentKey && profile?.theme_name === preset.name ? "ring-2 ring-primary" : undefined,
                )}
              >
                <div
                  className="h-12 w-full rounded-lg"
                  style={{
                    background: `linear-gradient(135deg, ${preset.primary} 0%, ${preset.secondary} 100%)`,
                  }}
                />
                <div className="mt-2 flex items-center justify-between">
                  <span className="truncate text-xs text-foreground/90">{preset.name}</span>
                  <span
                    className="h-4 w-4 rounded-full border"
                    style={{ backgroundColor: preset.background }}
                  />
                </div>
                {profile?.theme_name === preset.name && (
                  <span className="absolute right-2 top-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground shadow">
                    <Check className="h-3 w-3" />
                  </span>
                )}
              </button>
            ))}
          </div>
        </ScrollArea>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

