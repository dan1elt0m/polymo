// Configuration types matching the Python backend schema

export interface AuthConfig {
  type: 'none' | 'bearer' | 'api_key';
  token?: string | null;
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
}

export interface IncrementalConfig {
  mode?: string | null;
  cursor_param?: string | null;
  cursor_field?: string | null;
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

export interface StreamConfig {
  // name removed from persisted config; backend derives internally
  path: string;
  params: Record<string, any>;
  headers?: Record<string, any>;
  pagination: PaginationConfig;
  incremental: IncrementalConfig;
  infer_schema: boolean;
  schema?: string | null;
  record_selector: RecordSelectorConfig;
  error_handler?: ErrorHandlerConfig;
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
  yaml?: string;
}

// Payload aliases used by api.ts
export type ValidationPayload = ValidationResponse;
export interface SamplePayload {
  stream: string;
  records: Record<string, any>[];
  dtypes: Array<{ column: string; type: string }>;
  raw_pages: RawPagePayload[];
  rest_error?: string | null;
}

export interface RawPagePayload {
  page: number;
  url: string;
  status_code: number;
  headers?: Record<string, string>;
  records: Record<string, any>[];
  payload: unknown;
}

// Form state types for the builder UI
export interface ConfigFormState {
  version: string;
  baseUrl: string;
  authType: 'none' | 'bearer' | 'api_key';
  authToken: string;
  authApiKeyParamName?: string; // name of the query parameter for api_key auth
  streamPath: string;
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
  paginationStopOnEmptyResponse: boolean;
  incrementalMode: string;
  incrementalCursorParam: string;
  incrementalCursorField: string;
  incrementalStatePath: string;
  incrementalStartValue: string;
  incrementalStateKey: string;
  incrementalMemoryEnabled: boolean;
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
  yaml: string;
  lastEdited: 'ui' | 'yaml';
  builderView: 'ui' | 'yaml';
  readerOptions: Record<string, string>;
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
