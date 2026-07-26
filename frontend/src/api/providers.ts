import { companyApi } from "./client";
import type { ProviderConnection, ProviderDescriptor } from "../types/provider";

const AUTH_TOKEN_KEY = "companyai.accessToken";

export async function fetchProviderTypes(
  signal?: AbortSignal,
): Promise<ProviderDescriptor[]> {
  const accessToken = sessionStorage.getItem(AUTH_TOKEN_KEY);
  if (!accessToken) throw new Error("Authentication is required.");

  const response = await fetch("/api/v1/provider-types", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
    signal,
  });

  if (!response.ok) {
    throw new Error("Provider types are currently unavailable.");
  }

  return response.json() as Promise<ProviderDescriptor[]>;
}

export function fetchProviderConnections(
  signal?: AbortSignal,
): Promise<{ items: ProviderConnection[]; total: number; limit: number; offset: number }> {
  return companyApi("/provider-connections", { signal });
}
