import { Route, Routes } from "react-router-dom";

import { AppLayout } from "../layouts/AppLayout";
import { OverviewPage } from "../pages/OverviewPage";
import { PlaceholderPage } from "../pages/PlaceholderPage";

const placeholders = [
  ["/agent", "Agent Activity", "Observe local AI agent status and activity."],
  ["/providers", "Provider Connections", "Review connected business platforms."],
  ["/email", "Email Operations", "Manage outreach workflows in a future stage."],
  ["/calls", "Call Operations", "Coordinate calling platforms in a future stage."],
  ["/approvals", "Approvals", "Review controlled action requests in a future stage."],
  ["/audit", "Audit Log", "Explore complete company activity in a future stage."],
  ["/settings", "Settings", "Configure dashboard preferences in a future stage."],
] as const;

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<OverviewPage />} />
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
