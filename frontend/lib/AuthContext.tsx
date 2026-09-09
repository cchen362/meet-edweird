"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, useSyncExternalStore } from "react";
import { getAuthStatus, login as apiLogin, setupPassword as apiSetup, logout as apiLogout } from "./api";

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  needsSetup: boolean;
  login: (password: string) => Promise<void>;
  setup: (password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Check if auth hint exists (optimistic check to avoid spinner flash).
// Uses localStorage so the hint survives iOS PWA cold launches
// (sessionStorage is wiped each time the PWA is reopened).
// checkAuth() corrects the hint immediately if the cookie has expired.
function hasAuthHint(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem("edward_auth_hint") === "1";
  } catch {
    return false;
  }
}

const subscribeNoop = () => () => {};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Optimistic: if we have the hint, assume authenticated until proven otherwise.
  // useSyncExternalStore (not useState(hasAuthHint())) so the server render and the
  // client's first render both see the `false` snapshot — hasAuthHint() reads
  // localStorage, which doesn't exist on the server, so seeding useState directly
  // from it made server and client markup diverge and React flagged a hydration
  // mismatch. The real client value is applied by React right after hydration.
  const hint = useSyncExternalStore(subscribeNoop, hasAuthHint, () => false);
  const [verified, setVerified] = useState<boolean | null>(null); // null until /auth/status answers
  const [needsSetup, setNeedsSetup] = useState(false);

  const isAuthenticated = verified ?? hint;
  const isLoading = verified === null && !hint;

  const checkAuth = useCallback(async () => {
    try {
      const status = await getAuthStatus();
      setNeedsSetup(!status.configured);
      setVerified(status.authenticated);
      // Update hint
      try {
        if (status.authenticated) {
          localStorage.setItem("edward_auth_hint", "1");
        } else {
          localStorage.removeItem("edward_auth_hint");
        }
      } catch { /* localStorage unavailable */ }
    } catch {
      setVerified(false);
      try { localStorage.removeItem("edward_auth_hint"); } catch {}
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = async (password: string) => {
    await apiLogin(password);
    setVerified(true);
    setNeedsSetup(false);
    try { localStorage.setItem("edward_auth_hint", "1"); } catch {}
  };

  const setup = async (password: string) => {
    await apiSetup(password);
    setVerified(true);
    setNeedsSetup(false);
    try { localStorage.setItem("edward_auth_hint", "1"); } catch {}
  };

  const logout = async () => {
    await apiLogout();
    setVerified(false);
    try { localStorage.removeItem("edward_auth_hint"); } catch {}
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        needsSetup,
        login,
        setup,
        logout,
        checkAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
