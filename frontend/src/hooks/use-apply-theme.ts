"use client";

import { useEffect, useMemo } from "react";
import { useTheme } from "next-themes";

import type { UserProfile } from "@/lib/api/types";

const DEFAULT_PRIMARY_FOREGROUND = "0 0% 100%";
const DEFAULT_TEXT_FOREGROUND = "225 35% 12%";

function normalizeHex(input: string | null | undefined): string | null {
  if (!input) return null;
  const value = input.trim();
  if (!value.startsWith("#")) {
    return null;
  }
  const hex = value.slice(1);
  if (!/^([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(hex)) {
    return null;
  }
  const normalized =
    hex.length === 3
      ? hex
          .split("")
          .map((ch) => ch + ch)
          .join("")
      : hex;
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
  if (!hslValue) {
    return fallback;
  }
  const parts = hslValue.split(" ");
  if (parts.length < 3) {
    return fallback;
  }
  const lightness = Number(parts[2].replace("%", ""));
  if (Number.isNaN(lightness)) {
    return fallback;
  }
  return lightness > 55 ? `${parts[0]} ${parts[1]} 15%` : `${parts[0]} ${parts[1]} 95%`;
}

export function useApplyUserTheme(profile: UserProfile | null | undefined) {
  const { setTheme } = useTheme();

  const themeColors = useMemo(() => ({
    primary: hexToHsl(profile?.theme_primary ?? null),
    secondary: hexToHsl(profile?.theme_secondary ?? null),
    background: hexToHsl(profile?.theme_background ?? null),
    darkMode: Boolean(profile?.is_dark_mode),
    hasProfile: Boolean(profile),
  }), [profile]);

  useEffect(() => {
    if (!themeColors.hasProfile) {
      applyVariable("--primary", null);
      applyVariable("--secondary", null);
      applyVariable("--background", null);
      applyVariable("--card", null);
      applyVariable("--card-foreground", null);
      applyVariable("--popover", null);
      applyVariable("--popover-foreground", null);
      applyVariable("--primary-foreground", null);
      applyVariable("--secondary-foreground", null);
      setTheme("light");
      return;
    }

    const { primary, secondary, background, darkMode } = themeColors;

    applyVariable("--primary", primary);
    applyVariable("--primary-foreground", deriveForeground(primary, DEFAULT_PRIMARY_FOREGROUND));
    applyVariable("--secondary", secondary);
    applyVariable("--secondary-foreground", deriveForeground(secondary, DEFAULT_PRIMARY_FOREGROUND));
    applyVariable("--background", background);
    applyVariable("--card", background);
    applyVariable("--popover", background);
    applyVariable("--card-foreground", deriveForeground(background, DEFAULT_TEXT_FOREGROUND));
    applyVariable("--popover-foreground", deriveForeground(background, DEFAULT_TEXT_FOREGROUND));

    setTheme(darkMode ? "dark" : "light");
  }, [setTheme, themeColors]);
}
