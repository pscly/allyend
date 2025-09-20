import { ShieldCheck } from "lucide-react";

import { AdminUsersSection } from "@/features/admin/components/admin-users-section";
import { AdminInvitesSection } from "@/features/admin/components/admin-invites-section";
import { RegistrationSettingsCard } from "@/features/admin/components/registration-settings-card";

export default function AdminPage() {
  return (
    <section className="space-y-8">
      <header className="space-y-3">
        <span className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
          <ShieldCheck className="h-4 w-4" /> 系统安全由此掌控
        </span>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">后台管理控制中心</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          查看成员详情、分发邀请码以及配置注册策略，保障系统在安全合规的同时保持灵活易用。
        </p>
      </header>

      <div className="space-y-6">
        <AdminUsersSection />
        <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-[1.1fr_1fr]">
          <RegistrationSettingsCard />
          <AdminInvitesSection />
        </div>
      </div>
    </section>
  );
}
