import type { RestSourceConfig, ConfigFormState } from '../types';

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
};

export const PAGINATION_TYPES = [
  { value: 'none', label: 'None' },
  { value: 'link_header', label: 'Link Header' },
] as const;

export const AUTH_TYPES = [
  { value: 'none', label: 'None' },
  { value: 'bearer', label: 'Bearer Token' },
] as const;
