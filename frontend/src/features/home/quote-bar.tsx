"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface Hitokoto {
  hitokoto: string;
  from?: string;
}

export function QuoteBar({ className }: { className?: string }) {
  const [q, setQ] = useState<Hitokoto | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("https://v1.hitokoto.cn/?encode=json&charset=utf-8");
        const data = await res.json();
        if (!cancelled) setQ({ hitokoto: data.hitokoto, from: data.from });
      } catch {
        if (!cancelled) setQ({ hitokoto: "愿你出走半生，归来仍是少年。", from: "互联网" });
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div
      className={cn(
        "relative mx-auto w-full max-w-4xl rounded-full ring-1 ring-inset ring-white/15 bg-white/10 px-4 py-2 text-center text-sm text-white/90 shadow-[0_8px_28px_rgba(2,6,23,0.14)] backdrop-blur-2xl backdrop-saturate-150 bg-clip-padding",
        "dark:bg-white/10",
        className,
      )}
    >
      <div className="pointer-events-none absolute inset-0 rounded-full bg-gradient-to-r from-white/10 to-white/5" />
      {/* 主题染色：强度由 --home-glass-alpha 控制（0~0.6） */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-full"
        style={{ background: "linear-gradient(90deg, hsl(var(--primary) / var(--home-glass-alpha, 0)) 0%, transparent 70%)" }}
      />
      {loading ? "每日一言加载中…" : (
        <span>
          {q?.hitokoto}
          {q?.from ? <span className="text-white/60"> — {q.from}</span> : null}
        </span>
      )}
    </div>
  );
}
