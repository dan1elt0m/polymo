import React from "react";
import { useAtom } from "jotai";
import type { ConfigFormState } from "../../../types";
import { InfoTooltip } from "../../InfoTooltip";
import { databricksProfileAtom } from "../../../atoms";
import {
  ApiError,
  listDatabricksProfiles,
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

// Shown under every preview-secret input. Saved connectors never persist
// the preview secret (it's session-only), so it has to be re-entered after
// a reload or after resuming/loading a connector.
const SECRET_NOT_SAVED_HINT =
  "Not saved with the connector — you'll need to re-enter this after a reload.";

function describeSecretPickerError(error: unknown): string {
  // 501/502 (feature disabled on the backend, or the Databricks CLI call
  // itself failing) are the two workspace-lookup failure modes surfaced by
  // /api/databricks/*. Both render inline next to the "Load from workspace"
  // action; they never disable the free-text inputs.
  if (error instanceof ApiError && (error.status === 501 || error.status === 502)) {
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

  // Shared with the Deploy tab's profile picker, but here it's purely
  // optional: it only powers the "Load from workspace" suggestion buttons
  // below. Every credential/vault/secret/scope/key field is a plain text
  // input regardless of whether a profile is set, so nothing in this
  // section blocks on picking one — that was the bug (the UC credential
  // picker used to hang whenever no profile had been chosen in the Deploy
  // tab, since it only offered a <select> with no way to type a value).
  const [profile, setProfile] = useAtom(databricksProfileAtom);
  const [profiles, setProfiles] = React.useState<string[]>([]);
  const [profilesLoading, setProfilesLoading] = React.useState(false);
  const [profilesError, setProfilesError] = React.useState<string | null>(null);

  const [scopes, setScopes] = React.useState<string[]>([]);
  const [scopesLoading, setScopesLoading] = React.useState(false);
  const [scopesError, setScopesError] = React.useState<string | null>(null);
  const [keys, setKeys] = React.useState<string[]>([]);
  const [keysLoading, setKeysLoading] = React.useState(false);
  const [keysError, setKeysError] = React.useState<string | null>(null);

  const [credentials, setCredentials] = React.useState<string[]>([]);
  const [credentialsLoading, setCredentialsLoading] = React.useState(false);
  const [credentialsError, setCredentialsError] = React.useState<string | null>(null);

  const secretScopeActive = state.authSecretMode === "secret_scope";
  const ucSecretActive = state.authSecretMode === "uc_secret";

  // Lazily fetch the profile list the first time a workspace-backed secret
  // source is opened, so the inline profile picker below has options
  // without requiring a trip to the Deploy tab. This is a background
  // convenience fetch only — it never gates the text inputs.
  React.useEffect(() => {
    if (!secretScopeActive && !ucSecretActive) return;
    if (profilesLoading || profiles.length > 0) return;
    let cancelled = false;
    setProfilesLoading(true);
    setProfilesError(null);
    listDatabricksProfiles()
      .then((res) => {
        if (!cancelled) setProfiles(res.profiles);
      })
      .catch((err) => {
        if (!cancelled) setProfilesError(describeSecretPickerError(err));
      })
      .finally(() => {
        if (!cancelled) setProfilesLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [secretScopeActive, ucSecretActive]);

  // The three loaders below are explicit, user-triggered ("Load from
  // workspace") fetches rather than effects that auto-run on profile
  // change: with no profile selected they simply stay idle (button
  // disabled) instead of anything hanging, and a 501/502 from the backend
  // surfaces as inline text next to the button without touching the input.
  const loadScopes = React.useCallback(() => {
    if (!profile) return;
    setScopesLoading(true);
    setScopesError(null);
    listDatabricksSecretScopes(profile)
      .then((res) => setScopes(res.secret_scopes))
      .catch((err) => setScopesError(describeSecretPickerError(err)))
      .finally(() => setScopesLoading(false));
  }, [profile]);

  const loadKeys = React.useCallback(() => {
    if (!profile || !state.authSecretScope) return;
    setKeysLoading(true);
    setKeysError(null);
    listDatabricksSecretKeys(state.authSecretScope, profile)
      .then((res) => setKeys(res.secret_keys))
      .catch((err) => setKeysError(describeSecretPickerError(err)))
      .finally(() => setKeysLoading(false));
  }, [profile, state.authSecretScope]);

  const loadCredentials = React.useCallback(() => {
    if (!profile) return;
    setCredentialsLoading(true);
    setCredentialsError(null);
    listDatabricksServiceCredentials(profile)
      .then((res) => setCredentials(res.service_credentials))
      .catch((err) => setCredentialsError(describeSecretPickerError(err)))
      .finally(() => setCredentialsLoading(false));
  }, [profile]);

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

        {(secretScopeActive || ucSecretActive) && (
          <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border/60 bg-background/40 px-3 py-2.5 dark:border-drac-border/50">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-slate-11 dark:text-drac-foreground/80">
                Databricks profile (optional)
              </span>
              <select
                className={`${SELECT_CLASS} w-52`}
                value={profile}
                onChange={(event) => setProfile(event.target.value)}
              >
                <option value="">{profilesLoading ? "Loading…" : "No profile selected"}</option>
                {profiles.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
            <p className="max-w-sm text-xs text-muted dark:text-drac-muted">
              Only used to look up workspace suggestions below via "Load from workspace" — every
              field here also accepts free text, so this can be left unset.
            </p>
            {profilesError && <span className="text-xs text-error">{profilesError}</span>}
          </div>
        )}

        {secretScopeActive && (
          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-2">
              <span className="text-xs font-medium text-slate-11 dark:text-drac-foreground/80">Secret scope</span>
              <input
                type="text"
                list="auth-secret-scope-suggestions"
                className={INPUT_CLASS}
                placeholder="my-scope"
                value={state.authSecretScope || ""}
                onChange={(event) => onUpdateState({ authSecretScope: event.target.value })}
              />
              <datalist id="auth-secret-scope-suggestions">
                {scopes.map((scope) => (
                  <option key={scope} value={scope} />
                ))}
              </datalist>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="whitespace-nowrap text-xs text-blue-10 underline decoration-dotted disabled:cursor-not-allowed disabled:text-muted disabled:no-underline dark:text-drac-accent"
                  onClick={loadScopes}
                  disabled={!profile || scopesLoading}
                >
                  {scopesLoading ? "Loading…" : "Load from workspace"}
                </button>
                {scopesError && <span className="text-xs text-error">{scopesError}</span>}
              </div>
            </label>
            <label className="flex flex-col gap-2">
              <span className="text-xs font-medium text-slate-11 dark:text-drac-foreground/80">Secret key</span>
              <input
                type="text"
                list="auth-secret-key-suggestions"
                className={INPUT_CLASS}
                placeholder="api-token"
                value={state.authSecretKey || ""}
                onChange={(event) => onUpdateState({ authSecretKey: event.target.value })}
              />
              <datalist id="auth-secret-key-suggestions">
                {keys.map((key) => (
                  <option key={key} value={key} />
                ))}
              </datalist>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="whitespace-nowrap text-xs text-blue-10 underline decoration-dotted disabled:cursor-not-allowed disabled:text-muted disabled:no-underline dark:text-drac-accent"
                  onClick={loadKeys}
                  disabled={!profile || !state.authSecretScope || keysLoading}
                >
                  {keysLoading ? "Loading…" : "Load from workspace"}
                </button>
                {keysError && <span className="text-xs text-error">{keysError}</span>}
              </div>
            </label>
          </div>
        )}

        {ucSecretActive && (
          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-2">
              <span className="text-xs font-medium text-slate-11 dark:text-drac-foreground/80">
                UC service credential
              </span>
              <input
                type="text"
                list="auth-uc-credential-suggestions"
                className={INPUT_CLASS}
                placeholder="my-service-credential"
                value={state.authUcCredential || ""}
                onChange={(event) => onUpdateState({ authUcCredential: event.target.value })}
              />
              <datalist id="auth-uc-credential-suggestions">
                {credentials.map((credential) => (
                  <option key={credential} value={credential} />
                ))}
              </datalist>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="whitespace-nowrap text-xs text-blue-10 underline decoration-dotted disabled:cursor-not-allowed disabled:text-muted disabled:no-underline dark:text-drac-accent"
                  onClick={loadCredentials}
                  disabled={!profile || credentialsLoading}
                >
                  {credentialsLoading ? "Loading…" : "Load from workspace"}
                </button>
                {credentialsError && <span className="text-xs text-error">{credentialsError}</span>}
              </div>
            </label>
            <label className="flex flex-col gap-2">
              <span className="text-xs font-medium text-slate-11 dark:text-drac-foreground/80">
                Key Vault URL
              </span>
              <input
                type="text"
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
      profile,
      setProfile,
      profiles,
      profilesLoading,
      profilesError,
      scopes,
      scopesLoading,
      scopesError,
      loadScopes,
      keys,
      keysLoading,
      keysError,
      loadKeys,
      state.authSecretScope,
      state.authSecretKey,
      credentials,
      credentialsLoading,
      credentialsError,
      loadCredentials,
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
                  <span className="text-xs text-muted dark:text-drac-muted">{SECRET_NOT_SAVED_HINT}</span>
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
                  <span className="text-xs text-muted dark:text-drac-muted">{SECRET_NOT_SAVED_HINT}</span>
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
                  <span className="text-xs text-muted dark:text-drac-muted">{SECRET_NOT_SAVED_HINT}</span>
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
