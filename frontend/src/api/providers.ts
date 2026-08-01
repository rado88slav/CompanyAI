import { companyApi } from "./client";
import type {
  ProviderConnection,
  ProviderConnectionCreate,
  ProviderConnectionTestResult,
  ProviderCredentialCreate,
  ProviderDescriptor,
} from "../types/provider";

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

export function createProviderConnection(
  payload: ProviderConnectionCreate,
): Promise<ProviderConnection> {
  return companyApi("/provider-connections", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createProviderCredential(
  connectionId: string,
  payload: ProviderCredentialCreate,
): Promise<unknown> {
  return companyApi(`/provider-connections/${encodeURIComponent(connectionId)}/credentials`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function testProviderConnectionSmtp(
  connectionId: string,
): Promise<ProviderConnectionTestResult> {
  return companyApi(`/provider-connections/${encodeURIComponent(connectionId)}/test-smtp`, {
    method: "POST",
  });
}

export function testProviderConnectionImap(
  connectionId: string,
): Promise<ProviderConnectionTestResult> {
  return companyApi(`/provider-connections/${encodeURIComponent(connectionId)}/test-imap`, {
    method: "POST",
  });
}

export function activateProviderConnection(
  connectionId: string,
): Promise<ProviderConnection> {
  return companyApi(`/provider-connections/${encodeURIComponent(connectionId)}/activate`, {
    method: "POST",
  });
}
