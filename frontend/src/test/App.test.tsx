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

const firstRunReady = {
  initialized: true,
  setup_required: false,
  administrator_count: 1,
  company_count: 1,
  bootstrap_method: "local_cli",
};

const campaignSchedule = {
  campaign_key: "default",
  status: "draft",
  timezone: "Europe/Sofia",
  allowed_weekdays: [0, 1, 2, 3, 4],
  send_windows: [{ start: "09:00:00", end: "12:00:00" }],
  randomized_timing: {
    minimum_delay_minutes: 15,
    maximum_delay_minutes: 45,
    jitter_minutes: 10,
  },
  limits: {
    campaign_hourly: 20,
    campaign_daily: 100,
    mailbox_hourly: 10,
    mailbox_daily: 40,
    mailbox_max_consecutive: 3,
    company_daily: null,
  },
  mailbox_rotation: {
    strategy: "round_robin",
    allowed_connection_ids: [],
    preferred_connection_id: null,
    reply_monitoring_required: true,
    paused_connection_ids: [],
  },
  follow_up_steps: [],
  maximum_follow_ups: 3,
  start_date: null,
  end_date: null,
  approval_mode: "draft_only",
  auto_pause: {
    authentication_failures: 3,
    tls_or_connection_failures: 3,
    provider_quota_reached: true,
    hourly_or_daily_limit_reached: true,
    bounce_rate_percent: 8,
    unsubscribe_received: true,
    missing_mailbox: true,
    approval_unavailable: true,
    internal_error: true,
  },
  pause_reason: null,
  worker_enabled: false,
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
  return [
    await jsonResponse(firstRunReady),
    await jsonResponse(administrator),
    await jsonResponse(companyContexts),
  ];
}

async function authenticatedFetchMock(...responses: Response[]) {
  const fetchMock = vi.spyOn(globalThis, "fetch");
  for (const response of await bootstrapResponses()) fetchMock.mockResolvedValueOnce(response);
  for (const response of responses) fetchMock.mockResolvedValueOnce(response);
  return fetchMock;
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  vi.restoreAllMocks();
  window.history.pushState({}, "", "/");
});

test("login flow stores the token without rendering it and selects an authorized company", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(await jsonResponse(firstRunReady))
    .mockResolvedValueOnce(await jsonResponse({ access_token: "opaque-login-session-value" }))
    .mockResolvedValueOnce(await jsonResponse(firstRunReady))
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

test("renders setup-required state before any default administrator exists", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(await jsonResponse({
    initialized: false,
    setup_required: true,
    administrator_count: 0,
    company_count: 0,
    bootstrap_method: "local_cli",
  }));

  render(<App />);

  expect(await screen.findByRole("heading", { name: "CompanyAI is not initialized yet" })).toBeInTheDocument();
  expect(screen.getByText(/Create the first company and administrator/)).toBeInTheDocument();
  expect(document.body.textContent).not.toContain("password_hash");
});

test("first-run wizard initializes without rendering secrets", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(await jsonResponse({
      initialized: false,
      setup_required: true,
      administrator_count: 0,
      company_count: 0,
      bootstrap_method: "local_wizard",
    }))
    .mockResolvedValueOnce(await jsonResponse({
      initialized: true,
      company_id: "company-id",
      company_slug: "hvac-company",
      administrator_id: "admin-id",
      administrator_email: "owner@example.test",
    }));

  render(<App />);

  expect(await screen.findByRole("heading", { name: "CompanyAI is not initialized yet" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Company name"), { target: { value: "HVAC Company" } });
  fireEvent.change(screen.getByLabelText("Company slug"), { target: { value: "hvac-company" } });
  fireEvent.change(screen.getByLabelText("Administrator name"), { target: { value: "Owner User" } });
  fireEvent.change(screen.getByLabelText("Administrator email"), { target: { value: "OWNER@example.test" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "Str0ng-local-setup!" } });
  fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "Str0ng-local-setup!" } });
  fireEvent.click(screen.getByRole("button", { name: "Initialize CompanyAI" }));

  expect(await screen.findByText("Setup completed for hvac-company. Sign in with the administrator account.")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "CompanyAI dashboard" })).toBeInTheDocument();
  expect(document.body.textContent).not.toContain("Str0ng-local-setup!");
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
    .mockResolvedValueOnce(await jsonResponse(firstRunReady))
    .mockResolvedValueOnce(await jsonResponse(administrator))
    .mockResolvedValueOnce(await jsonResponse({ items: [], total: 0, limit: 100, offset: 0 }));

  render(<App />);

  expect(await screen.findByRole("heading", { name: "No companies available" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Provider Connections" })).toBeInTheDocument();
});

test("expired session clears protected context", async () => {
  setToken();
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(await jsonResponse(firstRunReady))
    .mockResolvedValueOnce(await jsonResponse({}, false, 401));

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

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(7));
  expect(await screen.findByText("Command the day with confidence.")).toBeInTheDocument();
});

test.each([
  ["/calls", "Call Operations"],
])("renders the %s protected placeholder route", async (path, title) => {
  setToken();
  window.history.pushState({}, "", path);
  await authenticatedFetchMock();
  render(<App />);

  expect(await screen.findByRole("heading", { name: title })).toBeInTheDocument();
  expect(screen.getByText("Not configured yet")).toBeInTheDocument();
});

test("renders Settings sections and persists safe local preferences", async () => {
  setToken();
  await authenticatedFetchMock();
  window.history.pushState({}, "", "/settings");
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Tune the dashboard to the way you work." })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Profile" })).toBeInTheDocument();
  expect(screen.getByDisplayValue("admin@example.test")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Preferences" }));
  fireEvent.change(screen.getAllByDisplayValue("English")[0], { target: { value: "bg" } });
  expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));

  expect(await screen.findByText("Saved")).toBeInTheDocument();
  expect(localStorage.getItem("companyai.settings.preferences")).toContain("\"interfaceLanguage\":\"bg\"");
  expect(document.body.textContent?.toLowerCase()).not.toContain("opaque-test-session-value");

  fireEvent.click(screen.getByRole("button", { name: "Security" }));
  expect(screen.getByText("Password changes and MFA need a verified secure backend flow before they can be offered. CompanyAI will not collect replacement passwords in this dashboard until that flow exists.")).toBeInTheDocument();
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
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(7));
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

const genericProviderDescriptor = {
  key: "generic_smtp_imap",
  display_name: "Generic SMTP/IMAP",
  category: "email",
  authentication_type: "username_password",
  required_secret_fields: ["password"],
  optional_secret_fields: [],
  configuration_fields: [
    "email_address",
    "sender_display_name",
    "username",
    "smtp_host",
    "smtp_port",
    "smtp_security",
    "imap_host",
    "imap_port",
    "imap_security",
    "imap_folder",
    "reply_to_address",
  ],
  capabilities: ["email.send", "email.read", "email.reply"],
  credentials_may_expire: false,
};

function genericConnection(overrides: Record<string, unknown> = {}) {
  return {
    id: "generic-connection",
    company_id: "company-id",
    provider_key: "generic_smtp_imap",
    display_name: "Primary mailbox",
    slug: "primary-mailbox",
    authentication_type: "username_password",
    status: "inactive",
    configuration: {
      email_address: "mailbox@example.test",
      username: "mailbox@example.test",
      smtp_host: "mail.example.test",
      smtp_port: 465,
      smtp_security: "ssl_tls",
      imap_host: "mail.example.test",
      imap_port: 993,
      imap_security: "ssl_tls",
      imap_folder: "INBOX",
    },
    metadata: {},
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    activated_at: null,
    deactivated_at: null,
    revoked_at: null,
    ...overrides,
  };
}

test("renders the Generic SMTP/IMAP provider and opens and closes the mailbox form", async () => {
  setToken();
  await authenticatedFetchMock(
    await jsonResponse([genericProviderDescriptor]),
    await jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }),
  );
  window.history.pushState({}, "", "/providers");
  render(<App />);

  expect(await screen.findByText("Generic SMTP/IMAP")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Add email mailbox" }));
  expect(screen.getByRole("heading", { name: "Add mailbox" })).toBeInTheDocument();
  expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("heading", { name: "Add mailbox" })).not.toBeInTheDocument();
});

test("validates mailbox form ports before saving", async () => {
  setToken();
  const fetchMock = await authenticatedFetchMock(
    await jsonResponse([genericProviderDescriptor]),
    await jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }),
  );
  window.history.pushState({}, "", "/providers");
  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: "Add email mailbox" }));
  fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "mailbox@example.test" } });
  fireEvent.change(screen.getByLabelText("Username"), { target: { value: "mailbox@example.test" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "not-rendered-mailbox-password" } });
  fireEvent.change(screen.getByLabelText("SMTP host"), { target: { value: "mail.example.test" } });
  fireEvent.change(screen.getByLabelText("SMTP port"), { target: { value: "70000" } });
  fireEvent.change(screen.getByLabelText("IMAP host"), { target: { value: "mail.example.test" } });
  fireEvent.click(screen.getByRole("button", { name: "Save mailbox" }));

  expect(await screen.findByText("SMTP port must be a valid TCP port.")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(5);
  expect(document.body.textContent).not.toContain("not-rendered-mailbox-password");
});

test("handles partial mailbox save when credential creation fails", async () => {
  setToken();
  const connection = genericConnection();
  await authenticatedFetchMock(
    await jsonResponse([genericProviderDescriptor]),
    await jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }),
    await jsonResponse(connection, true, 201),
    await jsonResponse({}, false, 409),
  );
  window.history.pushState({}, "", "/providers");
  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: "Add email mailbox" }));
  fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "mailbox@example.test" } });
  fireEvent.change(screen.getByLabelText("Username"), { target: { value: "mailbox@example.test" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "not-rendered-mailbox-password" } });
  fireEvent.change(screen.getByLabelText("SMTP host"), { target: { value: "mail.example.test" } });
  fireEvent.change(screen.getByLabelText("IMAP host"), { target: { value: "mail.example.test" } });
  fireEvent.click(screen.getByRole("button", { name: "Save mailbox" }));

  expect(await screen.findByText(/Connection saved, but password storage failed/)).toBeInTheDocument();
  expect(screen.getByText("Primary mailbox")).toBeInTheDocument();
  expect(document.body.textContent).not.toContain("not-rendered-mailbox-password");
});

test("failed mailbox tests prevent activation and successful tests enable it", async () => {
  setToken();
  const baseConnection = genericConnection();
  const smtpOk = genericConnection({
    metadata: {
      generic_smtp_imap_health: {
        smtp: { status: "succeeded", tested_at: "2026-01-01T00:00:00Z", category: "success", message: "Connection test succeeded." },
        activation_ready: false,
      },
    },
  });
  const imapFailed = genericConnection({
    metadata: {
      generic_smtp_imap_health: {
        smtp: { status: "succeeded", tested_at: "2026-01-01T00:00:00Z", category: "success", message: "Connection test succeeded." },
        imap: { status: "failed", tested_at: "2026-01-01T00:01:00Z", category: "authentication_failure", message: "Mailbox authentication failed." },
        activation_ready: false,
      },
    },
  });
  const imapOk = genericConnection({
    metadata: {
      generic_smtp_imap_health: {
        smtp: { status: "succeeded", tested_at: "2026-01-01T00:00:00Z", category: "success", message: "Connection test succeeded." },
        imap: { status: "succeeded", tested_at: "2026-01-01T00:02:00Z", category: "success", message: "Connection test succeeded." },
        activation_ready: true,
      },
    },
  });
  const active = genericConnection({ ...imapOk, status: "active", activated_at: "2026-01-01T00:03:00Z" });
  await authenticatedFetchMock(
    await jsonResponse([genericProviderDescriptor]),
    await jsonResponse({ items: [baseConnection], total: 1, limit: 50, offset: 0 }),
    await jsonResponse({ protocol: "smtp", status: "succeeded", tested_at: "2026-01-01T00:00:00Z", category: "success", message: "Connection test succeeded.", connection: smtpOk }),
    await jsonResponse({ protocol: "imap", status: "failed", tested_at: "2026-01-01T00:01:00Z", category: "authentication_failure", message: "Mailbox authentication failed.", connection: imapFailed }),
    await jsonResponse({ protocol: "imap", status: "succeeded", tested_at: "2026-01-01T00:02:00Z", category: "success", message: "Connection test succeeded.", connection: imapOk }),
    await jsonResponse(active),
  );
  window.history.pushState({}, "", "/providers");
  render(<App />);

  expect(await screen.findByText("Primary mailbox")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Activate" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Test SMTP" }));
  expect(await screen.findByText("Connection test succeeded.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Activate" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Test IMAP" }));
  expect(await screen.findByText("Mailbox authentication failed.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Activate" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Test IMAP" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Activate" })).not.toBeDisabled());
  fireEvent.click(screen.getByRole("button", { name: "Activate" }));
  expect(await screen.findByText("Mailbox activated.")).toBeInTheDocument();
  expect(document.body.textContent).not.toContain("not-rendered-mailbox-password");
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
    await jsonResponse(campaignSchedule),
    await jsonResponse({ items: [{
      id: "mailbox-1",
      company_id: "company-id",
      provider_key: "generic_smtp_imap",
      display_name: "Primary mailbox",
      slug: "primary-mailbox",
      authentication_type: "username_password",
      status: "active",
      configuration: {},
      metadata: {},
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      activated_at: "2026-01-01T00:00:00Z",
      deactivated_at: null,
      revoked_at: null,
    }], total: 1, limit: 50, offset: 0 }),
  );
  window.history.pushState({}, "", "/email");
  render(<App />);
  expect(await screen.findByRole("heading", { name: "No imported email" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Email Sandbox Guide" })).toHaveAttribute("href", "/documentation/email-sandbox");
  expect(screen.getByRole("heading", { name: "Email Sandbox" })).toBeInTheDocument();
  expect(screen.getByText("Backend enforced")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Email Automation" })).toBeInTheDocument();
  expect(screen.getByDisplayValue("Europe/Sofia")).toBeInTheDocument();
  expect(screen.getByText("Welcome sequence")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
});

test("previews email automation dry-run slots", async () => {
  setToken();
  await authenticatedFetchMock(
    await jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }),
    await jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }),
    await jsonResponse(campaignSchedule),
    await jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }),
    await jsonResponse({
      settings: campaignSchedule,
      slots: [{
        sequence: 1,
        planned_at_utc: "2026-08-03T06:00:00Z",
        planned_at_local: "2026-08-03T09:00:00+03:00",
        timezone: "Europe/Sofia",
        mailbox_connection_id: "mailbox-1",
        mailbox_display_name: "Primary mailbox",
        campaign_key: "default",
        recipient_step: "initial",
        status: "planned",
        reason: null,
        applicable_limits: { campaign_daily: 100 },
      }],
      skipped: [],
      worker_enabled: false,
      worker_contract: { preview_only: true },
    }),
  );
  window.history.pushState({}, "", "/email");
  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: "Preview dry run" }));

  expect(await screen.findByText("Dry-run preview refreshed.")).toBeInTheDocument();
  expect(screen.getByText("Primary mailbox")).toBeInTheDocument();
  expect(screen.getByText("initial")).toBeInTheDocument();
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
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
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
