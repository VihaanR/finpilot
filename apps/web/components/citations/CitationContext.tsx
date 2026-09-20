"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { TransactionDrawer } from "./TransactionDrawer";

export interface DrawerRequest {
  title: string;
  txnIds: string[];
  subtitle?: string;
}

const CitationContext = createContext<{ open: (req: DrawerRequest) => void } | null>(null);

/**
 * One drawer for the whole app.
 *
 * Every figure in FinPilot is meant to be clickable down to the rows behind
 * it, so the drawer is mounted once and addressed by context rather than
 * re-implemented per page. That also keeps exactly one focus trap alive at a
 * time, which is the part that is easy to get wrong.
 */
export function CitationProvider({ children }: { children: React.ReactNode }) {
  const [request, setRequest] = useState<DrawerRequest | null>(null);

  const open = useCallback((req: DrawerRequest) => setRequest(req), []);
  const value = useMemo(() => ({ open }), [open]);

  return (
    <CitationContext.Provider value={value}>
      {children}
      <TransactionDrawer request={request} onClose={() => setRequest(null)} />
    </CitationContext.Provider>
  );
}

export function useCitations() {
  const ctx = useContext(CitationContext);
  if (!ctx) throw new Error("useCitations must be used inside CitationProvider");
  return ctx;
}
