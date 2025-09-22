"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import { useTheme } from "next-themes";

import { Skeleton } from "@/components/ui/skeleton";
import type { CrawlerHeartbeat } from "@/lib/api/types";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

const STATUS_SCORE: Record<string, number> = {
  offline: 0,
  warning: 1,
  online: 2,
};

const STATUS_LABEL: Record<number, string> = {
  0: "离线",
  1: "预警",
  2: "在线",
};

function resolveMetricValue(payload: Record<string, unknown> | null | undefined, key: string): number | null {
  if (!payload || typeof payload !== "object") return null;
  const raw = (payload as Record<string, unknown>)[key];
  if (raw === undefined || raw === null) return null;
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  if (typeof raw === "string") {
    const num = Number(raw);
    return Number.isFinite(num) ? num : null;
  }
  return null;
}

function formatTooltipDate(value: number | string): string {
  const ts = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(ts)) return String(value);
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

export interface HeartbeatChartProps {
  data: CrawlerHeartbeat[];
  metricKey?: string;
  loading?: boolean;
}

export function HeartbeatChart({ data, metricKey = "__status", loading = false }: HeartbeatChartProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const textColor = isDark ? "#e2e8f0" : "#1f2937";
  const gridColor = isDark ? "rgba(148, 163, 184, 0.25)" : "rgba(148, 163, 184, 0.45)";
  const accentColor = isDark ? "#60a5fa" : "#2563eb";
  const statusColor = isDark ? "#34d399" : "#10b981";

  const statusSeries = useMemo(() =>
    data.map((item) => [new Date(item.created_at).getTime(), STATUS_SCORE[item.status] ?? STATUS_SCORE.offline]),
  [data]);

  const metricSeries = useMemo(
    () =>
      data.map(
        (item) => [new Date(item.created_at).getTime(), resolveMetricValue(item.payload ?? null, metricKey)] as [
          number,
          number | null,
        ],
      ),
    [data, metricKey],
  );

  const hasMetric = metricKey !== "__status" && metricSeries.some((entry) => entry[1] !== null);
  const metricLabel = metricKey === "__status" ? "" : metricKey;

  const option = useMemo(() => {
    const series: any[] = [
      {
        name: "状态",
        type: "line",
        step: "middle" as const,
        data: statusSeries,
        yAxisIndex: 0,
        symbol: "circle",
        symbolSize: 6,
        smooth: false,
        lineStyle: { color: statusColor, width: 2 },
        itemStyle: { color: statusColor },
        areaStyle: { color: isDark ? "rgba(52, 211, 153, 0.16)" : "rgba(16, 185, 129, 0.16)" },
      },
    ];

    if (hasMetric) {
      series.push({
        name: metricLabel,
        type: "line",
        // ECharts 运行时允许 null 作为缺失值，类型定义较严格，这里做兼容性断言
        data: metricSeries as unknown as number[][],
        yAxisIndex: 1,
        smooth: true,
        symbol: "circle",
        symbolSize: 4,
        lineStyle: { color: accentColor, width: 2 },
        itemStyle: { color: accentColor },
      });
    }

    return {
      textStyle: {
        color: textColor,
        fontFamily: '"SF Pro Display", "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      },
      grid: { left: 48, right: hasMetric ? 56 : 32, top: 36, bottom: 56 },
      legend: {
        data: hasMetric ? ["状态", metricLabel] : ["状态"],
        textStyle: { color: textColor },
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: isDark ? "rgba(15, 23, 42, 0.92)" : "rgba(255, 255, 255, 0.96)",
        borderColor: isDark ? "rgba(148, 163, 184, 0.2)" : "rgba(59, 130, 246, 0.2)",
        textStyle: { color: textColor },
        formatter: (params: any) => {
          const points = Array.isArray(params) ? params : [params];
          const first = points[0];
          const timeLabel = first ? formatTooltipDate(first.axisValue) : "";
          const pieces: string[] = [timeLabel];
          const statusPoint = points.find((item) => item && item.seriesName === "状态");
          if (statusPoint) {
            const raw = Array.isArray(statusPoint.value) ? statusPoint.value[1] : statusPoint.value;
            const label = STATUS_LABEL[Math.round(Number(raw))] ?? String(raw);
            pieces.push(`状态：${label}`);
          }
          if (hasMetric) {
            const metricPoint = points.find((item) => item && item.seriesName === metricLabel);
            if (metricPoint) {
              const raw = Array.isArray(metricPoint.value) ? metricPoint.value[1] : metricPoint.value;
              pieces.push(`${metricLabel}：${raw ?? "-"}`);
            }
          }
          return pieces.join('<br/>');
        },
      },
      dataZoom: [
        { type: "inside", throttle: 32 },
        { type: "slider", height: 24, bottom: 12 },
      ],
      xAxis: {
        type: "time",
        axisLabel: { color: textColor },
        axisLine: { lineStyle: { color: gridColor } },
        axisTick: { lineStyle: { color: gridColor } },
        splitLine: { lineStyle: { color: gridColor } },
      },
      yAxis: [
        {
          type: "value",
          min: -0.2,
          max: 2.2,
          interval: 1,
          axisLabel: {
            color: textColor,
            formatter: (value: number) => STATUS_LABEL[Math.round(value)] ?? "",
          },
          splitLine: { lineStyle: { color: gridColor } },
        },
        {
          type: "value",
          show: hasMetric,
          axisLabel: { color: textColor },
          splitLine: { show: false },
          position: "right",
          scale: true,
        },
      ],
      series,
    };
  }, [statusSeries, metricSeries, hasMetric, metricLabel, textColor, gridColor, statusColor, accentColor, isDark]);

  if (!data.length) {
    return loading ? <Skeleton className="h-64 w-full" /> : (
      <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
        暂无心跳数据
      </div>
    );
  }

  return (
    <div className="h-64 w-full">
      <ReactECharts style={{ height: "100%", width: "100%" }} option={option} notMerge lazyUpdate />
    </div>
  );
}
