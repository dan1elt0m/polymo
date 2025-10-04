import React from "react";
import type { ConfigFormState } from "../../../types";
import { InfoTooltip } from "../../InfoTooltip";

export interface AuthenticationSectionProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
  setBearerToken: (value: string) => void;
}

const AUTH_TOGGLE_ID = "auth-section";

export const AuthenticationSection: React.FC<AuthenticationSectionProps> = ({
  state,
  onUpdateState,
  setBearerToken,
}) => {
  const [isOpen, setIsOpen] = React.useState(false);

  React.useEffect(() => {
    if (state.authType === "bearer" || state.authType === "api_key") {
      setIsOpen(true);
    }
  }, [state.authType]);

  const handleAuthTypeChange = React.useCallback(
    (nextType: ConfigFormState["authType"]) => {
      const patch: Partial<ConfigFormState> = { authType: nextType };

      if (nextType === "none") {
        patch.authToken = "";
        patch.authApiKeyParamName = state.authApiKeyParamName;
        setBearerToken("");
      }

      if (nextType === "bearer") {
        patch.authApiKeyParamName = state.authApiKeyParamName;
      }

      if (nextType === "api_key") {
        patch.authToken = "";
        if (!state.authApiKeyParamName) {
          patch.authApiKeyParamName = "api_key";
        }
        setBearerToken("");
      }

      onUpdateState(patch);
    },
    [onUpdateState, setBearerToken, state.authApiKeyParamName, state.authToken],
  );

  const handleBearerTokenChange = React.useCallback(
    (value: string) => {
      onUpdateState({ authToken: value });
      setBearerToken(value);
    },
    [onUpdateState, setBearerToken],
  );

  return (
    <div className="space-y-3">
      <button
        type="button"
        className="flex w-full items-center justify-between rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-slate-12 hover:border-blue-7 hover:bg-blue-3/20 dark:hover:bg-drac-selection/40 transition-colors duration-200"
        onClick={() => setIsOpen((value) => !value)}
        aria-expanded={isOpen}
        aria-controls={AUTH_TOGGLE_ID}
      >
        <span className="flex items-center gap-2">
          Authentication
          <span className="text-xs font-normal text-muted">
            (optional{state.authType !== "none" ? `: ${state.authType}` : ""})
          </span>
        </span>
        <span className={`transition-transform duration-200 ${isOpen ? "rotate-90" : ""}`}>
          <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
            <path d="M7.25 3.75a.75.75 0 0 1 1.06 0l5 5a.75.75 0 0 1 0 1.06l-5 5a.75.75 0 1 1-1.06-1.06L11.69 10 7.25 5.56a.75.75 0 0 1 0-1.06Z" />
          </svg>
        </span>
      </button>

      {isOpen && (
        <div
          id={AUTH_TOGGLE_ID}
          className="space-y-5 rounded-xl border border-border/60 dark:border-drac-border/60 bg-surface/70 dark:bg-[#1f232b]/80 backdrop-blur-sm p-5 shadow-inner transition ring-1 ring-border/40 dark:ring-drac-border/30 animate-in fade-in duration-200"
        >
          <div className="grid gap-5 md:grid-cols-2">
            <label className="flex flex-col gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Auth Type</span>
                <InfoTooltip text="Authentication method applied to each request. Not stored in YAML." />
              </div>
              <div className="relative">
                <select
                  className="w-full rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm appearance-none pr-9 transition-all focus:border-blue-7 dark:focus:border-drac-accent focus:outline-none"
                  value={state.authType}
                  onChange={(event) => handleAuthTypeChange(event.target.value as ConfigFormState["authType"])}
                >
                  <option value="none">None</option>
                  <option value="bearer">Bearer Token</option>
                  <option value="api_key">API Key</option>
                </select>
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-10 dark:text-drac-muted">
                  <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                    <path d="M5.8 7.5a.75.75 0 0 1 1.05-.2L10 9.2l3.15-1.9a.75.75 0 0 1 .75 1.3l-3.5 2.11a.75.75 0 0 1-.76 0L5.99 8.6a.75.75 0 0 1-.2-1.1Z" />
                  </svg>
                </span>
              </div>
            </label>

            {state.authType === "bearer" && (
              <label className="flex flex-col gap-2">
                <div className="flex items-center gap-1">
                  <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Bearer Token</span>
                  <InfoTooltip text="Secret token sent as Authorization header." />
                </div>
                <input
                  type="password"
                  className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                  placeholder="your-token-here"
                  value={state.authToken}
                  onChange={(event) => handleBearerTokenChange(event.target.value)}
                />
              </label>
            )}

            {state.authType === "api_key" && (
              <div className="grid gap-5 md:grid-cols-2">
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">API Key Param</span>
                    <InfoTooltip text="Query parameter name that will hold the API key at runtime." />
                  </div>
                  <input
                    type="text"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="api_key"
                    value={state.authApiKeyParamName || ""}
                    onChange={(event) => onUpdateState({ authApiKeyParamName: event.target.value.trim() })}
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">API Key (secret)</span>
                    <InfoTooltip text="Secret API key stored only in the browser session and supplied at runtime via Spark options." />
                  </div>
                  <input
                    type="password"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="your-api-key"
                    value={state.authToken}
                    onChange={(event) => handleBearerTokenChange(event.target.value)}
                  />
                </label>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
