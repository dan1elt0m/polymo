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
  name: string;
  path: string;
  params: Record<string, any>;
  pagination: PaginationConfig;
  incremental: IncrementalConfig;
  infer_schema: boolean;
  schema?: string | null;
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

// API response types
export interface ValidationResponse {
  valid: boolean;
  stream?: string | null;
  message?: string;
  config?: RestSourceConfig;
  yaml?: string;
}

export interface SampleResponse {
  stream: string;
  records: Record<string, any>[];
  dtypes: Array<{ column: string; type: string }>;
}

export interface FormatResponse {
  yaml: string;
}

// Form state types for the builder UI
export interface ConfigFormState {
  version: string;
  baseUrl: string;
  authType: 'none' | 'bearer';
  authToken: string;
  streamName: string;
  streamPath: string;
  params: Record<string, string>;
  paginationType: 'none' | 'link_header';
  incrementalMode: string;
  incrementalCursorParam: string;
  incrementalCursorField: string;
  inferSchema: boolean;
  schema: string;
}
