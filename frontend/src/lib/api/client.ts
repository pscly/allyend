import { buildApiUrl } from "@/lib/env";

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface RequestOptions<TBody = unknown> {
  /**
   * 通过 zustand 获取到的访问令牌
   */
  token?: string | null;
  /**
   * JSON 请求体或 FormData
   */
  body?: TBody | FormData;
  /**
   * 附加查询参数
   */
  searchParams?: Record<string, string | number | boolean | undefined>;
  /**
   * 额外的 fetch 配置
   */
  init?: RequestInit;
}

export interface ApiErrorPayload {
  detail?: string;
  message?: string;
}

export class ApiError extends Error {
  status: number;
  payload: ApiErrorPayload | null;

  constructor(status: number, payload: ApiErrorPayload | null, message?: string) {
    super(message ?? payload?.detail ?? payload?.message ?? "接口请求失败");
    this.status = status;
    this.payload = payload;
  }
}

async function parseResponse<T>(response: Response): Promise<T | null> {
  if (response.status === 204) {
    return null;
  }
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    return (await response.json()) as T;
  }
  return null;
}

function appendSearchParams(url: string, params?: Record<string, string | number | boolean | undefined>) {
  if (!params) return url;
  const usp = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) return;
    usp.append(key, String(value));
  });
  return usp.size > 0 ? `${url}?${usp.toString()}` : url;
}

function isFormData(payload: unknown): payload is FormData {
  return typeof FormData !== "undefined" && payload instanceof FormData;
}

async function request<TResponse, TBody = unknown>(
  method: HttpMethod,
  path: string,
  options: RequestOptions<TBody> = {},
): Promise<TResponse> {
  const url = appendSearchParams(buildApiUrl(path), options.searchParams);
  const headers = new Headers(options.init?.headers ?? {});
  headers.set("Accept", "application/json");

  const init: RequestInit = {
    method,
    ...options.init,
    headers,
    cache: options.init?.cache ?? "no-store",
    credentials: options.init?.credentials ?? "include",
  };

  const body = options.body;
  if (body !== undefined && body !== null) {
    if (isFormData(body)) {
      init.body = body;
    } else {
      init.body = JSON.stringify(body);
      headers.set("Content-Type", "application/json");
    }
  }

  const token = options.token ?? headers.get("Authorization") ?? undefined;
  if (token && typeof token === "string") {
    headers.set("Authorization", token.startsWith("Bearer") ? token : `Bearer ${token}`);
  }

  const response = await fetch(url, init);
  if (!response.ok) {
    const payload = await parseResponse<ApiErrorPayload>(response);
    throw new ApiError(response.status, payload, payload?.detail);
  }
  const data = await parseResponse<TResponse>(response);
  return data as TResponse;
}

export const apiClient = {
  get: <T>(path: string, options?: RequestOptions) => request<T>("GET", path, options),
  post: <T, TBody = unknown>(path: string, body?: TBody | FormData, options?: RequestOptions<TBody>) =>
    request<T, TBody>("POST", path, { ...options, body }),
  patch: <T, TBody = unknown>(path: string, body?: TBody | FormData, options?: RequestOptions<TBody>) =>
    request<T, TBody>("PATCH", path, { ...options, body }),
  put: <T, TBody = unknown>(path: string, body?: TBody | FormData, options?: RequestOptions<TBody>) =>
    request<T, TBody>("PUT", path, { ...options, body }),
  delete: <T>(path: string, options?: RequestOptions) => request<T>("DELETE", path, options),
};

export type ApiClient = typeof apiClient;
