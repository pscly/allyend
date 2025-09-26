"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

// 中文注释：位置与天气类型定义
interface SavedLocation {
  name: string;
  country?: string;
  latitude: number;
  longitude: number;
}

interface CurrentWeather {
  temperature: number; // ℃
  windspeed: number; // km/h（open-meteo 默认）
  weathercode: number;
}

const LS_KEY = "home.location";

// 中文注释：将 Open‑Meteo weathercode 映射为中文文案
const WEATHER_CODE_TEXT: Record<number, string> = {
  0: "晴",
  1: "多云间晴",
  2: "多云",
  3: "阴",
  45: "有雾",
  48: "雾并有霜",
  51: "毛毛雨",
  53: "小雨",
  55: "中雨",
  56: "冻毛毛雨",
  57: "冻雨",
  61: "小雨",
  63: "中雨",
  65: "大雨",
  66: "冻雨",
  67: "冻雨",
  71: "小雪",
  73: "中雪",
  75: "大雪",
  77: "霰",
  80: "阵雨",
  81: "强阵雨",
  82: "暴雨",
  85: "阵雪",
  86: "强阵雪",
  95: "雷阵雨",
  96: "雷阵雨伴小冰雹",
  99: "雷阵雨伴大冰雹",
};

function useLocalLocation() {
  const [loc, setLoc] = useState<SavedLocation | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (raw) setLoc(JSON.parse(raw));
    } catch {}
  }, []);

  const save = useCallback((v: SavedLocation | null) => {
    try {
      if (v) localStorage.setItem(LS_KEY, JSON.stringify(v));
      else localStorage.removeItem(LS_KEY);
    } catch {}
    setLoc(v);
  }, []);

  return { loc, save };
}

async function fetchWeather(latitude: number, longitude: number): Promise<CurrentWeather> {
  // 中文注释：使用 Open‑Meteo 免费天气接口（无需 API Key）
  const url = new URL("https://api.open-meteo.com/v1/forecast");
  url.searchParams.set("latitude", String(latitude));
  url.searchParams.set("longitude", String(longitude));
  url.searchParams.set("current_weather", "true");
  url.searchParams.set("timezone", "auto");
  const res = await fetch(url.toString());
  const data = await res.json();
  const cw = data.current_weather;
  return {
    temperature: cw?.temperature ?? 0,
    windspeed: cw?.windspeed ?? 0,
    weathercode: cw?.weathercode ?? 0,
  };
}

async function geocode(query: string) {
  // 中文注释：Open‑Meteo 地理编码（支持中文城市名），仅取前 5 条
  const url = new URL("https://geocoding-api.open-meteo.com/v1/search");
  url.searchParams.set("name", query);
  url.searchParams.set("count", "5");
  url.searchParams.set("language", "zh");
  const res = await fetch(url.toString());
  const data = await res.json();
  const results: SavedLocation[] = (data?.results || []).map((r: any) => ({
    name: r.name,
    country: r.country,
    latitude: r.latitude,
    longitude: r.longitude,
  }));
  return results as SavedLocation[];
}

export function WeatherCard({ className }: { className?: string }) {
  const { loc, save } = useLocalLocation();
  const [weather, setWeather] = useState<CurrentWeather | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const [candidates, setCandidates] = useState<SavedLocation[]>([]);
  const [searching, setSearching] = useState(false);

  const text = useMemo(() => (weather ? WEATHER_CODE_TEXT[weather.weathercode] ?? "—" : "—"), [weather]);

  const loadByLocation = useCallback(async (l: SavedLocation) => {
    setError(null);
    setLoading(true);
    try {
      const w = await fetchWeather(l.latitude, l.longitude);
      setWeather(w);
      save(l);
    } catch (e: any) {
      setError("天气获取失败，请稍后再试");
    } finally {
      setLoading(false);
    }
  }, [save]);

  // 首次：优先使用本地保存；否则尝试浏览器定位
  useEffect(() => {
    (async () => {
      if (loc) {
        loadByLocation(loc);
        return;
      }
      if (typeof navigator !== "undefined" && navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            const l: SavedLocation = {
              name: "我的位置",
              latitude: pos.coords.latitude,
              longitude: pos.coords.longitude,
            };
            loadByLocation(l);
          },
          () => {
            // 忽略错误，等待用户手动选择
          },
          { enableHighAccuracy: false, timeout: 8000 },
        );
      }
    })();
    // 仅在初次挂载时触发
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSearch = useCallback(async () => {
    const v = q.trim();
    if (!v) return;
    setSearching(true);
    try {
      const list = await geocode(v);
      setCandidates(list);
    } finally {
      setSearching(false);
    }
  }, [q]);

  const onUseMyLocation = useCallback(() => {
    if (!navigator?.geolocation) return;
    setError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const l: SavedLocation = {
          name: "我的位置",
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
        };
        loadByLocation(l);
      },
      () => setError("无法获取定位，请检查浏览器权限"),
      { enableHighAccuracy: false, timeout: 8000 },
    );
  }, [loadByLocation]);

  return (
    <div
      className={cn(
        "relative rounded-2xl ring-1 ring-inset ring-white/15 bg-white/10 p-4 text-white shadow-[0_10px_36px_rgba(2,6,23,0.16)] backdrop-blur-2xl backdrop-saturate-150 bg-clip-padding",
        "dark:bg-white/10",
        className,
      )}
    >
      <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-white/10 to-white/5" />
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm text-white/90 dark:text-white/90">
            {loc ? `${loc.name}${loc.country ? ` · ${loc.country}` : ""}` : "未选择位置"}
          </p>
          <p className="text-xs text-white/70">{loading ? "加载中…" : error ? error : "当前天气"}</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" className="h-8" onClick={onUseMyLocation}>
            使用定位
          </Button>
        </div>
      </div>

      <div className="mb-4 flex items-end gap-4">
        <div className="leading-none">
          <div className="text-4xl font-bold tracking-tight text-white">
            {weather ? Math.round(weather.temperature) : "—"}
            <span className="ml-1 text-lg align-top">℃</span>
          </div>
          <div className="mt-1 text-sm text-white/80">{text}</div>
        </div>
        {weather && (
          <div className="text-xs text-white/75">风速 {Math.round(weather.windspeed)} km/h</div>
        )}
      </div>

      <div className="flex items-center gap-2">
        <Input
          placeholder="输入城市名，例如：北京"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="h-9 border-white/30 bg-white/10 text-white placeholder:text-white/60"
        />
        <Button size="sm" className="h-9" onClick={onSearch} disabled={searching}>
          {searching ? "搜索中…" : "搜索"}
        </Button>
      </div>

      {candidates.length > 0 && (
        <ul className="mt-3 max-h-44 space-y-1 overflow-auto rounded-lg border border-white/20 bg-white/10 p-2 text-sm text-white/90">
          {candidates.map((c) => (
            <li key={`${c.name}-${c.latitude}-${c.longitude}`}>
              <button
                className="w-full rounded-md px-2 py-1 text-left hover:bg-white/10"
                onClick={() => loadByLocation(c)}
              >
                {c.name}
                {c.country ? <span className="text-white/60"> · {c.country}</span> : null}
                <span className="text-white/60">（{c.latitude.toFixed(2)}, {c.longitude.toFixed(2)}）</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
