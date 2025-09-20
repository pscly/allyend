export interface TokenResponse {
  access_token: string;
  token_type: string;
}

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
}

export interface CrawlerSummary {
  id: number;
  local_id: number | null;
  name: string;
  created_at: string;
  last_heartbeat: string | null;
  last_source_ip: string | null;
  is_public: boolean;
  public_slug: string | null;
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
