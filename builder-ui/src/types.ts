// Configuration types matching the Python backend schema

export interface AuthConfig {
  type: 'none' | 'bearer';
  token?: string | null;
}

export interface PaginationConfig {
  type: 'none' | 'link_header';
}

export interface IncrementalConfig {
  mode?: string | null;
  cursor_param?: string | null;
  cursor_field?: string | null;
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
  authType: 'none' | 'bearer';
  authToken: string;
  streamPath: string;
  params: Record<string, string>;
  paginationType: 'none' | 'link_header';
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
