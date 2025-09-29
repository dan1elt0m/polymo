import type { RestSourceConfig, ConfigFormState, ErrorHandlerConfig } from '../types';

export const DEFAULT_ERROR_HANDLER: ErrorHandlerConfig = {
  max_retries: 5,
  retry_statuses: ['5XX', '429'],
  retry_on_timeout: true,
  retry_on_connection_errors: true,
  backoff: {
    initial_delay_seconds: 1,
    max_delay_seconds: 30,
    multiplier: 2,
  },
};

export const INITIAL_CONFIG: RestSourceConfig = {
  version: '0.1',
  source: {
    type: 'rest',
    base_url: '',
    auth: {
      type: 'none',
      token: null,
    },
  },
  stream: {
    path: '',
    params: {},
    headers: {},
    pagination: {
      type: 'none',
    },
    incremental: {
      mode: null,
      cursor_param: null,
      cursor_field: null,
    },
    infer_schema: true,
    schema: null,
    record_selector: {
      field_path: [],
      record_filter: null,
      cast_to_schema_types: false,
    },
    error_handler: DEFAULT_ERROR_HANDLER,
  },
};

export const INITIAL_FORM_STATE: ConfigFormState = {
  version: '0.1',
  baseUrl: '',
  authType: 'none',
  authToken: '',
  streamPath: '',
  params: {},
  headers: {},
  paginationType: 'none',
  incrementalMode: '',
  incrementalCursorParam: '',
  incrementalCursorField: '',
  incrementalStatePath: '',
  incrementalStartValue: '',
  incrementalStateKey: '',
  incrementalMemoryEnabled: true,
  inferSchema: true,
  schema: '',
  recordFieldPath: [],
  recordFilter: '',
  castToSchemaTypes: false,
  errorHandlerMaxRetries: String(DEFAULT_ERROR_HANDLER.max_retries),
  errorHandlerRetryStatuses: [...DEFAULT_ERROR_HANDLER.retry_statuses],
  errorHandlerInitialDelaySeconds: String(DEFAULT_ERROR_HANDLER.backoff.initial_delay_seconds),
  errorHandlerMaxDelaySeconds: String(DEFAULT_ERROR_HANDLER.backoff.max_delay_seconds),
  errorHandlerBackoffMultiplier: String(DEFAULT_ERROR_HANDLER.backoff.multiplier),
  errorHandlerRetryOnTimeout: DEFAULT_ERROR_HANDLER.retry_on_timeout,
  errorHandlerRetryOnConnectionErrors: DEFAULT_ERROR_HANDLER.retry_on_connection_errors,
};

export const PAGINATION_TYPES = [
  { value: 'none', label: 'None' },
  { value: 'link_header', label: 'Link Header' },
] as const;

export const AUTH_TYPES = [
  { value: 'none', label: 'None' },
  { value: 'bearer', label: 'Bearer Token' },
] as const;
