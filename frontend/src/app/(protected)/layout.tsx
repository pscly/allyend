import type { ReactNode } from "react";

import { ProtectedLayout } from "@/components/layout/protected-layout";

export default function ProtectedRouteLayout({
  children,
}: {
  children: ReactNode;
}) {
  return <ProtectedLayout>{children}</ProtectedLayout>;
}
