import { LandingHeader } from "@/components/layout/landing-header";
import { cn } from "@/lib/utils";
import { getSolarTermContext } from "@/lib/solar-terms";
import { WeatherCard } from "@/features/home/weather-card";
import { QuoteBar } from "@/features/home/quote-bar";

export default function HomePage() {
  // 中文注释：计算当前与下一节气信息
  const ctx = getSolarTermContext();
  const term = { id: ctx.current.id, name: ctx.current.name, imagePath: ctx.current.imagePath };
  const remainMs = ctx.msToNext;
  const remainDays = Math.floor(remainMs / 86400000);
  const remainHours = Math.floor((remainMs % 86400000) / 3600000);

  return (
    <div className="relative flex min-h-screen flex-col bg-background overflow-hidden">
      {/* 全页背景层：图片 + 轻暗化遮罩（确保在 body 渐变之上）*/}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 z-0 bg-cover bg-center bg-no-repeat bg-fixed"
        style={{ backgroundImage: `url(${term.imagePath})` }}
      />
      <div aria-hidden className="pointer-events-none absolute inset-0 z-0 bg-gradient-to-b from-black/40 via-black/20 to-transparent" />

      {/* 将内容包裹层设置为 flex-1，使页脚始终贴底 */}
      <div className="relative z-10 flex flex-1 flex-col">
        <LandingHeader />

        <main className="relative flex-1">
          <section className="mx-auto w-full max-w-6xl px-4 py-14 md:py-20">
            <div className="grid gap-8 lg:grid-cols-[3fr_2fr] lg:items-center">
              {/* 左侧文案卡片（毛玻璃） */}
              <div className="relative rounded-3xl ring-1 ring-inset ring-white/15 bg-white/10 p-6 text-white shadow-[0_12px_40px_rgba(2,6,23,0.18)] backdrop-blur-2xl backdrop-saturate-150 bg-clip-padding dark:bg-white/10">
                <div className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-br from-white/10 to-white/5" />
                {/* 主题染色：强度由 --home-glass-alpha 控制（0~0.6） */}
                <div
                  aria-hidden
                  className="pointer-events-none absolute inset-0 rounded-3xl"
                  style={{ background: "linear-gradient(135deg, hsl(var(--primary) / var(--home-glass-alpha, 0)) 0%, transparent 65%)" }}
                />
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center rounded-full bg-white/12 px-3 py-1 text-xs text-white/90">
                  当前节气：{ctx.current.name}
                </span>
                <span className="inline-flex items-center rounded-full bg-white/8 px-3 py-1 text-xs text-white/85">
                  下个节气：{ctx.next.name} · 还有 {remainDays} 天 {remainHours} 小时
                </span>
              </div>
              <h1 className="text-4xl font-bold leading-tight tracking-tight md:text-5xl">
                {ctx.current.name}
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-relaxed text-white/85">
                {ctx.current.desc || "节气更替，四时流转。"}
              </p>
              </div>

              {/* 右侧天气卡片（毛玻璃） */}
              <WeatherCard />
            </div>

            {/* 底部：每日一言（细行） */}
            <QuoteBar className="mt-10" />
          </section>
        </main>
      </div>

      <footer className="relative z-10 mt-auto border-t border-border/60 bg-background/70 py-6 text-center text-xs text-muted-foreground backdrop-blur">
        © {new Date().getFullYear()} AllYend • FastAPI + Next.js 全栈方案
      </footer>
    </div>
  );
}
