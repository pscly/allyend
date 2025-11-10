export interface ThemeSetting {
  theme_name: string;
  theme_primary: string;
  theme_secondary: string;
  theme_background: string;
  is_dark_mode: boolean;
}

export interface ThemeSettingUpdateInput {
  themeName?: string | null;
  themePrimary?: string | null;
  themeSecondary?: string | null;
  themeBackground?: string | null;
  isDarkMode?: boolean;
}

export interface UserProfile {
  id: number;
  username: string;
  display_name: string | null;
  email: string | null;
  avatar_url?: string | null;
  role: "user" | "admin" | "superadmin";
  is_active: boolean;
  is_root_admin?: boolean;
  group?: UserGroup;
  theme_name?: string;
  theme_primary?: string;
  theme_secondary?: string;
  theme_background?: string;
  is_dark_mode?: boolean;
  created_at?: string;
}

export interface UserGroup {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  enable_crawlers: boolean;
  enable_files: boolean;
}

export interface FileToken {
  id: number;
  token: string;
  name: string | null;
  description: string | null;
  is_active: boolean;
  allowed_ips: string | null;
  allowed_cidrs: string | null;
  usage_count: number;
  last_used_at: string | null;
  created_at: string;
}

export interface FileEntry {
  id: number;
  original_name: string;
  description: string | null;
  content_type: string | null;
  size_bytes: number;
  visibility: "private" | "group" | "public" | "disabled";
  is_anonymous: boolean;
  download_count: number;
  created_at: string;
  owner_id: number | null;
  owner_group_id: number | null;
  download_name?: string | null;
  download_url?: string | null;
}

export interface FileAccessLog {
  id: number;
  action: "upload" | "download" | "delete" | "list";
  ip_address: string | null;
  user_agent: string | null;
  status: string;
  created_at: string;
  file_id: number | null;
  user_id: number | null;
  token_id: number | null;
}

export interface FileUploadResponse {
  file_id: number;
  original_name: string;
  visibility: string;
  size_bytes: number;
}

export interface CrawlerGroup {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  color: string | null;
  crawler_count?: number;
  created_at: string;
}

export interface QuickLink {
  id: number;
  slug: string;
  target_type: 'crawler' | 'api_key' | 'group';
  description: string | null;
  is_active: boolean;
  allow_logs: boolean;
  created_at: string;
  crawler_id?: number | null;
  crawler_local_id?: number | null;
  api_key_id?: number | null;
  api_key_local_id?: number | null;
  group_id?: number | null;
  group_slug?: string | null;
  group_name?: string | null;
}

export interface ApiKey {
  id: number;
  local_id: number;
  key: string;
  name: string | null;
  description: string | null;
  active: boolean;
  is_public: boolean;
  created_at: string;
  last_used_at: string | null;
  last_used_ip: string | null;
  allowed_ips: string | null;
  group: CrawlerGroup | null;
  crawler_id: number | null;
  crawler_local_id: number | null;
  crawler_name: string | null;
  crawler_status: string | null;
  crawler_last_heartbeat: string | null;
  crawler_public_slug: string | null;
  crawler_active?: boolean;
}

export interface CrawlerSummary {
  id: number;
  local_id: number | null;
  name: string;
  created_at: string;
  last_heartbeat: string | null;
  last_source_ip: string | null;
  status: string;
  status_changed_at: string | null;
  uptime_ratio: number | null;
  uptime_minutes: number | null;
  heartbeat_payload: Record<string, unknown> | null;
  is_public: boolean;
  public_slug: string | null;
  is_hidden?: boolean | null;
  pinned_at?: string | null;
  pinned?: boolean | null;
  api_key_id: number | null;
  api_key_local_id: number | null;
  api_key_name: string | null;
  api_key_active: boolean | null;
  group: CrawlerGroup | null;
  config_assignment_id?: number | null;
  config_assignment_name?: string | null;
  config_assignment_version?: number | null;
  config_assignment_format?: string | null;
}


export interface CrawlerConfigTemplate {
  id: number;
  name: string;
  description: string | null;
  format: "json" | "yaml";
  content: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CrawlerConfigAssignment {
  id: number;
  name: string;
  description: string | null;
  target_type: "crawler" | "api_key" | "group";
  target_id: number;
  format: "json" | "yaml";
  content: string;
  version: number;
  is_active: boolean;
  template_id: number | null;
  template_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface CrawlerConfigFetch {
  has_config: boolean;
  assignment_id: number | null;
  name: string | null;
  format: "json" | "yaml" | null;
  version: number | null;
  content: string | null;
  updated_at: string | null;
}

export type AlertChannel = {
  type: "email" | "webhook";
  target: string;
  enabled: boolean;
  note?: string | null;
  status?: string;
};

export interface CrawlerAlertRule {
  id: number;
  name: string;
  description: string | null;
  trigger_type: "status_offline" | "payload_threshold";
  target_type: "all" | "group" | "crawler" | "api_key";
  target_ids: number[];
  status_from: string | null;
  status_to: string | null;
  payload_field: string | null;
  comparator: "gt" | "ge" | "lt" | "le" | "eq" | "ne" | null;
  threshold: number | null;
  consecutive_failures: number;
  cooldown_minutes: number;
  channels: AlertChannel[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_triggered_at: string | null;
}

export interface CrawlerAlertEvent {
  id: number;
  rule_id: number;
  crawler_id: number;
  crawler_local_id: number | null;
  crawler_name: string | null;
  triggered_at: string;
  status: string;
  message: string | null;
  payload: Record<string, unknown>;
  channel_results: Array<Record<string, unknown>>;
  error: string | null;
}

export interface CrawlerHeartbeat {
  id: number;
  status: string;
  payload: Record<string, unknown> | null;
  source_ip: string | null;
  created_at: string;
}

export interface CrawlerCommand {
  id: number;
  command: string;
  payload: Record<string, unknown> | null;
  status: string;
  result: Record<string, unknown> | null;
  created_at: string;
  processed_at: string | null;
  expires_at: string | null;
}

// =====================
// 应用 JSON 配置 - 前端类型
// =====================

export interface AppConfigListItem {
  app: string;
  description: string | null;
  enabled: boolean;
  pinned?: boolean | null;
  pinned_at?: string | null;
  updated_at: string;
  read_count: number;
}

export interface AppConfigDetail {
  app: string;
  description: string | null;
  content: Record<string, unknown>;
  version: number;
  enabled: boolean;
  pinned?: boolean | null;
  pinned_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CrawlerRun {
  id: number;
  status: string;
  started_at: string;
  ended_at: string | null;
  last_heartbeat: string | null;
  source_ip: string | null;
}

export interface CrawlerLog {
  id: number;
  level: string;
  level_code: number;
  message: string;
  ts: string;
  run_id: number | null;
  crawler_id: number;
  crawler_local_id: number | null;
  crawler_name: string | null;
  source_ip: string | null;
  api_key_id: number | null;
  api_key_local_id: number | null;
}

export interface InviteCode {
  id: number;
  code: string;
  note: string | null;
  allow_admin: boolean;
  max_uses: number | null;
  used_count: number;
  expires_at: string | null;
  created_at: string;
}

export interface AdminUserSummary {
  id: number;
  username: string;
  role: "user" | "admin" | "superadmin";
  is_active: boolean;
  is_root_admin: boolean;
  invited_by: string | null;
  created_at: string;
  group: UserGroup | null;
}

export type AdminUserRole = UserProfile["role"];

export interface AdminUserUpdatePayload {
  role?: AdminUserRole | null;
  group_id?: number | null;
  is_active?: boolean;
}

export type RegistrationMode = "open" | "invite" | "closed";

export interface RegistrationSettings {
  registration_mode: RegistrationMode;
}
