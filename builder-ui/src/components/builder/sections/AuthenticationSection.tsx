import React from "react";
import { useAtomValue } from "jotai";
import type { ConfigFormState } from "../../../types";
import { InfoTooltip } from "../../InfoTooltip";
import { databricksProfileAtom } from "../../../atoms";
import {
  ApiError,
  listDatabricksSecretKeys,
  listDatabricksSecretScopes,
  listDatabricksServiceCredentials,
} from "../../../lib/api";

export interface AuthenticationSectionProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
  setBearerToken: (value: string) => void;
}

const AUTH_TOGGLE_ID = "auth-section";
// Sentinel <option> value that swaps the credential field from a select
// (list of the profile's service credentials) to a free-text input — the
// deploy identity may not be able to list every credential (or one may not
// exist yet), so the user needs a way to name one, mirroring the Deploy
// tab's "Custom schema…" affordance.
const CUSTOM_CREDENTIAL_VALUE = "__custom__";

function describeSecretPickerError(error: unknown): string {
  if (error instanceof ApiError && error.status === 501) {
    return error.message;
  }
  return error instanceof Error ? error.message : String(error ?? "Failed to load");
}

const SELECT_CLASS =
  "w-full rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm appearance-none pr-9 transition-all focus:border-blue-7 dark:focus:border-drac-accent focus:outline-none disabled:opacity-60 disabled:cursor-not-allowed";
const INPUT_CLASS =
  "rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5 disabled:opacity-60 disabled:cursor-not-allowed";

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

  // Secret scopes/keys and service credentials are per-workspace. If the
  // shared Databricks profile changes (picked in the Deploy tab), a
  // previously-selected scope/key/credential almost certainly doesn't
  // exist in the new workspace — clear them all so a stale reference from
  // the old workspace never ships silently. Cleared unconditionally (not
  // just in the mode that uses them) since the fields should already be
  // empty in the other modes, so this is a no-op there; the
  // `previousProfileRef` skip avoids wiping a value just-loaded from a
  // saved connector on first mount, when `profile` hasn't actually
  // "changed" from the user's perspective.
  const previousProfileRef = React.useRef(profile);
  React.useEffect(() => {
    if (previousProfileRef.current !== profile) {
      if (state.authSecretScope || state.authSecretKey || state.authUcCredential) {
        onUpdateState({ authSecretScope: "", authSecretKey: "", authUcCredential: "" });
      }
      previousProfileRef.current = profile;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile]);

  const [scopes, setScopes] = React.useState<string[]>([]);
  const [scopesLoading, setScopesLoading] = React.useState(false);
  const [scopesError, setScopesError] = React.useState<string | null>(null);
  const [keys, setKeys] = React.useState<string[]>([]);
  const [keysLoading, setKeysLoading] = React.useState(false);
  const [keysError, setKeysError] = React.useState<string | null>(null);

  const [credentials, setCredentials] = React.useState<string[]>([]);
  const [credentialsLoading, setCredentialsLoading] = React.useState(false);
  const [credentialsError, setCredentialsError] = React.useState<string | null>(null);
  // Starts in "custom" mode when a credential is already set (e.g. loaded
  // from a saved connector) so its value stays visible even before/without
  // the profile's credential list loading — mirrors the Deploy tab's
  // schema field, which has the same "may already hold a value the list
  // doesn't have yet" situation.
  const [credentialMode, setCredentialMode] = React.useState<"select" | "custom">(() =>
    state.authUcCredential ? "custom" : "select",
  );

  const secretScopeActive = state.authSecretMode === "secret_scope";
  const ucSecretActive = state.authSecretMode === "uc_secret";

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

  React.useEffect(() => {
    if (!ucSecretActive || !profile || credentialMode !== "select") {
      setCredentials([]);
      setCredentialsError(null);
      return;
    }
    let cancelled = false;
    setCredentialsLoading(true);
    setCredentialsError(null);
    listDatabricksServiceCredentials(profile)
      .then((res) => {
        if (!cancelled) setCredentials(res.service_credentials);
      })
      .catch((err) => {
        if (!cancelled) setCredentialsError(describeSecretPickerError(err));
      })
      .finally(() => {
        if (!cancelled) setCredentialsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ucSecretActive, profile, credentialMode]);

  const renderSecretSourcePicker = React.useCallback(
    () => (
      <div className="flex flex-col gap-3 md:col-span-2">
        <div className="flex items-center gap-1">
          <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Secret source</span>
          <InfoTooltip text="Preview value: enter a value used only for previewing in this browser session; the exported script gets a REPLACE_ME placeholder. Databricks secret scope: reference a scope + key so the exported bundle resolves it at runtime instead. UC credential (Key Vault): reference a Unity Catalog service credential + Azure Key Vault secret instead." />
        </div>
        <div className="inline-flex w-fit flex-wrap rounded-full border border-border bg-background p-1 text-xs font-medium dark:border-drac-border/60 dark:bg-[#1f232b]">
          <button
            type="button"
            className={`rounded-full px-3 py-1.5 transition ${
              state.authSecretMode === "inline"
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
          <button
            type="button"
            className={`rounded-full px-3 py-1.5 transition ${
              ucSecretActive
                ? "bg-blue-9 text-white shadow-sm"
                : "text-slate-11 hover:text-slate-12 dark:text-drac-foreground/80 dark:hover:text-drac-foreground"
            }`}
            onClick={() => onUpdateState({ authSecretMode: "uc_secret" })}
          >
            UC credential (Key Vault)
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

        {ucSecretActive && (
          <div className="grid gap-3 md:grid-cols-2">
            {!profile && (
              <p className="text-xs text-warning md:col-span-2">
                Pick a Databricks profile in the Deploy tab first to browse service credentials.
              </p>
            )}
            <label className="flex flex-col gap-2">
              <span className="text-xs font-medium text-slate-11 dark:text-drac-foreground/80">
                UC service credential
              </span>
              {credentialMode === "custom" ? (
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    className={`${INPUT_CLASS} flex-1`}
                    placeholder="my-service-credential"
                    value={state.authUcCredential || ""}
                    onChange={(event) => onUpdateState({ authUcCredential: event.target.value })}
                  />
                  <button
                    type="button"
                    className="whitespace-nowrap text-xs text-muted underline dark:text-drac-muted"
                    onClick={() => {
                      setCredentialMode("select");
                      onUpdateState({ authUcCredential: "" });
                    }}
                  >
                    Back to list
                  </button>
                </div>
              ) : (
                <select
                  className={SELECT_CLASS}
                  value={state.authUcCredential || ""}
                  disabled={!profile || credentialsLoading}
                  onChange={(event) => {
                    if (event.target.value === CUSTOM_CREDENTIAL_VALUE) {
                      setCredentialMode("custom");
                      onUpdateState({ authUcCredential: "" });
                    } else {
                      onUpdateState({ authUcCredential: event.target.value });
                    }
                  }}
                >
                  <option value="">{credentialsLoading ? "Loading…" : "Select credential"}</option>
                  {credentials.map((credential) => (
                    <option key={credential} value={credential}>
                      {credential}
                    </option>
                  ))}
                  <option value={CUSTOM_CREDENTIAL_VALUE}>Custom credential name…</option>
                </select>
              )}
              {credentialsError && <span className="text-xs text-error">{credentialsError}</span>}
            </label>
            <label className="flex flex-col gap-2">
              <span className="text-xs font-medium text-slate-11 dark:text-drac-foreground/80">
                Key Vault URL
              </span>
              <input
                type="url"
                className={INPUT_CLASS}
                placeholder="https://my-vault.vault.azure.net/"
                value={state.authUcVaultUrl || ""}
                onChange={(event) => onUpdateState({ authUcVaultUrl: event.target.value })}
              />
            </label>
            <label className="flex flex-col gap-2 md:col-span-2">
              <span className="text-xs font-medium text-slate-11 dark:text-drac-foreground/80">Secret name</span>
              <input
                type="text"
                className={INPUT_CLASS}
                placeholder="api-token"
                value={state.authUcSecretName || ""}
                onChange={(event) => onUpdateState({ authUcSecretName: event.target.value })}
              />
            </label>
          </div>
        )}
      </div>
    ),
    [
      secretScopeActive,
      ucSecretActive,
      state.authSecretMode,
      profile,
      scopes,
      scopesLoading,
      scopesError,
      keys,
      keysLoading,
      keysError,
      state.authSecretScope,
      state.authSecretKey,
      credentials,
      credentialsLoading,
      credentialsError,
      credentialMode,
      state.authUcCredential,
      state.authUcVaultUrl,
      state.authUcSecretName,
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
        authUcCredential: "",
        authUcVaultUrl: "",
        authUcSecretName: "",
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
                      {secretScopeActive || ucSecretActive ? "Bearer Token — preview value (optional)" : "Bearer Token"}
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
                      {secretScopeActive || ucSecretActive ? "API Key — preview value (optional)" : "API Key (secret)"}
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
                      {secretScopeActive || ucSecretActive ? "Client Secret — preview value (optional)" : "Client Secret"}
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
