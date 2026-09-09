"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect, useRef, useCallback } from "react";
import { MessageSquare, Settings, PanelLeft, LogOut, ChevronDown } from "lucide-react";
import { ThemeProvider, ThemeToggle } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { ChatSidebar, MobileChatDrawer } from "@/components/chat/ChatSidebar";
import { NotificationPrompt } from "@/components/NotificationPrompt";
import { ServiceWorkerRegistration } from "@/components/ServiceWorkerRegistration";
import { useChat } from "@/lib/ChatContext";
import { useAuth } from "@/lib/AuthContext";
import { EdwardAvatar } from "@/components/EdwardAvatar";
import {
  getSettings,
  getModels,
  updateSettings,
  Model,
} from "@/lib/api";

function ModelBadge() {
  const [modelId, setModelId] = useState<string | null>(null);
  const [models, setModels] = useState<Model[]>([]);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const loadData = useCallback(async () => {
    try {
      const [s, m] = await Promise.all([
        getSettings(),
        getModels(),
      ]);
      setModelId(s.model);
      setModels(m);
    } catch {
      // Silently fail — badge just won't show
    }
  }, []);

  useEffect(() => {
    loadData();
    // Re-fetch on window focus to detect OAuth fallback
    const onFocus = () => loadData();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [loadData]);

  // Close dropdown on outside click
  useEffect(() => {
    if (!dropdownOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [dropdownOpen]);

  const handleSelect = async (id: string) => {
    if (id === modelId || saving) return;
    setSaving(true);
    setDropdownOpen(false);
    try {
      await updateSettings({ model: id });
      setModelId(id);
    } catch (e) {
      console.error("Failed to switch model:", e);
    } finally {
      setSaving(false);
    }
  };

  if (!modelId || models.length === 0) return null;

  const currentModel = models.find((m) => m.id === modelId);
  const displayName = currentModel?.name ?? modelId;
  const title = `Model: ${displayName}${currentModel?.description ? ` — ${currentModel.description}` : ""}`;

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setDropdownOpen(!dropdownOpen)}
        disabled={saving}
        className={cn(
          "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition-colors",
          "hover:bg-surface border border-transparent hover:border-input-border",
          saving ? "opacity-50" : "text-text-muted"
        )}
        title={title}
      >
        <span className="font-medium text-text-primary">{displayName}</span>
        <ChevronDown className="w-3 h-3" />
      </button>

      {dropdownOpen && (
        <div className="absolute top-full right-0 mt-1 w-56 rounded-lg border border-input-border bg-primary-bg shadow-lg z-50 py-1">
          {models.map((m) => (
            <button
              key={m.id}
              onClick={() => handleSelect(m.id)}
              className={cn(
                "w-full text-left px-3 py-1.5 text-sm transition-colors",
                m.id === modelId
                  ? "text-terminal bg-terminal/10"
                  : "text-text-primary hover:bg-surface"
              )}
            >
              <div>{m.name}</div>
              {m.description && (
                <div className="text-[10px] text-text-muted">{m.description}</div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
  const { sidebarCollapsed, toggleSidebar } = useChat();
  const { logout, isAuthenticated } = useAuth();
  const isChatPage = pathname === "/chat";

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <>
      <header className="border-b border-border bg-primary-bg">
        <div className="container mx-auto px-4 h-14 flex items-center justify-between">
          {/* Left side: Mobile drawer toggle + Logo */}
          <div className="flex items-center gap-2">
            {/* Mobile drawer toggle (only on chat page) */}
            {isChatPage && (
              <button
                onClick={() => setMobileDrawerOpen(true)}
                className="md:hidden p-2 rounded-md hover:bg-surface transition-colors"
                aria-label="Open chat history"
              >
                <PanelLeft className="w-5 h-5 text-text-primary" />
              </button>
            )}

            {/* Logo */}
            <Link href="/chat" className="flex items-center gap-2">
              <EdwardAvatar size={36} animated />
              <span className="font-mono font-bold text-lg text-text-primary hidden sm:inline">
                Edward
              </span>
            </Link>
          </div>

          {/* Right side: Model badge + Navigation icons */}
          <div className="flex items-center gap-2">
            {isAuthenticated && <ModelBadge />}

            <nav className="flex items-center gap-1">
              {/* Chat button (hidden on chat page) */}
              {!isChatPage && (
                <Link
                  href="/chat"
                  className="p-2 rounded-md hover:bg-surface transition-colors text-text-primary"
                  title="Chat"
                >
                  <MessageSquare className="w-5 h-5" />
                </Link>
              )}
              {/* Settings button */}
              <Link
                href="/settings"
                className={cn(
                  "p-2 rounded-md transition-colors text-text-primary",
                  pathname === "/settings" ? "bg-surface" : "hover:bg-surface"
                )}
                title="Settings"
              >
                <Settings className="w-5 h-5" />
              </Link>
              {/* Theme toggle */}
              <ThemeToggle />
              {/* Logout button */}
              {isAuthenticated && (
                <button
                  onClick={handleLogout}
                  className="p-2 rounded-md hover:bg-surface transition-colors text-text-primary"
                  title="Sign out"
                >
                  <LogOut className="w-5 h-5" />
                </button>
              )}
            </nav>
          </div>
        </div>
      </header>

      {/* Mobile drawer (only on chat page) */}
      {isChatPage && (
        <MobileChatDrawer
          isOpen={mobileDrawerOpen}
          onClose={() => setMobileDrawerOpen(false)}
        />
      )}
    </>
  );
}

interface ClientLayoutProps {
  children: React.ReactNode;
}

export function ClientLayout({ children }: ClientLayoutProps) {
  const pathname = usePathname();
  const isChatPage = pathname === "/chat";

  return (
    <ThemeProvider>
      {/* Register service worker for PWA */}
      <ServiceWorkerRegistration />
      <div className="h-screen flex flex-col overflow-hidden bg-primary-bg">
        <Header />
        <div className="flex-1 flex overflow-hidden min-h-0">
          {/* Sidebar only on chat page */}
          {isChatPage && <ChatSidebar />}
          <main className="flex-1 flex flex-col overflow-hidden min-h-0">{children}</main>
        </div>
        {/* Push notification prompt */}
        <NotificationPrompt />
      </div>
    </ThemeProvider>
  );
}
