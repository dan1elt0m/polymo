// Configuration types matching the Python backend schema

// A reference to a secret stored in a Databricks secret scope. Configs
// carry ONLY this reference (`scope` + `key`) — never the secret value
// itself; the exported bundle resolves it at runtime via `dbutils`.
export interface SecretRef {
  scope: string;
  key: string;
}

// A reference to a secret resolved via a Unity Catalog service credential
// + Azure Key Vault, instead of a Databricks secret scope. Configs carry
// ONLY this reference — never the secret value itself; the exported bundle
// resolves it at runtime via `dbutils.credentials.getServiceCredentialsProvider`
// + the Azure Key Vault SDK.
export interface UcSecretRef {
  credential: string;
  vault_url: string;
  secret_name: string;
}

export interface AuthConfig {
  type: 'none' | 'bearer' | 'oauth2' | 'api_key';
  token?: string | null;
  token_url?: string | null;
  client_id?: string | null;
  client_secret?: string | null;
  scope?: string[] | null;
  audience?: string | null;
  extra_params?: Record<string, any> | null;
  // api_key auth: where the key goes and its header/query name. The key
  // VALUE is never persisted here, same as `token` for bearer.
  api_key_in?: 'header' | 'query' | null;
  api_key_name?: string | null;
  // Optional Databricks secret-scope reference for the auth secret slot
  // (bearer token / api_key value / oauth2 client_secret). When set, the
  // exported bundle resolves the secret from Databricks instead of a
  // REPLACE_ME placeholder. Mutually exclusive with `uc_secret`.
  secret?: SecretRef | null;
  // Optional Unity Catalog service-credential + Key Vault reference for the
  // same auth secret slot. Mutually exclusive with `secret`.
  uc_secret?: UcSecretRef | null;
}

export interface PaginationConfig {
  type: 'none' | 'link_header' | 'offset' | 'cursor' | 'page';
  page_size?: number | null;
  limit_param?: string | null;
  offset_param?: string | null;
  start_offset?: number | null;
  page_param?: string | null;
  start_page?: number | null;
  cursor_param?: string | null;
  cursor_path?: string[] | null;
  next_url_path?: string[] | null;
  cursor_header?: string | null;
  initial_cursor?: string | null;
  stop_on_empty_response?: boolean | null;
  // Added pagination metadata hint fields used for partition planning & UI
  total_pages_path?: string[] | null;
  total_pages_header?: string | null;
  total_records_path?: string[] | null;
  total_records_header?: string | null;
}

export interface IncrementalConfig {
  mode?: string | null;
  cursor_param?: string | null;
  cursor_field?: string | null;
  // Where the generated script keeps the cursor between runs: a local path
  // or an fsspec URL (default `<stream>_state.json`), the seed used when
  // nothing is stored yet, and the entry key inside the state file
  // (default `<stream>@<base_url>`).
  state_path?: string | null;
  start_value?: string | null;
  state_key?: string | null;
}

export interface BackoffConfig {
  initial_delay_seconds: number;
  max_delay_seconds: number;
  multiplier: number;
}

export interface ErrorHandlerConfig {
  max_retries: number;
  retry_statuses: string[];
  retry_on_timeout: boolean;
  retry_on_connection_errors: boolean;
  backoff: BackoffConfig;
}

export interface PartitionConfig {
  strategy: 'none' | 'pagination' | 'param_range' | 'endpoints';
  param?: string | null;
  values?: string | null;
  range_start?: number | string | null;
  range_end?: number | string | null;
  range_step?: number | null;
  range_kind?: 'numeric' | 'date' | null;
  value_template?: string | null;
  extra_template?: string | null;
  endpoints?: string[] | null;
}

export interface StreamConfig {
  // dp table name; defaults to a path-derived name on the backend when
  // omitted or blank.
  name?: string | null;
  path: string;
  params: Record<string, any>;
  headers?: Record<string, any>;
  pagination: PaginationConfig;
  incremental: IncrementalConfig;
  infer_schema: boolean;
  schema?: string | null;
  record_selector: RecordSelectorConfig;
  error_handler?: ErrorHandlerConfig;
  partition?: PartitionConfig;
  streaming?: boolean;
  response_format?: 'json' | 'xml';
  xml_record_path?: string | null;
}

export interface SourceConfig {
  type: 'rest';
  base_url: string;
  auth?: AuthConfig;
}

export interface RestSourceConfig {
  version: string;
  source: SourceConfig;
  stream: StreamConfig;
}

export interface RecordSelectorConfig {
  field_path: string[];
  record_filter?: string | null;
  cast_to_schema_types: boolean;
}

// API response types
export interface ValidationResponse {
  valid: boolean;
  stream?: string | null;
  message?: string;
  config?: RestSourceConfig;
}

// Payload aliases used by api.ts
export type ValidationPayload = ValidationResponse;

export interface GenerateResponse {
  script: string;
  stream: string;
}

export interface SamplePayload {
  stream: string;
  records: Record<string, any>[];
  dtypes: Array<{ column: string; type: string }>;
  raw_pages: RawPagePayload[];
  rest_error?: string | null;
}

export interface RawPagePayload {
  url: string;
  status_code: number;
  payload: unknown;
}

// Databricks builder-integration response shapes (see
// src/polymo/builder/app.py for the source of truth).
export interface DatabricksProfilesResponse {
  profiles: string[];
}

export interface DatabricksCatalogsResponse {
  catalogs: string[];
}

export interface DatabricksSchemasResponse {
  schemas: string[];
}

export interface DatabricksSecretScopesResponse {
  secret_scopes: string[];
}

export interface DatabricksSecretKeysResponse {
  secret_keys: string[];
}

export interface DatabricksServiceCredentialsResponse {
  service_credentials: string[];
}

export interface DatabricksBootstrapResponse {
  project_path: string;
  files: string[];
}

export interface DatabricksCommandResponse {
  ok: boolean;
  output: string;
}

// Form state types for the builder UI
export interface ConfigFormState {
  version: string;
  baseUrl: string;
  authType: 'none' | 'bearer' | 'api_key' | 'oauth2';
  authToken: string;
  authApiKeyIn?: 'header' | 'query'; // placement of the api_key auth value
  authApiKeyName?: string; // header or query parameter name for api_key auth
  authTokenUrl?: string;
  authClientId?: string;
  authScopes?: string;
  authAudience?: string;
  authExtraParams?: string;
  // Where the auth secret value comes from. 'inline' keeps today's
  // behavior (a session-only preview value / REPLACE_ME placeholder on
  // export); 'secret_scope' references a Databricks secret scope + key
  // instead; 'uc_secret' references a Unity Catalog service credential +
  // Azure Key Vault secret. Both non-inline modes are resolved by the
  // exported bundle at runtime instead of a REPLACE_ME placeholder.
  authSecretMode: 'inline' | 'secret_scope' | 'uc_secret';
  authSecretScope?: string;
  authSecretKey?: string;
  // Unity Catalog service-credential secret source fields (authSecretMode
  // === 'uc_secret'). authUcCredential holds the resolved credential name
  // whether it was picked from the profile's list or typed as a custom
  // value — the UI's select-vs-custom toggle is local component state, not
  // part of the saved config.
  authUcCredential?: string;
  authUcVaultUrl?: string;
  authUcSecretName?: string;
  streamName: string;
  streamPath: string;
  streaming: boolean;
  responseFormat: 'json' | 'xml';
  xmlRecordPath?: string;
  params: Record<string, string>;
  paginationType: 'none' | 'link_header' | 'offset' | 'cursor' | 'page';
  // Added pagination input fields used by the Builder UI (not yet serialized to backend config)
  paginationPageSize?: string; // number as string for input control
  paginationLimitParam?: string; // e.g. "limit"
  paginationOffsetParam?: string;
  paginationStartOffset?: string;
  paginationPageParam?: string;
  paginationStartPage?: string;
  paginationCursorParam?: string;
  paginationCursorPath?: string;
  paginationNextUrlPath?: string;
  paginationCursorHeader?: string;
  paginationInitialCursor?: string;
  paginationTotalPagesPath?: string;
  paginationTotalPagesHeader?: string;
  paginationTotalRecordsPath?: string;
  paginationTotalRecordsHeader?: string;
  partitionStrategy: 'none' | 'pagination' | 'param_range' | 'endpoints';
  partitionParam?: string;
  partitionValues?: string;
  partitionRangeStart?: string;
  partitionRangeEnd?: string;
  partitionRangeStep?: string;
  partitionRangeKind?: 'numeric' | 'date';
  partitionValueTemplate?: string;
  partitionExtraTemplate?: string;
  partitionEndpoints?: string;
  incrementalMode: string;
  incrementalCursorParam: string;
  incrementalCursorField: string;
  incrementalStatePath: string;
  incrementalStartValue: string;
  incrementalStateKey: string;
  inferSchema: boolean;
  schema: string;
  headers: Record<string, string>;
  recordFieldPath: string[];
  recordFilter: string;
  castToSchemaTypes: boolean;
  errorHandlerMaxRetries: string;
  errorHandlerRetryStatuses: string[];
  errorHandlerInitialDelaySeconds: string;
  errorHandlerMaxDelaySeconds: string;
  errorHandlerBackoffMultiplier: string;
  errorHandlerRetryOnTimeout: boolean;
  errorHandlerRetryOnConnectionErrors: boolean;
}

export interface SavedConnector {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  formState: ConfigFormState;
  lastEdited: 'ui';
  builderView: 'ui' | 'code' | 'deploy';
  readerOptions: Record<string, string>;
}

// A snapshot of the in-progress editor session (not yet — or not recently —
// saved), persisted separately from `savedConnectors` so an imported or
// freshly-edited config survives a reload even before/between saves. Never
// carries `formState.authToken`: preview secrets are session-only and are
// stripped before this is written to storage (see bug: silent work loss on
// reload).
export interface WorkingState {
  formState: ConfigFormState;
  readerOptions: Record<string, string>;
  builderView: 'ui' | 'code' | 'deploy';
  activeConnectorId: string | null;
  savedAt: string;
}

// Added interfaces used by atoms and components
export interface StatusState {
  tone: 'info' | 'success' | 'warn' | 'error';
  message: string;
}

export interface SampleState {
  data: Array<Record<string, any>>;
  dtypes: Array<{ column: string; type: string }>;
  stream: string;
  limit: number;
  view: 'table' | 'json' | 'raw';
  wrap: boolean;
  page: number;
  pageSize: number;
  loading: boolean;
  rawPages: RawPagePayload[];
  restError: string | null;
}
