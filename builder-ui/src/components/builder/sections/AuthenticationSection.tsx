import React from "react";
import { useAtom } from "jotai";
import type { ConfigFormState } from "../../../types";
import { databricksProfileAtom } from "../../../atoms";
import {
  ApiError,
  listDatabricksProfiles,
  listDatabricksSecretKeys,
  listDatabricksSecretScopes,
  listDatabricksServiceCredentials,
} from "../../../lib/api";
import { BTN_LINK, Field, INPUT, RadioRow, SELECT, SegmentedControl, SelectInput, TEXTAREA, cx } from "../../ui/primitives";

export interface AuthenticationSectionProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
  setBearerToken: (value: string) => void;
}

// Shown under every preview-secret input. Saved connectors never persist
// the preview secret (it's session-only), so it has to be re-entered after
// a reload or after resuming/loading a connector.
const SECRET_NOT_SAVED_HINT =
  "Not saved with the connector — re-enter after a reload.";

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

const AUTH_TYPE_OPTIONS: Array<{ value: ConfigFormState["authType"]; label: string }> = [
  { value: "none", label: "None" },
  { value: "bearer", label: "Bearer token" },
  { value: "api_key", label: "API key" },
  { value: "oauth2", label: "OAuth 2.0" },
];

const SECRET_SOURCE_OPTIONS: Array<{ value: ConfigFormState["authSecretMode"]; label: string; description: string }> = [
  {
    value: "inline",
    label: "Preview only",
    description:
      "Enter the secret above to preview in this browser session. The exported script gets a REPLACE_ME placeholder instead.",
  },
  {
    value: "secret_scope",
    label: "Secret scope",
    description: "Reference a Databricks secret scope + key. The exported bundle resolves it at runtime via dbutils.",
  },
  {
    value: "uc_secret",
    label: "UC credential",
    description:
      "Reference a Unity Catalog service credential + Azure Key Vault secret. The exported bundle resolves it at runtime.",
  },
];

export const AuthenticationSection: React.FC<AuthenticationSectionProps> = ({
  state,
  onUpdateState,
  setBearerToken,
}) => {
  // Shared with the Deploy tab's profile picker, but here it's purely
  // optional: it only powers the "Load …" suggestion links below. Every
  // credential/vault/secret/scope/key field is a plain text input
  // regardless of whether a profile is set, so nothing in this section
  // blocks on picking one.
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
  const workspaceBacked = secretScopeActive || ucSecretActive;

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

  // The three loaders below are explicit, user-triggered fetches rather
  // than effects that auto-run on profile change: with no profile selected
  // they simply stay idle (link disabled) instead of anything hanging, and
  // a 501/502 from the backend surfaces as inline text without touching
  // the input.
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

  const previewSuffix = workspaceBacked ? " — preview value (optional)" : "";

  const secretSource = (
    <div className="space-y-3">
      <Field
        as="div"
        label="Secret source"
        tooltip="Where the exported bundle reads this secret from. Preview only: nothing is exported (REPLACE_ME placeholder). Secret scope: Databricks secret scope + key. UC credential: Unity Catalog service credential + Azure Key Vault secret."
      >
        <RadioRow
          name="auth-secret-mode"
          value={state.authSecretMode}
          options={SECRET_SOURCE_OPTIONS}
          onChange={(authSecretMode) => onUpdateState({ authSecretMode })}
        />
      </Field>

      {secretScopeActive && (
        <div className="grid grid-cols-2 gap-4">
          <Field label="Secret scope">
            <input
              type="text"
              list="auth-secret-scope-suggestions"
              className={cx(INPUT, "font-mono text-xs")}
              placeholder="my-scope"
              value={state.authSecretScope || ""}
              onChange={(event) => onUpdateState({ authSecretScope: event.target.value })}
            />
            <datalist id="auth-secret-scope-suggestions">
              {scopes.map((scope) => (
                <option key={scope} value={scope} />
              ))}
            </datalist>
          </Field>
          <Field label="Secret key">
            <input
              type="text"
              list="auth-secret-key-suggestions"
              className={cx(INPUT, "font-mono text-xs")}
              placeholder="api-token"
              value={state.authSecretKey || ""}
              onChange={(event) => onUpdateState({ authSecretKey: event.target.value })}
            />
            <datalist id="auth-secret-key-suggestions">
              {keys.map((key) => (
                <option key={key} value={key} />
              ))}
            </datalist>
          </Field>
        </div>
      )}

      {ucSecretActive && (
        <div className="grid grid-cols-2 gap-4">
          <Field label="UC service credential">
            <input
              type="text"
              list="auth-uc-credential-suggestions"
              className={cx(INPUT, "font-mono text-xs")}
              placeholder="my-service-credential"
              value={state.authUcCredential || ""}
              onChange={(event) => onUpdateState({ authUcCredential: event.target.value })}
            />
            <datalist id="auth-uc-credential-suggestions">
              {credentials.map((credential) => (
                <option key={credential} value={credential} />
              ))}
            </datalist>
          </Field>
          <Field label="Key Vault URL">
            <input
              type="text"
              className={cx(INPUT, "font-mono text-xs")}
              placeholder="https://my-vault.vault.azure.net/"
              value={state.authUcVaultUrl || ""}
              onChange={(event) => onUpdateState({ authUcVaultUrl: event.target.value })}
            />
          </Field>
          <Field label="Secret name" className="col-span-2">
            <input
              type="text"
              className={cx(INPUT, "font-mono text-xs")}
              placeholder="api-token"
              value={state.authUcSecretName || ""}
              onChange={(event) => onUpdateState({ authUcSecretName: event.target.value })}
            />
          </Field>
        </div>
      )}

      {workspaceBacked && (
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-fg-muted">
            <span>Load from workspace:</span>
            {secretScopeActive ? (
              <>
                <button type="button" className={BTN_LINK} onClick={loadScopes} disabled={!profile || scopesLoading}>
                  {scopesLoading ? "Loading scopes…" : "scopes"}
                </button>
                <button
                  type="button"
                  className={BTN_LINK}
                  onClick={loadKeys}
                  disabled={!profile || !state.authSecretScope || keysLoading}
                >
                  {keysLoading ? "Loading keys…" : "keys"}
                </button>
              </>
            ) : (
              <button type="button" className={BTN_LINK} onClick={loadCredentials} disabled={!profile || credentialsLoading}>
                {credentialsLoading ? "Loading credentials…" : "service credentials"}
              </button>
            )}
            <label className="inline-flex items-center gap-1.5">
              <span>using profile</span>
              <span className="relative inline-block">
                <select
                  className={cx(SELECT, "h-7 w-44 max-w-[11rem] py-0 pl-2 pr-7 text-xs")}
                  value={profile}
                  onChange={(event) => setProfile(event.target.value)}
                  aria-label="Databricks profile (optional)"
                >
                  <option value="">{profilesLoading ? "Loading…" : "none selected"}</option>
                  {profiles.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="pointer-events-none absolute right-2 top-1/2 h-3 w-3 -translate-y-1/2 text-fg-subtle" aria-hidden="true">
                  <path d="m3.5 6 4.5 4.5L12.5 6" />
                </svg>
              </span>
            </label>
          </div>
          <p className="text-xs leading-relaxed text-fg-muted">
            Optional — the profile only fills the suggestion lists; every field above accepts free text.
          </p>
          {(profilesError || scopesError || keysError || credentialsError) && (
            <p className="text-xs text-error">{profilesError || scopesError || keysError || credentialsError}</p>
          )}
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-4">
      <Field as="div" label="Authentication" tooltip="Authentication method applied to each request. Secret values are never persisted in the saved config.">
        <SegmentedControl
          fill
          aria-label="Authentication type"
          value={state.authType}
          options={AUTH_TYPE_OPTIONS}
          onChange={handleAuthTypeChange}
        />
      </Field>

      {state.authType === "bearer" && (
        <>
          <Field label={`Bearer token${previewSuffix}`} tooltip="Secret token sent as Authorization header." help={SECRET_NOT_SAVED_HINT}>
            <input
              type="password"
              className={INPUT}
              placeholder="your-token-here"
              value={state.authToken}
              onChange={(event) => handleBearerTokenChange(event.target.value)}
              autoComplete="off"
            />
          </Field>
          {secretSource}
        </>
      )}

      {state.authType === "api_key" && (
        <>
          <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-4">
            <Field label="Placement" tooltip="Whether the API key is sent as a request header or a query parameter.">
              <SelectInput
                value={state.authApiKeyIn || "header"}
                onChange={(event) => onUpdateState({ authApiKeyIn: event.target.value as ConfigFormState["authApiKeyIn"] })}
              >
                <option value="header">Header</option>
                <option value="query">Query parameter</option>
              </SelectInput>
            </Field>
            <Field
              label={state.authApiKeyIn === "query" ? "Query param name" : "Header name"}
              tooltip="Name of the header or query parameter that will carry the API key at runtime."
            >
              <input
                type="text"
                className={cx(INPUT, "font-mono text-xs")}
                placeholder={state.authApiKeyIn === "query" ? "api_key" : "X-API-Key"}
                value={state.authApiKeyName || ""}
                onChange={(event) => onUpdateState({ authApiKeyName: event.target.value })}
              />
            </Field>
          </div>
          <Field
            label={`API key${previewSuffix}`}
            tooltip="Secret API key stored only in the browser session for previewing; the exported script gets a REPLACE_ME placeholder instead."
            help={SECRET_NOT_SAVED_HINT}
          >
            <input
              type="password"
              className={INPUT}
              placeholder="your-api-key"
              value={state.authToken}
              onChange={(event) => handleBearerTokenChange(event.target.value)}
              autoComplete="off"
            />
          </Field>
          {secretSource}
        </>
      )}

      {state.authType === "oauth2" && (
        <>
          <Field label="Token URL" tooltip="OAuth2 token endpoint used for the client credentials grant.">
            <input
              type="url"
              className={INPUT}
              placeholder="https://example.com/oauth/token"
              value={state.authTokenUrl || ''}
              onChange={(event) => onUpdateState({ authTokenUrl: event.target.value })}
            />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Client ID" tooltip="Public client identifier used when requesting the token.">
              <input
                type="text"
                className={INPUT}
                placeholder="client-id"
                value={state.authClientId || ''}
                onChange={(event) => onUpdateState({ authClientId: event.target.value })}
              />
            </Field>
            <Field
              label={`Client secret${previewSuffix}`}
              tooltip="Secret stored only in this session and passed as a runtime option ('oauth_client_secret')."
              help={SECRET_NOT_SAVED_HINT}
            >
              <input
                type="password"
                className={INPUT}
                placeholder="your-client-secret"
                value={state.authToken}
                onChange={(event) => handleBearerTokenChange(event.target.value)}
                autoComplete="off"
              />
            </Field>
          </div>
          {secretSource}
          <div className="grid grid-cols-2 gap-4">
            <Field label="Scopes" tooltip="Optional list of scopes separated by spaces or commas.">
              <input
                type="text"
                className={INPUT}
                placeholder="read write"
                value={state.authScopes || ''}
                onChange={(event) => onUpdateState({ authScopes: event.target.value })}
              />
            </Field>
            <Field label="Audience" tooltip="Optional audience parameter included with the token request.">
              <input
                type="text"
                className={INPUT}
                placeholder="https://api.example.com"
                value={state.authAudience || ''}
                onChange={(event) => onUpdateState({ authAudience: event.target.value })}
              />
            </Field>
          </div>
          <Field label="Extra params (JSON)" tooltip="Optional JSON object merged into the token request body.">
            <textarea
              className={cx(TEXTAREA, "min-h-[64px] font-mono text-xs")}
              rows={2}
              placeholder='{"resource": "https://graph.microsoft.com"}'
              value={state.authExtraParams || ''}
              onChange={(event) => onUpdateState({ authExtraParams: event.target.value })}
            />
          </Field>
        </>
      )}
    </div>
  );
};
