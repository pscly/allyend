"use client";

import { Lock, Sparkles, Ticket, Users } from "lucide-react";
import type { ComponentType, SVGProps } from "react";
import { useRegistrationSettingQuery } from "@/features/admin/queries";
import { useUpdateRegistrationModeMutation } from "@/features/admin/mutations";
import { useToast } from "@/hooks/use-toast";
import type { ApiError } from "@/lib/api/client";
import type { RegistrationMode } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const OPTIONS: Array<{
  value: RegistrationMode;
  label: string;
  description: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
}> = [
  {
    value: "open",
    label: "公开注册",
    description: "任何人都可以注册账号",
    icon: Users,
  },
  {
    value: "invite",
    label: "邀请码注册",
    description: "需持邀请码方可加入",
    icon: Ticket,
  },
  {
    value: "closed",
    label: "关闭注册",
    description: "仅管理员可创建账号",
    icon: Lock,
  },
];

export function RegistrationSettingsCard() {
  const { toast } = useToast();
  const settingsQuery = useRegistrationSettingQuery();
  const updateMode = useUpdateRegistrationModeMutation();

  const currentMode = settingsQuery.data?.registration_mode ?? "invite";

  const handleChange = async (next: RegistrationMode) => {
    if (next === currentMode) {
      return;
    }
    try {
      await updateMode.mutateAsync(next);
      toast({ title: "注册策略已更新", description: OPTIONS.find((option) => option.value === next)?.label });
    } catch (error) {
      const message = error instanceof ApiError ? error.payload?.detail ?? "更新失败" : "更新失败";
      toast({ title: "操作失败", description: message, variant: "destructive" });
    }
  };

  return (
    <section className="space-y-4 rounded-3xl border border-border/60 bg-card/70 p-6 shadow-surface">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
            <Sparkles className="h-5 w-5 text-primary" /> 注册策略
          </h2>
          <p className="text-sm text-muted-foreground">控制站点的开放程度，平衡易用性与安全性。</p>
        </div>
      </header>

      {settingsQuery.isLoading ? (
        <div className="grid gap-3 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-28 rounded-2xl border border-border/50 bg-muted/20" />
          ))}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-3">
          {OPTIONS.map(({ value, label, description, icon: Icon }) => {
            const selected = currentMode === value;
            return (
              <button
                key={value}
                type="button"
                className={cn(
                  "group flex h-full flex-col justify-between gap-2 rounded-2xl border border-border/60 bg-background/80 p-4 text-left transition-all duration-200",
                  selected && "border-primary/70 bg-primary/10 shadow-surface",
                  !selected && "hover:border-primary/40 hover:bg-primary/5",
                  (updateMode.isPending && !selected) && "cursor-not-allowed opacity-70",
                )}
                onClick={() => {
                  void handleChange(value);
                }}
                disabled={updateMode.isPending}
              >
                <div className="flex items-center gap-3">
                  <span
                    className={cn(
                      "flex h-10 w-10 items-center justify-center rounded-full border border-border/60 bg-background text-primary transition-colors",
                      selected && "border-primary/60 bg-primary text-primary-foreground",
                    )}
                  >
                    <Icon className="h-5 w-5" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-foreground">{label}</p>
                    <p className="text-xs text-muted-foreground">{description}</p>
                  </div>
                </div>
                {selected ? (
                  <span className="self-start rounded-full bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground">
                    当前策略
                  </span>
                ) : (
                  <span className="self-start text-xs text-primary transition-colors group-hover:text-primary/80">
                    点击选择
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {settingsQuery.isError && (
        <p className="text-xs text-destructive">
          {(settingsQuery.error as ApiError | undefined)?.payload?.detail ?? "获取注册策略失败"}
        </p>
      )}
    </section>
  );
}




