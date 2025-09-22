export type PublicLinkType = "crawler" | "api_key" | "group";

export interface PublicLinkBaseSummary {
  type: PublicLinkType;
  slug: string;
  name?: string | null;
  owner_id?: number | null;
  owner_name?: string | null;
  link_description?: string | null;
  link_created_at?: string | null;
  allow_logs: boolean;
}

export interface PublicCrawlerSummary extends PublicLinkBaseSummary {
  type: "crawler";
  crawler_id: number;
  local_id?: number | null;
  status: string;
  last_heartbeat?: string | null;
  last_source_ip?: string | null;
}

export interface PublicApiKeySummary extends PublicLinkBaseSummary {
  type: "api_key";
  api_key_id: number;
  local_id?: number | null;
  last_used_at?: string | null;
  last_used_ip?: string | null;
  crawler_name?: string | null;
  crawler_status?: string | null;
}

export interface PublicGroupCrawlerEntry {
  id: number;
  local_id?: number | null;
  name?: string | null;
  status: string;
  last_heartbeat?: string | null;
  last_source_ip?: string | null;
}

export interface PublicGroupSummary extends PublicLinkBaseSummary {
  type: "group";
  group_id: number;
  group_slug?: string | null;
  group_name?: string | null;
  crawler_total: number;
  status_breakdown: Record<string, number>;
  crawlers: PublicGroupCrawlerEntry[];
}

export type PublicLinkSummary =
  | PublicCrawlerSummary
  | PublicApiKeySummary
  | PublicGroupSummary;
