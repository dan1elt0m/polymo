import type { RestSourceConfig, ConfigFormState, ErrorHandlerConfig } from '../types';
import { DEFAULT_ERROR_HANDLER } from './initial-data';

/**
 * Convert form state to API configuration format
 */
export function formStateToConfig(formState: ConfigFormState): RestSourceConfig {
  // Clean up params - remove empty values
  const cleanParams: Record<string, any> = {};
  Object.entries(formState.params).forEach(([key, value]) => {
    if (key.trim() && value.trim()) {
      const numValue = Number(value);
      cleanParams[key] = !isNaN(numValue) && isFinite(numValue) ? numValue : value;
    }
  });

  // Inject api_key param placeholder if using api_key auth and user hasn't defined it
  if (formState.authType === 'api_key') {
    const paramName = (formState.authApiKeyParamName || 'api_key').trim();
    if (paramName && !(paramName in cleanParams)) {
      cleanParams[paramName] = `{{ options.${paramName} }}`;
    }
  }

  // Clean up headers - remove empty values
  const cleanHeaders: Record<string, any> = {};
  Object.entries(formState.headers || {}).forEach(([key, value]) => {
    if (key.trim() && value.trim()) {
      cleanHeaders[key] = value;
    }
  });

  const fieldPathSegments = (formState.recordFieldPath || [])
    .map((segment) => segment.trim())
    .filter((segment) => segment.length > 0);
  const recordFilter = formState.recordFilter.trim();

  const parseIntOrDefault = (value: string, fallback: number): number => {
    const parsed = Number.parseInt(value, 10);
    return Number.isInteger(parsed) && parsed >= 0 ? parsed : fallback;
  };
  const parseFloatOrDefault = (value: string, fallback: number): number => {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
  };
  const parseOptionalInteger = (
    value?: string | null,
    minimum: number | undefined = undefined,
  ): number | undefined => {
    if (value === undefined || value === null) {
      return undefined;
    }
    const trimmed = value.trim();
    if (!trimmed) {
      return undefined;
    }
    const parsed = Number.parseInt(trimmed, 10);
    if (!Number.isFinite(parsed)) {
      return undefined;
    }
    if (minimum !== undefined && parsed < minimum) {
      return undefined;
    }
    return parsed;
  };
  const parseOptionalPositiveInt = (value?: string | null): number | undefined =>
    parseOptionalInteger(value, 1);
  const parseOptionalNonNegativeInt = (value?: string | null): number | undefined =>
    parseOptionalInteger(value, 0);
  const parsePathInput = (value?: string | null): string[] | undefined => {
    if (!value) {
      return undefined;
    }
    const segments = value
      .split('.')
      .map((segment) => segment.trim())
      .filter((segment) => segment.length > 0);
    return segments.length > 0 ? segments : undefined;
  };

  const sanitizedRetryStatuses = (formState.errorHandlerRetryStatuses || [])
    .map((status) => status.trim().toUpperCase())
    .filter((status) => status.length > 0);

  const fallbackHandler = DEFAULT_ERROR_HANDLER;
  const errorHandler = {
    max_retries: parseIntOrDefault(formState.errorHandlerMaxRetries, fallbackHandler.max_retries),
    retry_statuses: sanitizedRetryStatuses,
    retry_on_timeout: formState.errorHandlerRetryOnTimeout,
    retry_on_connection_errors: formState.errorHandlerRetryOnConnectionErrors,
    backoff: {
      initial_delay_seconds: parseFloatOrDefault(
        formState.errorHandlerInitialDelaySeconds,
        fallbackHandler.backoff.initial_delay_seconds,
      ),
      max_delay_seconds: parseFloatOrDefault(
        formState.errorHandlerMaxDelaySeconds,
        fallbackHandler.backoff.max_delay_seconds,
      ),
      multiplier: parseFloatOrDefault(
        formState.errorHandlerBackoffMultiplier,
        fallbackHandler.backoff.multiplier,
      ) || fallbackHandler.backoff.multiplier,
    },
  } satisfies ErrorHandlerConfig;

  // Create partition config if strategy is not 'none'
  const partitionConfig = (() => {
    if (formState.partitionStrategy === 'none') {
      return undefined;
    }

    const config: Record<string, any> = {
      strategy: formState.partitionStrategy
    };

    if (formState.partitionStrategy === 'pagination') {
      // No additional fields needed for pagination strategy
      return config;
    }

    if (formState.partitionStrategy === 'param_range') {
      const param = formState.partitionParam?.trim();
      if (param) {
        config.param = param;
      }

      // NEW: serialize explicit values list (overrides range generation on backend)
      const rawValues = formState.partitionValues?.trim();
      if (rawValues) {
        config.values = rawValues; // keep raw string; backend can parse CSV or JSON
      }

      if (!rawValues) { // only serialize range fields if no explicit values provided
        if (formState.partitionRangeKind === 'numeric') {
          const start = parseOptionalInteger(formState.partitionRangeStart);
          if (start !== undefined) {
            config.range_start = start;
          }

          const end = parseOptionalInteger(formState.partitionRangeEnd);
            if (end !== undefined) {
              config.range_end = end;
            }

          const step = parseOptionalPositiveInt(formState.partitionRangeStep);
          if (step !== undefined) {
            config.range_step = step;
          }
        } else if (formState.partitionRangeKind === 'date') {
          // For date ranges, keep as string
          const start = formState.partitionRangeStart?.trim();
          if (start) {
            config.range_start = start;
          }

          const end = formState.partitionRangeEnd?.trim();
          if (end) {
            config.range_end = end;
          }

          const step = parseOptionalPositiveInt(formState.partitionRangeStep);
          if (step !== undefined) {
            config.range_step = step;
          }

          config.range_kind = 'date';
        }
      }

      const valueTemplate = formState.partitionValueTemplate?.trim();
      if (valueTemplate) {
        config.value_template = valueTemplate;
      }

      const extraTemplate = formState.partitionExtraTemplate?.trim();
      if (extraTemplate) {
        config.extra_template = extraTemplate;
      }
    }

    if (formState.partitionStrategy === 'endpoints') {
      const endpointsStr = formState.partitionEndpoints?.trim();
      if (endpointsStr) {
        let endpoints: string[] = [];
        // Try JSON first
        try {
          const parsed = JSON.parse(endpointsStr);
          if (Array.isArray(parsed)) {
            if (parsed.every(item => typeof item === 'string')) {
              endpoints = parsed.map(s => s.trim()).filter(s => s.length > 0);
            } else if (parsed.every(item => typeof item === 'object' && item)) {
              // Support array of objects with name/path (ignore params for now)
              endpoints = parsed
                .map(obj => {
                  const name = (obj as any).name?.trim();
                  const path = (obj as any).path?.trim();
                  if (!path) return null;
                  return name ? `${name}:${path}` : path;
                })
                .filter((v): v is string => !!v);
            }
          }
        } catch {
          // Not JSON �� fallback to splitting by newlines or commas
          endpoints = endpointsStr
            .split(/[,\n]/)
            .map(e => e.trim())
            .filter(e => e.length > 0);
        }

        if (endpoints.length > 0) {
          config.endpoints = endpoints;
        }
      }
    }

    return config;
  })();

  const trimmedStreamPath = formState.streamPath.trim();
  const endpointsConfigured = !!formState.partitionEndpoints?.trim();
  let effectiveStreamPath = trimmedStreamPath;

  if (!effectiveStreamPath && formState.partitionStrategy === 'endpoints' && endpointsConfigured) {
    effectiveStreamPath = '/';
  }

  if (effectiveStreamPath && !effectiveStreamPath.startsWith('/')) {
    effectiveStreamPath = `/${effectiveStreamPath}`;
  }

  return {
    version: formState.version,
    source: {
      type: 'rest',
      base_url: formState.baseUrl,
      // Auth intentionally excluded from persisted config (token supplied separately)
    },
    stream: {
      path: effectiveStreamPath,
      params: cleanParams,
      headers: cleanHeaders,
      pagination: (() => {
        const pagination: Record<string, any> = { type: formState.paginationType };
        if (formState.paginationType !== 'none') {
          const parsedSize = parseOptionalPositiveInt(formState.paginationPageSize);
          if (parsedSize !== undefined) {
            pagination.page_size = parsedSize;
          }
          const limitParam = formState.paginationLimitParam?.trim();
          if (limitParam) {
            pagination.limit_param = limitParam;
          }
          if (!formState.paginationStopOnEmptyResponse) { // simplified
            pagination.stop_on_empty_response = false;
          }
          const totalPagesPath = parsePathInput(formState.paginationTotalPagesPath);
          if (totalPagesPath) {
            (pagination as any).total_pages_path = totalPagesPath;
          }
          const totalPagesHeader = formState.paginationTotalPagesHeader?.trim();
          if (totalPagesHeader) {
            (pagination as any).total_pages_header = totalPagesHeader;
          }
          const totalRecordsPath = parsePathInput(formState.paginationTotalRecordsPath);
          if (totalRecordsPath) {
            (pagination as any).total_records_path = totalRecordsPath;
          }
          const totalRecordsHeader = formState.paginationTotalRecordsHeader?.trim();
          if (totalRecordsHeader) {
            (pagination as any).total_records_header = totalRecordsHeader;
          }
        }

        if (formState.paginationType === 'offset') {
          const offsetParam = formState.paginationOffsetParam?.trim();
          if (offsetParam) {
            pagination.offset_param = offsetParam;
          }
          const startOffset = parseOptionalNonNegativeInt(formState.paginationStartOffset);
          if (startOffset !== undefined) {
            pagination.start_offset = startOffset;
          }
        }

        if (formState.paginationType === 'page') {
          const pageParam = formState.paginationPageParam?.trim();
          if (pageParam) {
            pagination.page_param = pageParam;
          }
          const startPage = parseOptionalPositiveInt(formState.paginationStartPage);
          if (startPage !== undefined) {
            pagination.start_page = startPage;
          }
        }

        if (formState.paginationType === 'cursor') {
          const cursorParam = formState.paginationCursorParam?.trim();
          if (cursorParam) {
            pagination.cursor_param = cursorParam;
          }
          const cursorPath = parsePathInput(formState.paginationCursorPath);
          if (cursorPath) {
            pagination.cursor_path = cursorPath;
          }
          const nextUrlPath = parsePathInput(formState.paginationNextUrlPath);
          if (nextUrlPath) {
            pagination.next_url_path = nextUrlPath;
          }
          const cursorHeader = formState.paginationCursorHeader?.trim();
          if (cursorHeader) {
            pagination.cursor_header = cursorHeader;
          }
          const initialCursor = formState.paginationInitialCursor?.trim();
          if (initialCursor) {
            pagination.initial_cursor = initialCursor;
          }
        }

        return pagination;
      })(),
      incremental: {
        mode: formState.incrementalMode || null,
        cursor_param: formState.incrementalCursorParam || null,
        cursor_field: formState.incrementalCursorField || null,
      },
      infer_schema: formState.inferSchema,
      schema: formState.schema || null,
      record_selector: {
        field_path: fieldPathSegments,
        record_filter: recordFilter ? recordFilter : null,
        cast_to_schema_types: formState.castToSchemaTypes,
      },
      error_handler: errorHandler,
      ...(partitionConfig ? { partition: partitionConfig } : {}),
    },
  } as any; // backend ignores missing name
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

  // Convert headers to string values for form inputs - safely handle undefined headers
  const stringHeaders: Record<string, string> = {};
  if (config.stream.headers) {
    Object.entries(config.stream.headers).forEach(([key, value]) => {
      stringHeaders[key] = String(value);
    });
  }

  const recordSelector = config.stream.record_selector ?? {
    field_path: [],
    record_filter: null,
    cast_to_schema_types: false,
  };

  const upstreamErrorHandler = config.stream.error_handler as Partial<ErrorHandlerConfig> | undefined;
  const effectiveMaxRetries = upstreamErrorHandler?.max_retries ?? DEFAULT_ERROR_HANDLER.max_retries;
  const effectiveRetryStatuses = Array.isArray(upstreamErrorHandler?.retry_statuses)
    ? upstreamErrorHandler!.retry_statuses.map((status) => String(status))
    : [...DEFAULT_ERROR_HANDLER.retry_statuses];
  const upstreamBackoff = upstreamErrorHandler?.backoff ?? DEFAULT_ERROR_HANDLER.backoff;
  const effectiveBackoff = {
    initial_delay_seconds: upstreamBackoff?.initial_delay_seconds ?? DEFAULT_ERROR_HANDLER.backoff.initial_delay_seconds,
    max_delay_seconds: upstreamBackoff?.max_delay_seconds ?? DEFAULT_ERROR_HANDLER.backoff.max_delay_seconds,
    multiplier: upstreamBackoff?.multiplier ?? DEFAULT_ERROR_HANDLER.backoff.multiplier,
  };
  const effectiveRetryOnTimeout = upstreamErrorHandler?.retry_on_timeout ?? DEFAULT_ERROR_HANDLER.retry_on_timeout;
  const effectiveRetryOnConnectionErrors = upstreamErrorHandler?.retry_on_connection_errors ?? DEFAULT_ERROR_HANDLER.retry_on_connection_errors;

  // Get partition config exclusively from stream.partition
  const partitionConfig = config.stream.partition;

  // Default values for partition configuration
  let partitionStrategy: 'none' | 'pagination' | 'param_range' | 'endpoints' = partitionConfig?.strategy ?? 'none';
  let partitionParam = '';
  let partitionValues = '';
  let partitionRangeStart = '';
  let partitionRangeEnd = '';
  let partitionRangeStep = '';
  let partitionRangeKind: 'numeric' | 'date' = 'numeric';
  let partitionValueTemplate = '';
  let partitionExtraTemplate = '';
  let partitionEndpoints = '';

  // Extract partition config from stream.partition if available
  if (partitionConfig) {
    partitionStrategy = partitionConfig.strategy;

    if (partitionConfig.param) {
      partitionParam = String(partitionConfig.param);
    }

    if (partitionConfig.values) {
      partitionValues = String(partitionConfig.values);
    }

    if (partitionConfig.range_start !== undefined && partitionConfig.range_start !== null) {
      partitionRangeStart = String(partitionConfig.range_start);
    }

    if (partitionConfig.range_end !== undefined && partitionConfig.range_end !== null) {
      partitionRangeEnd = String(partitionConfig.range_end);
    }

    if (partitionConfig.range_step !== undefined && partitionConfig.range_step !== null) {
      partitionRangeStep = String(partitionConfig.range_step);
    }

    if (partitionConfig.range_kind === 'date') {
      partitionRangeKind = 'date';
    }

    if (partitionConfig.value_template) {
      partitionValueTemplate = String(partitionConfig.value_template);
    }

    if (partitionConfig.extra_template) {
      partitionExtraTemplate = String(partitionConfig.extra_template);
    }

    if (partitionConfig.endpoints && Array.isArray(partitionConfig.endpoints)) {
      partitionEndpoints = partitionConfig.endpoints.join(',');
    }
  }

  const rawStreamPath = (config.stream as any).path || '';
  const streamPath = partitionStrategy === 'endpoints' && rawStreamPath === '/' ? '' : rawStreamPath;

  return {
    version: config.version,
    baseUrl: config.source.base_url,
    authType: (config.source as any).auth?.type || 'none',
    authToken: '', // token never returned by API
    streamPath,
    params: stringParams,
    headers: stringHeaders,
    paginationType: config.stream.pagination?.type || 'none',
    paginationPageSize: config.stream.pagination?.page_size
      ? String(config.stream.pagination.page_size)
      : '',
    paginationLimitParam: config.stream.pagination?.limit_param || '',
    paginationOffsetParam: config.stream.pagination?.offset_param || '',
    paginationStartOffset:
      config.stream.pagination?.start_offset !== undefined &&
      config.stream.pagination?.start_offset !== null &&
      config.stream.pagination?.start_offset !== 0
        ? String(config.stream.pagination.start_offset)
        : '',
    paginationPageParam: config.stream.pagination?.page_param || '',
    paginationStartPage:
      config.stream.pagination?.start_page !== undefined &&
      config.stream.pagination?.start_page !== null &&
      config.stream.pagination?.start_page !== 1
        ? String(config.stream.pagination.start_page)
        : '',
    paginationCursorParam: config.stream.pagination?.cursor_param || '',
    paginationCursorPath:
      config.stream.pagination?.cursor_path && config.stream.pagination.cursor_path.length > 0
        ? config.stream.pagination.cursor_path.join('.')
        : '',
    paginationNextUrlPath:
      config.stream.pagination?.next_url_path && config.stream.pagination.next_url_path.length > 0
        ? config.stream.pagination.next_url_path.join('.')
        : '',
    paginationCursorHeader: config.stream.pagination?.cursor_header || '',
    paginationInitialCursor: config.stream.pagination?.initial_cursor || '',
    paginationStopOnEmptyResponse: (config.stream.pagination as any)?.stop_on_empty_response !== false,
    paginationTotalPagesPath:
      (config.stream.pagination as any)?.total_pages_path && (config.stream.pagination as any).total_pages_path.length > 0
        ? (config.stream.pagination as any).total_pages_path.join('.')
        : '',
    paginationTotalPagesHeader: (config.stream.pagination as any)?.total_pages_header || '',
    paginationTotalRecordsPath:
      (config.stream.pagination as any)?.total_records_path && (config.stream.pagination as any).total_records_path.length > 0
        ? (config.stream.pagination as any).total_records_path.join('.')
        : '',
    paginationTotalRecordsHeader: (config.stream.pagination as any)?.total_records_header || '',
    partitionStrategy,
    partitionParam,
    partitionValues,
    partitionRangeStart,
    partitionRangeEnd,
    partitionRangeStep,
    partitionRangeKind,
    partitionValueTemplate,
    partitionExtraTemplate,
    partitionEndpoints,
    incrementalMode: config.stream.incremental?.mode || '',
    incrementalCursorParam: config.stream.incremental?.cursor_param || '',
    incrementalCursorField: config.stream.incremental?.cursor_field || '',
    incrementalStatePath: '',
    incrementalStartValue: '',
    incrementalStateKey: '',
    incrementalMemoryEnabled: true,
    inferSchema: config.stream.infer_schema ?? true,
    schema: config.stream.schema || '',
    recordFieldPath: Array.isArray(recordSelector.field_path) ? recordSelector.field_path.map(String) : [],
    recordFilter: recordSelector.record_filter || '',
    castToSchemaTypes: Boolean(recordSelector.cast_to_schema_types),
    errorHandlerMaxRetries: String(effectiveMaxRetries),
    errorHandlerRetryStatuses: effectiveRetryStatuses,
    errorHandlerInitialDelaySeconds: String(effectiveBackoff.initial_delay_seconds),
    errorHandlerMaxDelaySeconds: String(effectiveBackoff.max_delay_seconds),
    errorHandlerBackoffMultiplier: String(effectiveBackoff.multiplier),
    errorHandlerRetryOnTimeout: effectiveRetryOnTimeout,
    errorHandlerRetryOnConnectionErrors: effectiveRetryOnConnectionErrors,
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

  const trimmedPath = formState.streamPath.trim();
  const endpointsConfigured = !!formState.partitionEndpoints?.trim();
  const requiresPath = formState.partitionStrategy !== 'endpoints' || !endpointsConfigured;

  if (requiresPath && !trimmedPath) {
    errors.push('Stream path is required');
  }

  if (trimmedPath && !trimmedPath.startsWith('/')) {
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
