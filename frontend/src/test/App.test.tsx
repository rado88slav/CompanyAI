import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { App } from "../App";
import type { DashboardSummary } from "../types/dashboard";

const administrator = {
  id: "admin-1",
  email: "admin@example.test",
  full_name: "Admin User",
  is_active: true,
  is_superuser: false,
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const companyContexts = {
  items: [
    {
      company: {
        id: "company-id",
        name: "Company Test",
        slug: "company-test",
        status: "active",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
      membership_role: "admin",
      is_platform_superuser: false,
    },
    {
      company: {
        id: "company-two",
        name: "Second Company",
        slug: "second-company",
        status: "active",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
      membership_role: "viewer",
      is_platform_superuser: false,
    },
  ],
  total: 2,
  limit: 100,
  offset: 0,
};

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

function setToken(companyId = "company-id") {
  sessionStorage.setItem("companyai.accessToken", "opaque-test-session-value");
  sessionStorage.setItem("companyai.companyId", companyId);
}

function jsonResponse(body: unknown, ok = true, status = ok ? 200 : 500) {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(body),
  } as Response);
}

async function bootstrapResponses() {
  return [await jsonResponse(administrator), await jsonResponse(companyContexts)];
}

async function authenticatedFetchMock(...responses: Response[]) {
  const fetchMock = vi.spyOn(globalThis, "fetch");
  for (const response of await bootstrapResponses()) fetchMock.mockResolvedValueOnce(response);
  for (const response of responses) fetchMock.mockResolvedValueOnce(response);
  return fetchMock;
}

beforeEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
  window.history.pushState({}, "", "/");
});

test("login flow stores the token without rendering it and selects an authorized company", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(await jsonResponse({ access_token: "opaque-login-session-value" }))
    .mockResolvedValueOnce(await jsonResponse(administrator))
    .mockResolvedValueOnce(await jsonResponse(companyContexts));

  render(<App />);

  expect(await screen.findByRole("heading", { name: "CompanyAI dashboard" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ADMIN@example.test" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "not-rendered" } });
  fireEvent.click(screen.getByRole("button", { name: "Login" }));

  expect(await screen.findByRole("button", { name: "Logout" })).toBeInTheDocument();
  expect(sessionStorage.getItem("companyai.accessToken")).toBe("opaque-login-session-value");
  expect(sessionStorage.getItem("companyai.companyId")).toBe("company-id");
  expect(document.body.textContent).not.toContain("opaque-login-session-value");
});

test("saved unauthorized company falls back to the first available company", async () => {
  setToken("unauthorized-company");
  await authenticatedFetchMock(await jsonResponse(summary));

  render(<App />);

  expect(await screen.findByRole("combobox", { name: "Active company" })).toHaveValue("company-id");
  expect(sessionStorage.getItem("companyai.companyId")).toBe("company-id");
});

test("empty company list renders a protected empty state", async () => {
  setToken();
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(await jsonResponse(administrator))
    .mockResolvedValueOnce(await jsonResponse({ items: [], total: 0, limit: 100, offset: 0 }));

  render(<App />);

  expect(await screen.findByRole("heading", { name: "No companies available" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Provider Connections" })).toBeInTheDocument();
});

test("expired session clears protected context", async () => {
  setToken();
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(await jsonResponse({}, false, 401));

  render(<App />);

  expect(await screen.findByText("Your session expired. Please sign in again.")).toBeInTheDocument();
  expect(sessionStorage.getItem("companyai.accessToken")).toBeNull();
});

test("renders the overview loading state and successful real summary", async () => {
  setToken();
  let resolveRequest!: (response: Response) => void;
  const fetchMock = vi.spyOn(globalThis, "fetch");
  for (const response of await bootstrapResponses()) fetchMock.mockResolvedValueOnce(response);
  fetchMock.mockReturnValueOnce(
    new Promise((resolve) => {
      resolveRequest = resolve;
    }),
  );

  render(<App />);

  expect(await screen.findByText("Loading current operations")).toBeInTheDocument();
  resolveRequest(await jsonResponse(summary));

  expect(await screen.findByText("Operational clarity, at a glance.")).toBeInTheDocument();
  expect(screen.getByText("Provider connections")).toBeInTheDocument();
  expect(screen.getByText("No audit events have been recorded for this company yet.")).toBeInTheDocument();
  expect(screen.getByText("test")).toBeInTheDocument();
});

test("renders an error state and retries the summary request", async () => {
  setToken();
  const fetchMock = await authenticatedFetchMock(
    { ok: false, status: 500 } as Response,
    await jsonResponse(summary),
  );

  render(<App />);

  expect(await screen.findByText("Overview unavailable")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
  expect(await screen.findByText("CompanyAI API")).toBeInTheDocument();
});

test.each([
  ["/calls", "Call Operations"],
  ["/settings", "Settings"],
])("renders the %s protected placeholder route", async (path, title) => {
  setToken();
  window.history.pushState({}, "", path);
  await authenticatedFetchMock();
  render(<App />);

  expect(await screen.findByRole("heading", { name: title })).toBeInTheDocument();
  expect(screen.getByText("Not configured yet")).toBeInTheDocument();
});

test("company selector changes the active company for protected requests", async () => {
  setToken();
  const fetchMock = await authenticatedFetchMock(
    await jsonResponse(summary),
    await jsonResponse(summary),
  );

  render(<App />);
  expect(await screen.findByText("CompanyAI API")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Active company"), { target: { value: "company-two" } });

  await waitFor(() => expect(sessionStorage.getItem("companyai.companyId")).toBe("company-two"));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
  expect(fetchMock).toHaveBeenLastCalledWith(
    "/api/v1/companies/company-two/dashboard/summary",
    expect.objectContaining({
      headers: expect.objectContaining({ "X-Company-ID": "company-two" }),
    }),
  );
});

test("renders agent runtime tools and structured read-only result", async () => {
  setToken();
  await authenticatedFetchMock(
    await jsonResponse({ items: [{
      key: "dashboard.summary.read",
      display_name: "Read dashboard summary",
      description: "Return safe dashboard summary.",
      category: "dashboard",
      risk_level: "low",
      requires_approval: false,
      runtime_registered: true,
      company_enabled: true,
    }, {
      key: "email.campaigns.list",
      display_name: "List mock email campaigns",
      description: "Return deterministic mock campaigns.",
      category: "email",
      risk_level: "low",
      requires_approval: false,
      runtime_registered: true,
      company_enabled: true,
    }]}),
    await jsonResponse({
      tool_key: "dashboard.summary.read",
      status: "succeeded",
      executed_at: "2026-01-01T00:00:00Z",
      audit_event_id: "audit-1",
      result: summary,
    }),
  );

  window.history.pushState({}, "", "/agent");
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Agent Activity" })).toBeInTheDocument();
  expect(screen.getByText("List mock email campaigns")).toBeInTheDocument();
  fireEvent.click(screen.getAllByRole("button", { name: "Run read-only tool" })[0]);
  expect(await screen.findByText("dashboard.summary.read")).toBeInTheDocument();
  expect(screen.getByText("audit-1")).toBeInTheDocument();
  expect(document.body.textContent?.toLowerCase()).not.toContain("opaque-test-session-value");
});

test("renders agent runtime setup state when no tools are enabled", async () => {
  setToken();
  await authenticatedFetchMock(await jsonResponse({ items: [] }));

  window.history.pushState({}, "", "/agent");
  render(<App />);

  expect(await screen.findByRole("heading", { name: "No runtime tools enabled" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Enable local tool" })).toBeInTheDocument();
});

test("renders provider connections from safe catalog and company data", async () => {
  setToken();
  await authenticatedFetchMock(
    await jsonResponse([{
      key: "local-test-email",
      display_name: "Local Test Email",
      category: "email",
      authentication_type: "none",
      required_secret_fields: [],
      optional_secret_fields: [],
      configuration_fields: [],
      capabilities: ["email.send"],
      credentials_may_expire: false,
    }]),
    await jsonResponse({
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
    }),
  );

  window.history.pushState({}, "", "/providers");
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Provider Connections" })).toBeInTheDocument();
  expect(screen.getAllByText("Local Test Email").length).toBeGreaterThan(0);
  expect(screen.getAllByText("email.send").length).toBeGreaterThan(0);
  expect(document.body.textContent?.toLowerCase()).not.toContain("secret");
});

test("renders inbox empty state and refresh", async () => {
  setToken();
  await authenticatedFetchMock(
    await jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }),
    await jsonResponse({ items: [{
      id: "campaign-1",
      company_id: "company-id",
      provider_key: "local_mock_email",
      external_campaign_id: "mock-welcome",
      name: "Welcome sequence",
      status: "draft",
      audience_count: 42,
      sent_count: 0,
      reply_count: 0,
      bounce_count: 0,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
    }], total: 1, limit: 50, offset: 0 }),
  );
  window.history.pushState({}, "", "/email");
  render(<App />);
  expect(await screen.findByRole("heading", { name: "No imported email" })).toBeInTheDocument();
  expect(screen.getByText("Welcome sequence")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
});

test("renders inbox error state", async () => {
  setToken();
  await authenticatedFetchMock({ ok: false, status: 500 } as Response);
  window.history.pushState({}, "", "/email");
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Inbox unavailable" })).toBeInTheDocument();
});

test("renders exact approval content and decision actions", async () => {
  setToken();
  await authenticatedFetchMock(await jsonResponse({items: [{
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
  setToken();
  await authenticatedFetchMock(await jsonResponse({items: [{
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
  setToken();
  await authenticatedFetchMock(await jsonResponse(summary));

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
