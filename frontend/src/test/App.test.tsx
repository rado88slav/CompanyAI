import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { App } from "../App";
import type { ActivityEventList } from "../types/activity";
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

const activity: ActivityEventList = {
  items: [{
    id: "activity-1",
    company_id: "company-id",
    occurred_at: "2026-01-01T00:00:00Z",
    category: "provider",
    source: "provider_connection",
    action: "provider_connection.created",
    title: "Provider Connection Created",
    summary: "Provider operation created on provider connection.",
    status: "recorded",
    severity: "info",
    actor_display: "Administrator",
    entity_type: "provider_connection",
    entity_id: "connection-1",
    safe_details: { provider_key: "local_test_email", status: "active" },
    correlation_id: "connection-1",
  }],
  total: 1,
  limit: 4,
  offset: 0,
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
  await authenticatedFetchMock(await jsonResponse(summary), await jsonResponse(activity));

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
  fetchMock.mockResolvedValueOnce(await jsonResponse(activity));

  render(<App />);

  expect(await screen.findByText("Loading operations dashboard")).toBeInTheDocument();
  resolveRequest(await jsonResponse(summary));

  expect(await screen.findByText("Command the day with confidence.")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "All critical services" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Active workspace" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Jump into work" })).toBeInTheDocument();
  expect(screen.getByText("Provider Connection Created")).toBeInTheDocument();
  expect(screen.getByText("3 approval requests awaiting review.")).toBeInTheDocument();
});

test("renders an error state and retries the summary request", async () => {
  setToken();
  const fetchMock = await authenticatedFetchMock(
    { ok: false, status: 500 } as Response,
    await jsonResponse({ items: [], total: 0, limit: 4, offset: 0 }),
    await jsonResponse(summary),
    await jsonResponse(activity),
  );

  render(<App />);

  expect(await screen.findByText("Operations dashboard unavailable")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(6));
  expect(await screen.findByText("Command the day with confidence.")).toBeInTheDocument();
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

test("renders protected System Status health indicators", async () => {
  setToken();
  const fetchMock = await authenticatedFetchMock(await jsonResponse(summary));
  window.history.pushState({}, "", "/system-status");
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Operational health without the noise." })).toBeInTheDocument();
  expect(screen.getAllByText("Company Test").length).toBeGreaterThan(0);
  expect(await screen.findByRole("heading", { name: "Backend" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Database" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Lemlist" })).toBeInTheDocument();
  expect(screen.getByText("No call placement or paid telephony action is enabled")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/companies/company-id/dashboard/summary",
    expect.objectContaining({
      method: "GET",
      headers: expect.objectContaining({ "X-Company-ID": "company-id" }),
    }),
  );
});

test("renders Documentation Center, switches language, searches and navigates articles", async () => {
  setToken();
  await authenticatedFetchMock();
  window.history.pushState({}, "", "/documentation/providers");
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Learn CompanyAI without leaving the dashboard." })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Providers" })).toBeInTheDocument();
  expect(screen.getByText("On this page")).toBeInTheDocument();
  const breadcrumb = screen.getByRole("navigation", { name: "Breadcrumb" });
  expect(breadcrumb).toHaveTextContent("Overview");
  expect(breadcrumb).toHaveTextContent("Documentation");
  expect(breadcrumb).toHaveTextContent("Provider Connections");

  fireEvent.change(screen.getByLabelText("Language"), { target: { value: "bg" } });
  expect(await screen.findByRole("heading", { name: "Providers" })).toBeInTheDocument();
  expect(screen.getAllByText("Интеграции").length).toBeGreaterThan(0);
  expect(sessionStorage.getItem("companyai.docsLanguage")).toBe("bg");

  fireEvent.change(screen.getByLabelText("Search documentation"), { target: { value: "approval" } });
  expect(await screen.findByRole("heading", { name: "Search results" })).toBeInTheDocument();
  const approvalsDocLink = screen.getAllByRole("link", { name: /Approvals/i }).find((link) => (
    link.getAttribute("href") === "/documentation/approvals"
  ));
  expect(approvalsDocLink).toBeDefined();
  fireEvent.click(approvalsDocLink!);
  expect(await screen.findByRole("heading", { name: "Approvals" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Next:/ })).toBeInTheDocument();
});

test("company selector changes the active company for protected requests", async () => {
  setToken();
  const fetchMock = await authenticatedFetchMock(
    await jsonResponse(summary),
    await jsonResponse(activity),
    await jsonResponse(summary),
    await jsonResponse(activity),
  );

  render(<App />);
  expect(await screen.findByText("Command the day with confidence.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Active company"), { target: { value: "company-two" } });

  await waitFor(() => expect(sessionStorage.getItem("companyai.companyId")).toBe("company-two"));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(6));
  expect(fetchMock).toHaveBeenCalledWith(
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
  expect(screen.getByRole("link", { name: "How Agent works" })).toHaveAttribute("href", "/documentation/agent");
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
  expect(screen.getByRole("link", { name: "Learn more" })).toHaveAttribute("href", "/documentation/providers");
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
  expect(screen.getByRole("link", { name: "Email Campaign Guide" })).toHaveAttribute("href", "/documentation/email-campaigns");
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
  await authenticatedFetchMock(await jsonResponse(activity));
  window.history.pushState({}, "", "/audit");
  render(<App />);
  expect(await screen.findByText("provider_connection.created")).toBeInTheDocument();
  expect(screen.queryByText("details")).not.toBeInTheDocument();
});

test("renders Activity Center timeline and filters safe details", async () => {
  setToken();
  const fetchMock = await authenticatedFetchMock(
    await jsonResponse(activity),
    await jsonResponse({ ...activity, items: [] }),
  );
  window.history.pushState({}, "", "/activity");
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Everything that happened, in one place." })).toBeInTheDocument();
  expect(await screen.findByText("Provider Connection Created")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Show safe details" }));
  expect(await screen.findByText("local_test_email")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Agent" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
  expect(await screen.findByRole("heading", { name: "No matching activity" })).toBeInTheDocument();
});

test("overview output does not render secret-bearing field names", async () => {
  setToken();
  await authenticatedFetchMock(await jsonResponse(summary), await jsonResponse(activity));

  const { container } = render(<App />);
  await screen.findByText("Command the day with confidence.");

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
