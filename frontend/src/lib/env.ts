const FALLBACK_API = "http://localhost:9093";
const FALLBACK_APP = "http://localhost:3000";

/**
 * 统一的前端环境变量访问入口
 */
export const env = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || FALLBACK_API,
  appBaseUrl: process.env.NEXT_PUBLIC_APP_BASE_URL?.trim() || FALLBACK_APP,
};

export function buildApiUrl(path: string) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${env.apiBaseUrl}${normalized}`;
}
