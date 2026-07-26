const AUTH_TOKEN_KEY = "companyai.accessToken";
const COMPANY_ID_KEY = "companyai.companyId";
export const SESSION_EXPIRED_EVENT = "companyai:session-expired";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export type Administrator = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AvailableCompanyContext = {
  company: {
    id: string;
    name: string;
    slug: string;
    status: string;
    is_active: boolean;
    created_at: string;
    updated_at: string;
  };
  membership_role: string | null;
  is_platform_superuser: boolean;
};

export type AvailableCompanyContextList = {
  items: AvailableCompanyContext[];
  total: number;
  limit: number;
  offset: number;
};

export type FirstRunStatus = {
  initialized: boolean;
  setup_required: boolean;
  administrator_count: number;
  company_count: number;
  bootstrap_method: string;
};

export function accessToken(): string | null {
  return sessionStorage.getItem(AUTH_TOKEN_KEY);
}

export function selectedCompanyId(): string | null {
  return sessionStorage.getItem(COMPANY_ID_KEY);
}

export function hasAccessToken(): boolean {
  return Boolean(accessToken());
}

export function saveAccessToken(token: string): void {
  sessionStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function saveCompanyContext(id: string): void {
  sessionStorage.setItem(COMPANY_ID_KEY, id);
}

export function clearSessionContext(): void {
  sessionStorage.removeItem(AUTH_TOKEN_KEY);
  sessionStorage.removeItem(COMPANY_ID_KEY);
}

export function notifySessionExpired(): void {
  window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
}

export function companyId(): string {
  const value = selectedCompanyId();
  if (!value) throw new Error("An active company context is required.");
  return value;
}

async function parseJson<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = accessToken();
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) notifySessionExpired();
    throw new ApiError("The requested operation could not be completed.", response.status);
  }
  return parseJson<T>(response);
}

export async function login(email: string, password: string): Promise<void> {
  const response = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw new ApiError("Sign in failed.", response.status);
  const payload = await parseJson<{ access_token: string }>(response);
  saveAccessToken(payload.access_token);
}

export async function fetchFirstRunStatus(signal?: AbortSignal): Promise<FirstRunStatus> {
  const response = await fetch("/api/v1/first-run/status", { signal });
  if (!response.ok) throw new ApiError("Setup status is unavailable.", response.status);
  return parseJson<FirstRunStatus>(response);
}

export function fetchCurrentAdministrator(signal?: AbortSignal): Promise<Administrator> {
  return request<Administrator>("/api/v1/auth/me", { signal });
}

export function fetchAvailableCompanies(signal?: AbortSignal): Promise<AvailableCompanyContextList> {
  return request<AvailableCompanyContextList>("/api/v1/company-context/available-companies", { signal });
}

export function isAuthenticationError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

export async function companyApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = accessToken();
  const id = companyId();
  if (!token) throw new Error("Authentication is required.");
  const response = await fetch(`/api/v1/companies/${encodeURIComponent(id)}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`, "X-Company-ID": id,
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) notifySessionExpired();
    throw new ApiError("The requested operation could not be completed.", response.status);
  }
  return parseJson<T>(response);
}
