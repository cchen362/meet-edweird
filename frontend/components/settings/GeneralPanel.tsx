"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { ExternalLink, LogOut, Loader2 } from "lucide-react";
import {
  getSettings,
  updateSettings,
  getModels,
  getOpenAIStatus,
  startCodexLogin,
  logoutCodex,
  Model,
  Settings,
  OpenAIStatus,
} from "@/lib/api";

interface GeneralPanelProps {
  isExpanded?: boolean;
  hideHeader?: boolean;
}

export function GeneralPanel({ isExpanded, hideHeader }: GeneralPanelProps) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [models, setModels] = useState<Model[]>([]);
  const [openaiStatus, setOpenaiStatus] = useState<OpenAIStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loginLoading, setLoginLoading] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [s, m, o] = await Promise.all([
        getSettings(),
        getModels(),
        getOpenAIStatus(),
      ]);
      setSettings(s);
      setModels(m);
      setOpenaiStatus(o);
    } catch (e) {
      console.error("Failed to load settings:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [loadData]);

  const handleModelChange = async (modelId: string) => {
    if (!settings) return;
    setSaving(true);
    try {
      const updated = await updateSettings({ model: modelId });
      setSettings(updated);
    } catch (e) {
      console.error("Failed to update model:", e);
    } finally {
      setSaving(false);
    }
  };

  const handleTemperatureChange = async (temp: number) => {
    if (!settings) return;
    setSaving(true);
    try {
      const updated = await updateSettings({ temperature: temp });
      setSettings(updated);
    } catch (e) {
      console.error("Failed to update temperature:", e);
    } finally {
      setSaving(false);
    }
  };

  const handleCodexLogin = async () => {
    setLoginLoading(true);
    try {
      const { auth_url } = await startCodexLogin();
      window.open(auth_url, "_blank");
      // Poll for completion every 2s
      pollRef.current = setInterval(async () => {
        try {
          const status = await getOpenAIStatus();
          if (status.codex_connected) {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setOpenaiStatus(status);
            setLoginLoading(false);
            // Refresh model list to show OpenAI models
            const m = await getModels();
            setModels(m);
          }
        } catch {
          // Ignore polling errors
        }
      }, 2000);
      // Timeout after 2 minutes
      setTimeout(() => {
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        setLoginLoading(false);
      }, 120000);
    } catch (e) {
      console.error("Failed to start OpenAI login:", e);
      setLoginLoading(false);
    }
  };

  const handleCodexLogout = async () => {
    try {
      await logoutCodex();
      setOpenaiStatus({
        codex_connected: false,
        codex_email: null,
      });
      // Refresh model list to hide OpenAI models
      const m = await getModels();
      setModels(m);
    } catch (e) {
      console.error("Failed to logout:", e);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-text-muted text-sm py-8">
        <Loader2 className="w-4 h-4 animate-spin" />
        Loading settings...
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="text-red-400 text-sm py-8">Failed to load settings</div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Model Selection */}
      <div>
        <label className="block text-sm font-medium text-text-primary mb-2">
          Model
        </label>
        <select
          value={settings.model}
          onChange={(e) => handleModelChange(e.target.value)}
          disabled={saving}
          className="w-full bg-surface border border-input-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-terminal/50 transition-colors disabled:opacity-50"
        >
          {models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
        {saving && (
          <p className="text-xs text-text-muted mt-1">Saving...</p>
        )}
      </div>

      {/* Temperature */}
      <div>
        <label className="block text-sm font-medium text-text-primary mb-2">
          Temperature: {settings.temperature.toFixed(1)}
        </label>
        <input
          type="range"
          min="0"
          max="1"
          step="0.1"
          value={settings.temperature}
          onChange={(e) => handleTemperatureChange(parseFloat(e.target.value))}
          className="w-full accent-terminal"
        />
        <div className="flex justify-between text-xs text-text-muted mt-1">
          <span>Precise</span>
          <span>Creative</span>
        </div>
      </div>

      {/* OpenAI Connection */}
      <div className="border-t border-input-border pt-4">
        <h3 className="text-sm font-medium text-text-primary mb-3">
          OpenAI Connection
        </h3>
        {openaiStatus?.codex_connected ? (
          <div className="flex items-center justify-between p-3 rounded-lg bg-green-400/10 border border-green-400/20">
            <div>
              <div className="text-sm text-text-primary">
                Connected via Codex OAuth
              </div>
              {openaiStatus.codex_email && (
                <div className="text-xs text-text-muted">
                  {openaiStatus.codex_email}
                </div>
              )}
            </div>
            <button
              onClick={handleCodexLogout}
              className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1 transition-colors"
            >
              <LogOut className="w-3 h-3" /> Disconnect
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-xs text-text-muted">
              Chat runs on your ChatGPT subscription via Codex. Sign in to
              use it — until then, chat is unavailable.
            </p>
            <button
              onClick={handleCodexLogin}
              disabled={loginLoading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface border border-input-border hover:border-terminal/50 text-sm text-text-primary transition-colors disabled:opacity-50"
            >
              {loginLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ExternalLink className="w-4 h-4" />
              )}
              Sign in with OpenAI
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
