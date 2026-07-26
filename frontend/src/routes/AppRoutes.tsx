import { Route, Routes } from "react-router-dom";

import { AppLayout } from "../layouts/AppLayout";
import { OverviewPage } from "../pages/OverviewPage";
import { PlaceholderPage } from "../pages/PlaceholderPage";
import { EmailInboxPage } from "../pages/EmailInboxPage";
import { EmailDetailPage } from "../pages/EmailDetailPage";
import { ApprovalsPage } from "../pages/ApprovalsPage";
import { AuditPage } from "../pages/AuditPage";
import { AgentRuntimePage } from "../pages/AgentRuntimePage";
import { ProviderConnectionsPage } from "../pages/ProviderConnectionsPage";
import { ActivityCenterPage } from "../pages/ActivityCenterPage";
import { SystemStatusPage } from "../pages/SystemStatusPage";

const placeholders = [
  ["/calls", "Call Operations", "Coordinate calling platforms in a future stage."],
  ["/settings", "Settings", "Configure dashboard preferences in a future stage."],
] as const;

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="/agent" element={<AgentRuntimePage />} />
        <Route path="/email" element={<EmailInboxPage />} />
        <Route path="/email/:emailId" element={<EmailDetailPage />} />
        <Route path="/approvals" element={<ApprovalsPage />} />
        <Route path="/activity" element={<ActivityCenterPage />} />
        <Route path="/system-status" element={<SystemStatusPage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/providers" element={<ProviderConnectionsPage />} />
        {placeholders.map(([path, title, description]) => (
          <Route
            key={path}
            path={path}
            element={<PlaceholderPage title={title} description={description} />}
          />
        ))}
      </Route>
    </Routes>
  );
}
