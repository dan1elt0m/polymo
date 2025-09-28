import type { RestSourceConfig, ConfigFormState } from '../types';

export const INITIAL_CONFIG: RestSourceConfig = {
  version: '0.1',
  source: {
    type: 'rest',
    base_url: 'https://jsonplaceholder.typicode.com',
    auth: {
      type: 'none',
      token: null,
    },
  },
  stream: {
    name: 'posts',
    path: '/posts',
    params: {
      _limit: '25',
    },
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
  },
};

export const INITIAL_FORM_STATE: ConfigFormState = {
  version: '0.1',
  baseUrl: 'https://jsonplaceholder.typicode.com',
  authType: 'none',
  authToken: '',
  streamName: 'posts',
  streamPath: '/posts',
  params: {
    _limit: '25',
  },
  paginationType: 'none',
  incrementalMode: '',
  incrementalCursorParam: '',
  incrementalCursorField: '',
  inferSchema: true,
  schema: '',
};

export const PAGINATION_TYPES = [
  { value: 'none', label: 'None' },
  { value: 'link_header', label: 'Link Header' },
] as const;

export const AUTH_TYPES = [
  { value: 'none', label: 'None' },
  { value: 'bearer', label: 'Bearer Token' },
] as const;
