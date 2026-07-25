const AUTH_TOKEN_KEY = "companyai.accessToken";
const COMPANY_ID_KEY = "companyai.companyId";

export function companyId(): string {
  const value = sessionStorage.getItem(COMPANY_ID_KEY);
  if (!value) throw new Error("An active company context is required.");
  return value;
}

export async function companyApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = sessionStorage.getItem(AUTH_TOKEN_KEY);
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
  if (!response.ok) throw new Error("The requested operation could not be completed.");
  return response.json() as Promise<T>;
}
