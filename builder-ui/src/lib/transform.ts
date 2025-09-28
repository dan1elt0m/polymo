import type { RestSourceConfig, ConfigFormState } from '../types';

/**
 * Convert form state to API configuration format
 */
export function formStateToConfig(formState: ConfigFormState): RestSourceConfig {
  // Clean up params - remove empty values
  const cleanParams: Record<string, any> = {};
  Object.entries(formState.params).forEach(([key, value]) => {
    if (key.trim() && value.trim()) {
      // Try to parse as number if it looks like one
      const numValue = Number(value);
      cleanParams[key] = !isNaN(numValue) && isFinite(numValue) ? numValue : value;
    }
  });

  return {
    version: formState.version,
    source: {
      type: 'rest',
      base_url: formState.baseUrl,
      ...(formState.authType !== 'none' && {
        auth: {
          type: formState.authType,
          ...(formState.authToken && { token: formState.authToken }),
        },
      }),
    },
    stream: {
      name: formState.streamName,
      path: formState.streamPath,
      params: cleanParams,
      pagination: {
        type: formState.paginationType,
      },
      incremental: {
        mode: formState.incrementalMode || null,
        cursor_param: formState.incrementalCursorParam || null,
        cursor_field: formState.incrementalCursorField || null,
      },
      infer_schema: formState.inferSchema,
      schema: formState.schema || null,
    },
  };
}

/**
 * Convert API configuration to form state
 */
export function configToFormState(config: RestSourceConfig): ConfigFormState {
  // Convert params to string values for form inputs
  const stringParams: Record<string, string> = {};
  Object.entries(config.stream.params || {}).forEach(([key, value]) => {
    stringParams[key] = String(value);
  });

  return {
    version: config.version,
    baseUrl: config.source.base_url,
    authType: config.source.auth?.type || 'none',
    authToken: config.source.auth?.token || '',
    streamName: config.stream.name,
    streamPath: config.stream.path,
    params: stringParams,
    paginationType: config.stream.pagination?.type || 'none',
    incrementalMode: config.stream.incremental?.mode || '',
    incrementalCursorParam: config.stream.incremental?.cursor_param || '',
    incrementalCursorField: config.stream.incremental?.cursor_field || '',
    inferSchema: config.stream.infer_schema ?? true,
    schema: config.stream.schema || '',
  };
}

/**
 * Validate form state and return validation errors
 */
export function validateFormState(formState: ConfigFormState): string[] {
  const errors: string[] = [];

  if (!formState.baseUrl.trim()) {
    errors.push('Base URL is required');
  } else if (!isValidUrl(formState.baseUrl)) {
    errors.push('Base URL must be a valid HTTP/HTTPS URL');
  }

  if (!formState.streamName.trim()) {
    errors.push('Stream name is required');
  }

  if (!formState.streamPath.trim()) {
    errors.push('Stream path is required');
  } else if (!formState.streamPath.startsWith('/')) {
    errors.push('Stream path must start with /');
  }

  if (formState.authType === 'bearer' && !formState.authToken.trim()) {
    errors.push('Bearer token is required when using bearer authentication');
  }

  if (!formState.inferSchema && !formState.schema.trim()) {
    errors.push('Either schema inference must be enabled or a schema must be provided');
  }

  return errors;
}

/**
 * Check if a string is a valid URL
 */
function isValidUrl(str: string): boolean {
  try {
    const url = new URL(str);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}
