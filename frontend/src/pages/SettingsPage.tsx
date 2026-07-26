import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link, useOutletContext } from "react-router-dom";

import {
  clearSessionContext,
  selectedCompanyId,
  type Administrator,
} from "../api/client";
import { useActiveCompany } from "../context/ActiveCompanyContext";

const preferenceKey = "companyai.settings.preferences";

type ThemeMode = "light" | "dark" | "system";
type Density = "comfortable" | "compact";

interface SettingsPreferences {
  interfaceLanguage: string;
  documentationLanguage: string;
  landingPage: string;
  timezone: string;
  dateFormat: string;
  density: Density;
  appearance: ThemeMode;
  notifyApprovals: boolean;
  notifyProviderHealth: boolean;
  notifyCampaigns: boolean;
  notifyAgent: boolean;
  defaultCompanyId: string;
  dashboardPreference: string;
}

const defaultPreferences: SettingsPreferences = {
  interfaceLanguage: "en",
  documentationLanguage: "en",
  landingPage: "/",
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  dateFormat: "medium",
  density: "comfortable",
  appearance: "system",
  notifyApprovals: true,
  notifyProviderHealth: true,
  notifyCampaigns: false,
  notifyAgent: true,
  defaultCompanyId: "",
  dashboardPreference: "operations",
};

function readPreferences(activeCompanyId: string): SettingsPreferences {
  try {
    const parsed = JSON.parse(localStorage.getItem(preferenceKey) ?? "{}") as Partial<SettingsPreferences>;
    return { ...defaultPreferences, ...parsed, defaultCompanyId: parsed.defaultCompanyId ?? activeCompanyId };
  } catch {
    return { ...defaultPreferences, defaultCompanyId: activeCompanyId };
  }
}

function settingId(name: string) {
  return `setting-${name}`;
}

function Field({
  label,
  children,
  note,
}: {
  label: string;
  children: ReactNode;
  note?: string;
}) {
  return (
    <label className="settings-field">
      <span>{label}</span>
      {children}
      {note && <small>{note}</small>}
    </label>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="settings-toggle">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

export function SettingsPage() {
  const { administrator } = useOutletContext<{ administrator: Administrator }>();
  const activeCompany = useActiveCompany();
  const activeCompanyId = selectedCompanyId() ?? activeCompany?.company.id ?? "";
  const [selectedSection, setSelectedSection] = useState("profile");
  const [saved, setSaved] = useState(() => readPreferences(activeCompanyId));
  const [draft, setDraft] = useState(saved);
  const [saveState, setSaveState] = useState<"idle" | "saved">("idle");

  useEffect(() => {
    const next = readPreferences(activeCompanyId);
    setSaved(next);
    setDraft(next);
  }, [activeCompanyId]);

  const dirty = useMemo(() => JSON.stringify(saved) !== JSON.stringify(draft), [draft, saved]);

  function update<K extends keyof SettingsPreferences>(key: K, value: SettingsPreferences[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
    setSaveState("idle");
  }

  function savePreferences() {
    localStorage.setItem(preferenceKey, JSON.stringify(draft));
    sessionStorage.setItem("companyai.docsLanguage", draft.documentationLanguage);
    setSaved(draft);
    setSaveState("saved");
    window.setTimeout(() => setSaveState("idle"), 1600);
  }

  function logout() {
    clearSessionContext();
    window.location.assign("/");
  }

  const sections = [
    ["profile", "Profile"],
    ["preferences", "Preferences"],
    ["appearance", "Appearance"],
    ["notifications", "Notifications"],
    ["security", "Security"],
    ["company", "Company defaults"],
    ["documentation", "Documentation"],
  ] as const;

  return (
    <section className="page settings-page" aria-labelledby="settings-title">
      <div className="overview-hero settings-hero">
        <div>
          <span className="eyebrow">Settings</span>
          <h1 id="settings-title">Tune the dashboard to the way you work.</h1>
          <p>Safe local preferences for this browser session and read-only account context.</p>
        </div>
        <div className="settings-save">
          <span className={dirty ? "status-badge status-badge--warning" : "status-badge status-badge--positive"}>
            {dirty ? "Unsaved changes" : saveState === "saved" ? "Saved" : "Up to date"}
          </span>
          <button className="button" type="button" onClick={savePreferences} disabled={!dirty}>
            Save preferences
          </button>
        </div>
      </div>

      <div className="settings-layout">
        <nav className="settings-nav" aria-label="Settings sections">
          {sections.map(([key, label]) => (
            <button className={selectedSection === key ? "is-active" : ""} key={key} type="button" onClick={() => setSelectedSection(key)}>
              {label}
            </button>
          ))}
        </nav>

        <div className="settings-panel">
          {selectedSection === "profile" && (
            <section aria-labelledby={settingId("profile")}>
              <h2 id={settingId("profile")}>Profile</h2>
              <div className="settings-grid">
                <Field label="Display name"><input value={administrator.full_name} readOnly /></Field>
                <Field label="Email" note="Email changes require a future secure verification flow."><input value={administrator.email} readOnly /></Field>
                <Field label="Role"><input value={activeCompany?.membership_role ?? (administrator.is_superuser ? "platform superuser" : "administrator")} readOnly /></Field>
                <Field label="Active company"><input value={activeCompany?.company.name ?? "No active company"} readOnly /></Field>
              </div>
            </section>
          )}

          {selectedSection === "preferences" && (
            <section aria-labelledby={settingId("preferences")}>
              <h2 id={settingId("preferences")}>Preferences</h2>
              <div className="settings-grid">
                <Field label="Interface language"><select value={draft.interfaceLanguage} onChange={(event) => update("interfaceLanguage", event.target.value)}><option value="en">English</option><option value="bg">Bulgarian</option><option value="de">German</option><option value="fr">French</option></select></Field>
                <Field label="Documentation language"><select value={draft.documentationLanguage} onChange={(event) => update("documentationLanguage", event.target.value)}><option value="en">English</option><option value="bg">Bulgarian</option><option value="de">German</option><option value="fr">French</option></select></Field>
                <Field label="Default landing page"><select value={draft.landingPage} onChange={(event) => update("landingPage", event.target.value)}><option value="/">Overview</option><option value="/activity">Activity</option><option value="/system-status">System Status</option><option value="/documentation">Documentation</option></select></Field>
                <Field label="Timezone"><input value={draft.timezone} onChange={(event) => update("timezone", event.target.value)} /></Field>
                <Field label="Date format"><select value={draft.dateFormat} onChange={(event) => update("dateFormat", event.target.value)}><option value="medium">Medium</option><option value="short">Short</option><option value="iso">ISO</option></select></Field>
                <Field label="Density"><select value={draft.density} onChange={(event) => update("density", event.target.value as Density)}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></Field>
              </div>
            </section>
          )}

          {selectedSection === "appearance" && (
            <section aria-labelledby={settingId("appearance")}>
              <h2 id={settingId("appearance")}>Appearance</h2>
              <div className="segmented-control" role="group" aria-label="Appearance mode">
                {(["light", "dark", "system"] as const).map((value) => (
                  <button className={draft.appearance === value ? "is-active" : ""} type="button" onClick={() => update("appearance", value)} key={value}>{value}</button>
                ))}
              </div>
              <p className="settings-note">The selected mode is stored locally. System mode follows the browser preference.</p>
            </section>
          )}

          {selectedSection === "notifications" && (
            <section aria-labelledby={settingId("notifications")}>
              <h2 id={settingId("notifications")}>Notifications</h2>
              <div className="settings-stack">
                <Toggle label="Approval notifications" checked={draft.notifyApprovals} onChange={(value) => update("notifyApprovals", value)} />
                <Toggle label="Provider health notifications" checked={draft.notifyProviderHealth} onChange={(value) => update("notifyProviderHealth", value)} />
                <Toggle label="Campaign notifications" checked={draft.notifyCampaigns} onChange={(value) => update("notifyCampaigns", value)} />
                <Toggle label="Agent notifications" checked={draft.notifyAgent} onChange={(value) => update("notifyAgent", value)} />
              </div>
              <p className="settings-note">These preferences are local-only until backend preference storage is introduced.</p>
            </section>
          )}

          {selectedSection === "security" && (
            <section aria-labelledby={settingId("security")}>
              <h2 id={settingId("security")}>Security</h2>
              <div className="settings-grid">
                <Field label="Session"><input value="Current browser session active" readOnly /></Field>
                <Field label="Last login"><input value={administrator.last_login_at ? new Date(administrator.last_login_at).toLocaleString() : "Not recorded"} readOnly /></Field>
              </div>
              <div className="settings-callout">
                Password changes and MFA need a verified secure backend flow before they can be offered. CompanyAI will not collect replacement passwords in this dashboard until that flow exists.
              </div>
              <button className="button button--light" type="button" onClick={logout}>Logout from current session</button>
            </section>
          )}

          {selectedSection === "company" && (
            <section aria-labelledby={settingId("company")}>
              <h2 id={settingId("company")}>Company defaults</h2>
              <div className="settings-grid">
                <Field label="Default active company"><input value={activeCompany?.company.name ?? "No active company"} readOnly /></Field>
                <Field label="Company status"><input value={activeCompany?.company.status ?? "Unavailable"} readOnly /></Field>
                <Field label="Company dashboard preference"><select value={draft.dashboardPreference} onChange={(event) => update("dashboardPreference", event.target.value)}><option value="operations">Operations control center</option><option value="activity">Activity-first review</option><option value="status">Status-first review</option></select></Field>
                <Field label="Company slug"><input value={activeCompany?.company.slug ?? "Unavailable"} readOnly /></Field>
              </div>
            </section>
          )}

          {selectedSection === "documentation" && (
            <section aria-labelledby={settingId("documentation")}>
              <h2 id={settingId("documentation")}>Documentation</h2>
              <div className="settings-grid">
                <Field label="Preferred documentation language"><select value={draft.documentationLanguage} onChange={(event) => update("documentationLanguage", event.target.value)}><option value="en">English</option><option value="bg">Bulgarian</option><option value="de">German</option><option value="fr">French</option></select></Field>
                <div className="settings-card-link"><strong>Documentation Center</strong><p>Open searchable product guidance for all implemented modules.</p><Link className="button button--light" to="/documentation/settings">Open Documentation Center</Link></div>
              </div>
            </section>
          )}
        </div>
      </div>
    </section>
  );
}
