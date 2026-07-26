import { createContext, useContext } from "react";
import type { ReactNode } from "react";

import type { AvailableCompanyContext } from "../api/client";

const ActiveCompanyContext = createContext<AvailableCompanyContext | null>(null);

export function ActiveCompanyProvider({
  value,
  children,
}: {
  value: AvailableCompanyContext | null;
  children: ReactNode;
}) {
  return (
    <ActiveCompanyContext.Provider value={value}>
      {children}
    </ActiveCompanyContext.Provider>
  );
}

export function useActiveCompany() {
  return useContext(ActiveCompanyContext);
}
