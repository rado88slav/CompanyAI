import { companyApi } from "./client";
import type { ActivityEventList, ActivityFilters } from "../types/activity";

export function fetchActivity(filters: ActivityFilters = {}, signal?: AbortSignal) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const query = params.toString();
  return companyApi<ActivityEventList>(`/activity${query ? `?${query}` : ""}`, { signal });
}
