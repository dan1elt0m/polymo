import React from "react";
import { useAtomValue } from "jotai";
import type { ConfigFormState } from "../../../types";
import { InfoTooltip } from "../../InfoTooltip";
import { databricksProfileAtom } from "../../../atoms";
import { ApiError, listDatabricksSecretKeys, listDatabricksSecretScopes } from "../../../lib/api";

export interface AuthenticationSectionProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
  setBearerToken: (value: string) => void;
}

const AUTH_TOGGLE_ID = "auth-section";

function describeSecretPickerError(error: unknown): string {
  if (error instanceof ApiError && error.status === 501) {
    return error.message;
  }
  return error instanceof Error ? error.message : String(error ?? "Failed to load");
}

const SELECT_CLASS =
  "w-full rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm appearance-none pr-9 transition-all focus:border-blue-7 dark:focus:border-drac-accent focus:outline-none disabled:opacity-60 disabled:cursor-not-allowed";

export const AuthenticationSection: React.FC<AuthenticationSectionProps> = ({
  state,
  onUpdateState,
  setBearerToken,
}) => {
  const [isOpen, setIsOpen] = React.useState(false);

  React.useEffect(() => {
    if (state.authType === "bearer" || state.authType === "api_key" || state.authType === "oauth2") {
      setIsOpen(true);
    }
  }, [state.authType]);

  const profile = useAtomValue(databricksProfileAtom);
  const [scopes, setScopes] = React.useState<string[]>([]);
  const [scopesLoading, setScopesLoading] = React.useState(false);
  const [scopesError, setScopesError] = React.useState<string | null>(null);
  const [keys, setKeys] = React.useState<string[]>([]);
  const [keysLoading, setKeysLoading] = React.useState(false);
  const [keysError, setKeysError] = React.useState<string | null>(null);

  const secretScopeActive = state.authSecretMode === "secret_scope";

  React.useEffect(() => {
    if (!secretScopeActive || !profile) {
      setScopes([]);
      setScopesError(null);
      return;
    }
    let cancelled = false;
    setScopesLoading(true);
    setScopesError(null);
    listDatabricksSecretScopes(profile)
      .then((res) => {
        if (!cancelled) setScopes(res.secret_scopes);
      })
      .catch((err) => {
        if (!cancelled) setScopesError(describeSecretPickerError(err));
      })
      .finally(() => {
        if (!cancelled) setScopesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [secretScopeActive, profile]);

  React.useEffect(() => {
    if (!secretScopeActive || !profile || !state.authSecretScope) {
      setKeys([]);
      setKeysError(null);
      return;
    }
    let cancelled = false;
    setKeysLoading(true);
    setKeysError(null);
    listDatabricksSecretKeys(state.authSecretScope, profile)
      .then((res) => {
        if (!cancelled) setKeys(res.secret_keys);
      })
      .catch((err) => {
        if (!cancelled) setKeysError(describeSecretPickerError(err));
      })
      .finally(() => {
        if (!cancelled) setKeysLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [secretScopeActive, profile, state.authSecretScope]);

  const renderSecretSourcePicker = React.useCallback(
    () => (
      <div className="flex flex-col gap-3 md:col-span-2">
        <div className="flex items-center gap-1">
          <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Secret source</span>
          <InfoTooltip text="Preview value: enter a value used only for previewing in this browser session; the exported script gets a REPLACE_ME placeholder. Databricks secret scope: reference a scope + key so the exported bundle resolves it at runtime instead." />
        </div>
        <div className="inline-flex w-fit rounded-full border border-border bg-background p-1 text-xs font-medium dark:border-drac-border/60 dark:bg-[#1f232b]">
          <button
            type="button"
            className={`rounded-full px-3 py-1.5 transition ${
              !secretScopeActive
                ? "bg-blue-9 text-white shadow-sm"
                : "text-slate-11 hover:text-slate-12 dark:text-drac-foreground/80 dark:hover:text-drac-foreground"
            }`}
            onClick={() => onUpdateState({ authSecretMode: "inline" })}
          >
            Enter for preview / placeholder in export
          </button>
          <button
            type="button"
            className={`rounded-full px-3 py-1.5 transition ${
              secretScopeActive
                ? "bg-blue-9 text-white shadow-sm"
                : "text-slate-11 hover:text-slate-12 dark:text-drac-foreground/80 dark:hover:text-drac-foreground"
            }`}
            onClick={() => onUpdateState({ authSecretMode: "secret_scope" })}
          >
            Databricks secret scope
          </button>
        </div>

        {secretScopeActive && (
          <div className="grid gap-3 md:grid-cols-2">
            {!profile && (
              <p className="text-xs text-warning md:col-span-2">
                Pick a Databricks profile in the Deploy tab first to browse secret scopes and keys.
              </p>
            )}
            <label className="flex flex-col gap-2">
              <span className="text-xs font-medium text-slate-11 dark:text-drac-foreground/80">Secret scope</span>
              <select
                className={SELECT_CLASS}
                value={state.authSecretScope || ""}
                disabled={!profile || scopesLoading}
                onChange={(event) => onUpdateState({ authSecretScope: event.target.value, authSecretKey: "" })}
              >
                <option value="">{scopesLoading ? "Loading…" : "Select scope"}</option>
                {scopes.map((scope) => (
                  <option key={scope} value={scope}>
                    {scope}
                  </option>
                ))}
              </select>
              {scopesError && <span className="text-xs text-error">{scopesError}</span>}
            </label>
            <label className="flex flex-col gap-2">
              <span className="text-xs font-medium text-slate-11 dark:text-drac-foreground/80">Secret key</span>
              <select
                className={SELECT_CLASS}
                value={state.authSecretKey || ""}
                disabled={!state.authSecretScope || keysLoading}
                onChange={(event) => onUpdateState({ authSecretKey: event.target.value })}
              >
                <option value="">{keysLoading ? "Loading…" : "Select key"}</option>
                {keys.map((key) => (
                  <option key={key} value={key}>
                    {key}
                  </option>
                ))}
              </select>
              {keysError && <span className="text-xs text-error">{keysError}</span>}
            </label>
          </div>
        )}
      </div>
    ),
    [
      secretScopeActive,
      profile,
      scopes,
      scopesLoading,
      scopesError,
      keys,
      keysLoading,
      keysError,
      state.authSecretScope,
      state.authSecretKey,
      onUpdateState,
    ],
  );

  const handleAuthTypeChange = React.useCallback(
    (nextType: ConfigFormState["authType"]) => {
      const patch: Partial<ConfigFormState> = {
        authType: nextType,
        authSecretMode: "inline",
        authSecretScope: "",
        authSecretKey: "",
      };

      if (nextType === "none") {
        patch.authToken = "";
        patch.authApiKeyIn = state.authApiKeyIn;
        patch.authApiKeyName = state.authApiKeyName;
        patch.authTokenUrl = "";
        patch.authClientId = "";
        patch.authScopes = "";
        patch.authAudience = "";
        patch.authExtraParams = "";
        setBearerToken("");
      }

      if (nextType === "bearer") {
        patch.authApiKeyIn = state.authApiKeyIn;
        patch.authApiKeyName = state.authApiKeyName;
        patch.authTokenUrl = "";
        patch.authClientId = "";
        patch.authScopes = "";
        patch.authAudience = "";
        patch.authExtraParams = "";
      }

      if (nextType === "api_key") {
        patch.authToken = "";
        if (!state.authApiKeyIn) {
          patch.authApiKeyIn = "header";
        }
        if (!state.authApiKeyName) {
          patch.authApiKeyName = "X-API-Key";
        }
        patch.authTokenUrl = "";
        patch.authClientId = "";
        patch.authScopes = "";
        patch.authAudience = "";
        patch.authExtraParams = "";
        setBearerToken("");
      }

      if (nextType === "oauth2") {
        patch.authToken = "";
        patch.authTokenUrl = "";
        patch.authClientId = "";
        patch.authScopes = "";
        patch.authAudience = "";
        patch.authExtraParams = "";
        setBearerToken("");
      }

      onUpdateState(patch);
    },
    [onUpdateState, setBearerToken, state.authApiKeyIn, state.authApiKeyName, state.authToken],
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
                <InfoTooltip text="Authentication method applied to each request. Not persisted in the saved config." />
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
                  <option value="oauth2">OAuth 2.0 (Client Credentials)</option>
                </select>
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-10 dark:text-drac-muted">
                  <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                    <path d="M5.8 7.5a.75.75 0 0 1 1.05-.2L10 9.2l3.15-1.9a.75.75 0 0 1 .75 1.3l-3.5 2.11a.75.75 0 0 1-.76 0L5.99 8.6a.75.75 0 0 1-.2-1.1Z" />
                  </svg>
                </span>
              </div>
            </label>

            {state.authType === "bearer" && (
              <>
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">
                      {secretScopeActive ? "Bearer Token — preview value (optional)" : "Bearer Token"}
                    </span>
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
                {renderSecretSourcePicker()}
              </>
            )}

            {state.authType === "api_key" && (
              <div className="grid gap-5 md:grid-cols-2">
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Placement</span>
                    <InfoTooltip text="Whether the API key is sent as a request header or a query parameter." />
                  </div>
                  <div className="relative">
                    <select
                      className="w-full rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm appearance-none pr-9 transition-all focus:border-blue-7 dark:focus:border-drac-accent focus:outline-none"
                      value={state.authApiKeyIn || "header"}
                      onChange={(event) =>
                        onUpdateState({ authApiKeyIn: event.target.value as ConfigFormState["authApiKeyIn"] })
                      }
                    >
                      <option value="header">Header</option>
                      <option value="query">Query parameter</option>
                    </select>
                    <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-10 dark:text-drac-muted">
                      <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                        <path d="M5.8 7.5a.75.75 0 0 1 1.05-.2L10 9.2l3.15-1.9a.75.75 0 0 1 .75 1.3l-3.5 2.11a.75.75 0 0 1-.76 0L5.99 8.6a.75.75 0 0 1-.2-1.1Z" />
                      </svg>
                    </span>
                  </div>
                </label>
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">
                      {state.authApiKeyIn === "query" ? "Query Param Name" : "Header Name"}
                    </span>
                    <InfoTooltip text="Name of the header or query parameter that will carry the API key at runtime." />
                  </div>
                  <input
                    type="text"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder={state.authApiKeyIn === "query" ? "api_key" : "X-API-Key"}
                    value={state.authApiKeyName || ""}
                    onChange={(event) => onUpdateState({ authApiKeyName: event.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-2 md:col-span-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">
                      {secretScopeActive ? "API Key — preview value (optional)" : "API Key (secret)"}
                    </span>
                    <InfoTooltip text="Secret API key stored only in the browser session for previewing; the exported script gets a REPLACE_ME placeholder instead." />
                  </div>
                  <input
                    type="password"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="your-api-key"
                    value={state.authToken}
                    onChange={(event) => handleBearerTokenChange(event.target.value)}
                  />
                </label>
                {renderSecretSourcePicker()}
              </div>
            )}

            {state.authType === "oauth2" && (
              <div className="grid gap-5 md:grid-cols-2">
                <label className="flex flex-col gap-2 md:col-span-1">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Token URL</span>
                    <InfoTooltip text="OAuth2 token endpoint used for the client credentials grant." />
                  </div>
                  <input
                    type="url"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="https://example.com/oauth/token"
                    value={state.authTokenUrl || ''}
                    onChange={(event) => onUpdateState({ authTokenUrl: event.target.value })}
                  />
                </label>

                <label className="flex flex-col gap-2 md:col-span-1">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Client ID</span>
                    <InfoTooltip text="Public client identifier used when requesting the token." />
                  </div>
                  <input
                    type="text"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="client-id"
                    value={state.authClientId || ''}
                    onChange={(event) => onUpdateState({ authClientId: event.target.value })}
                  />
                </label>

                <label className="flex flex-col gap-2 md:col-span-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">
                      {secretScopeActive ? "Client Secret — preview value (optional)" : "Client Secret"}
                    </span>
                    <InfoTooltip text="Secret stored only in this session and passed as a runtime option ('oauth_client_secret')." />
                  </div>
                  <input
                    type="password"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="your-client-secret"
                    value={state.authToken}
                    onChange={(event) => handleBearerTokenChange(event.target.value)}
                  />
                </label>
                {renderSecretSourcePicker()}

                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Scopes</span>
                    <InfoTooltip text="Optional list of scopes separated by spaces or commas." />
                  </div>
                  <input
                    type="text"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="read write"
                    value={state.authScopes || ''}
                    onChange={(event) => onUpdateState({ authScopes: event.target.value })}
                  />
                </label>

                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Audience</span>
                    <InfoTooltip text="Optional audience parameter included with the token request." />
                  </div>
                  <input
                    type="text"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="https://api.example.com"
                    value={state.authAudience || ''}
                    onChange={(event) => onUpdateState({ authAudience: event.target.value })}
                  />
                </label>

                <label className="flex flex-col gap-2 md:col-span-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Extra Params (JSON)</span>
                    <InfoTooltip text="Optional JSON object merged into the token request body." />
                  </div>
                  <textarea
                    className="min-h-[90px] rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm leading-snug text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder='{\"resource\": \"https://graph.microsoft.com\"}'
                    value={state.authExtraParams || ''}
                    onChange={(event) => onUpdateState({ authExtraParams: event.target.value })}
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
