import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { App } from "../App";
import type { DashboardSummary } from "../types/dashboard";

const summary: DashboardSummary = {
  service: {
    status: "ok",
    readiness: "reachable",
    environment: "test",
    version: "1.0.0",
  },
  counts: {
    provider_connections: 2,
    enabled_provider_connections: 1,
    provider_credentials: 0,
    pending_approvals: 3,
    provider_executions: 5,
    failed_provider_executions: 1,
    audit_events: 8,
  },
  recent_audit_events: [],
};

function setContext() {
  sessionStorage.setItem("companyai.accessToken", "test-session-token");
  sessionStorage.setItem("companyai.companyId", "company-id");
}

function jsonResponse(body: unknown, ok = true) {
  return Promise.resolve({
    ok,
    json: () => Promise.resolve(body),
  } as Response);
}

test("renders the overview loading state and successful real summary", async () => {
  setContext();
  let resolveRequest!: (response: Response) => void;
  vi.spyOn(globalThis, "fetch").mockReturnValue(
    new Promise((resolve) => {
      resolveRequest = resolve;
    }),
  );

  render(<App />);

  expect(screen.getByText("Loading current operations")).toBeInTheDocument();
  resolveRequest(await jsonResponse(summary));

  expect(await screen.findByText("Operational clarity, at a glance.")).toBeInTheDocument();
  expect(screen.getByText("Provider connections")).toBeInTheDocument();
  expect(screen.getByText("No audit events have been recorded for this company yet.")).toBeInTheDocument();
  expect(screen.getByText("test")).toBeInTheDocument();
});

test("renders an error state and retries the summary request", async () => {
  setContext();
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce({ ok: false } as Response)
    .mockResolvedValueOnce(await jsonResponse(summary));

  render(<App />);

  expect(await screen.findByText("Overview unavailable")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(await screen.findByText("CompanyAI API")).toBeInTheDocument();
});

test.each([
  ["/agent", "Agent Activity"],
  ["/providers", "Provider Connections"],
  ["/email", "Email Operations"],
  ["/calls", "Call Operations"],
  ["/approvals", "Approvals"],
  ["/audit", "Audit Log"],
  ["/settings", "Settings"],
])("renders the %s placeholder route", async (path, title) => {
  window.history.pushState({}, "", path);
  render(<App />);

  expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
  expect(screen.getByText("Not configured yet")).toBeInTheDocument();
  expect(screen.getByText(/coming in a later dashboard stage/i)).toBeInTheDocument();
});

test("overview output does not render secret-bearing field names", async () => {
  setContext();
  vi.spyOn(globalThis, "fetch").mockResolvedValue(await jsonResponse(summary));

  const { container } = render(<App />);
  await screen.findByText("CompanyAI API");

  const rendered = container.textContent?.toLowerCase() ?? "";
  for (const forbidden of [
    "encrypted_payload",
    "nonce",
    "encryption_key_id",
    "keyring",
    "access_token",
  ]) {
    expect(rendered).not.toContain(forbidden);
  }
});
