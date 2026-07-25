import { Route, Routes } from "react-router-dom";

import { AppLayout } from "../layouts/AppLayout";
import { OverviewPage } from "../pages/OverviewPage";
import { PlaceholderPage } from "../pages/PlaceholderPage";
import { EmailInboxPage } from "../pages/EmailInboxPage";
import { EmailDetailPage } from "../pages/EmailDetailPage";
import { ApprovalsPage } from "../pages/ApprovalsPage";
import { AuditPage } from "../pages/AuditPage";

const placeholders = [
  ["/agent", "Agent Activity", "Observe local AI agent status and activity."],
  ["/providers", "Provider Connections", "Review connected business platforms."],
  ["/calls", "Call Operations", "Coordinate calling platforms in a future stage."],
  ["/settings", "Settings", "Configure dashboard preferences in a future stage."],
] as const;

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="/email" element={<EmailInboxPage />} />
        <Route path="/email/:emailId" element={<EmailDetailPage />} />
        <Route path="/approvals" element={<ApprovalsPage />} />
        <Route path="/audit" element={<AuditPage />} />
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
