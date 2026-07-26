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

test("development session setup stores context without echoing the bearer token", async () => {
  sessionStorage.clear();
  render(<App />);

  expect(screen.getByRole("heading", { name: "Browser session" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Administrator bearer token"), { target: { value: "secret-bearer-token" } });
  fireEvent.change(screen.getByLabelText("Active company ID"), { target: { value: "0138bfbe-80af-4304-ad91-14d1914a9869" } });
  fireEvent.click(screen.getByRole("button", { name: "Save session" }));

  expect(sessionStorage.getItem("companyai.accessToken")).toBe("secret-bearer-token");
  expect(document.body.textContent).not.toContain("secret-bearer-token");
  expect(screen.getByRole("button", { name: "Clear session" })).toBeInTheDocument();
});

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
  ["/calls", "Call Operations"],
  ["/settings", "Settings"],
])("renders the %s placeholder route", async (path, title) => {
  setContext();
  window.history.pushState({}, "", path);
  render(<App />);

  expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
  expect(screen.getByText("Not configured yet")).toBeInTheDocument();
  expect(screen.getByText(/coming in a later dashboard stage/i)).toBeInTheDocument();
});

test("renders agent runtime tools and structured read-only result", async () => {
  setContext();
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(await jsonResponse({ items: [{
      key: "dashboard.summary.read",
      display_name: "Read dashboard summary",
      description: "Return safe dashboard summary.",
      category: "dashboard",
      risk_level: "low",
      requires_approval: false,
      runtime_registered: true,
      company_enabled: true,
    }]}))
    .mockResolvedValueOnce(await jsonResponse({
      tool_key: "dashboard.summary.read",
      status: "succeeded",
      executed_at: "2026-01-01T00:00:00Z",
      audit_event_id: "audit-1",
      result: summary,
    }));

  window.history.pushState({}, "", "/agent");
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Agent Activity" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Run read-only tool" }));
  expect(await screen.findByText("dashboard.summary.read")).toBeInTheDocument();
  expect(screen.getByText("audit-1")).toBeInTheDocument();
  expect(document.body.textContent?.toLowerCase()).not.toContain("secret-bearer-token");
});

test("renders agent runtime setup state when no tools are enabled", async () => {
  setContext();
  vi.spyOn(globalThis, "fetch").mockResolvedValue(await jsonResponse({ items: [] }));

  window.history.pushState({}, "", "/agent");
  render(<App />);

  expect(await screen.findByRole("heading", { name: "No runtime tools enabled" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Enable local tool" })).toBeInTheDocument();
});

test("renders provider connections from safe catalog and company data", async () => {
  setContext();
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(await jsonResponse([{
      key: "local-test-email",
      display_name: "Local Test Email",
      category: "email",
      authentication_type: "none",
      required_secret_fields: [],
      optional_secret_fields: [],
      configuration_fields: [],
      capabilities: ["email.send"],
      credentials_may_expire: false,
    }]))
    .mockResolvedValueOnce(await jsonResponse({
      items: [{
        id: "connection-1",
        company_id: "company-id",
        provider_key: "local-test-email",
        display_name: "Local Test Email",
        slug: "local-test-email",
        authentication_type: "none",
        status: "active",
        configuration: {},
        metadata: {},
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        activated_at: "2026-01-01T00:00:00Z",
        deactivated_at: null,
        revoked_at: null,
      }],
      total: 1,
      limit: 50,
      offset: 0,
    }));

  window.history.pushState({}, "", "/providers");
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Provider Connections" })).toBeInTheDocument();
  expect(screen.getAllByText("Local Test Email").length).toBeGreaterThan(0);
  expect(screen.getAllByText("email.send").length).toBeGreaterThan(0);
  expect(document.body.textContent?.toLowerCase()).not.toContain("secret");
});

test("renders inbox empty state and refresh", async () => {
  setContext();
  vi.spyOn(globalThis, "fetch").mockResolvedValue(await jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }));
  window.history.pushState({}, "", "/email");
  render(<App />);
  expect(await screen.findByRole("heading", { name: "No imported email" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
});

test("renders inbox error state", async () => {
  setContext();
  vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: false } as Response);
  window.history.pushState({}, "", "/email");
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Inbox unavailable" })).toBeInTheDocument();
});

test("renders exact approval content and decision actions", async () => {
  setContext();
  vi.spyOn(globalThis, "fetch").mockResolvedValue(await jsonResponse({items: [{
    id: "approval-1", status: "pending", requester_administrator_id: "requester-1",
    created_at: "2026-01-01T00:00:00Z", recipient_email: "person@example.com",
    subject: "Re: Hello", body: "Exact plain-text reply", inbound_email_id: "email-1",
    inbound_subject: "Hello", requested_action: "email.reply.send",
  }]}));
  window.history.pushState({}, "", "/approvals");
  render(<App />);
  expect(await screen.findByText("Exact plain-text reply")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve exact reply" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
});

test("renders safe audit fields without details", async () => {
  setContext();
  vi.spyOn(globalThis, "fetch").mockResolvedValue(await jsonResponse({items: [{
    id: "event-1", actor_type: "administrator", actor_administrator_id: "actor-1",
    action: "email.imported", resource_type: "inbound_email", resource_id: "email-1",
    created_at: "2026-01-01T00:00:00Z",
  }]}));
  window.history.pushState({}, "", "/audit");
  render(<App />);
  expect(await screen.findByText("email.imported")).toBeInTheDocument();
  expect(screen.queryByText("details")).not.toBeInTheDocument();
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
