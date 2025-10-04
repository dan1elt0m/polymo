import { atom } from "jotai";
import { atomWithStorage, createJSONStorage } from "jotai/utils";
import type { ConfigFormState, SampleState, StatusState, SavedConnector } from "../types";
import { DEFAULT_ERROR_HANDLER, INITIAL_FORM_STATE } from "../lib/initial-data";
import { formStateToConfig } from "../lib/transform";
import {
	DEFAULT_PAGE_SIZE,
	DEFAULT_SAMPLE_LIMIT,
	SAMPLE_VIEWS,
} from "../lib/constants";
import yaml from "js-yaml";

export const configFormStateAtom = atom<ConfigFormState>(INITIAL_FORM_STATE);
export const builderViewAtom = atom<"ui" | "yaml">("ui");
export const yamlTextAtom = atom<string>("");
export const yamlErrorAtom = atom<string | null>(null);
export const lastEditedAtom = atom<"ui" | "yaml">("ui");
export const statusAtom = atom<StatusState>({ tone: "info", message: "Ready to configure" });
export const isValidatingAtom = atom(false);
export const isSavingAtom = atom(false);

export const DEFAULT_SAMPLE_STATE: SampleState = {
	data: [],
	dtypes: [],
	stream: "",
	limit: DEFAULT_SAMPLE_LIMIT,
	view: SAMPLE_VIEWS.TABLE,
	wrap: false,
	page: 1,
	pageSize: DEFAULT_PAGE_SIZE,
	loading: false,
	rawPages: [],
	restError: null,
};
export const sampleAtom = atom<SampleState>(DEFAULT_SAMPLE_STATE);

const deriveEndpointOptions = (raw: string): string[] => {
	const text = raw.trim();
	if (!text) return [];

	const labels: string[] = [];
	const seen = new Set<string>();
	const addLabel = (label?: string, fallback?: string) => {
		const candidate = (label ?? fallback ?? '').trim();
		if (!candidate) return;
		const key = candidate.toLowerCase();
		if (seen.has(key)) return;
		seen.add(key);
		labels.push(candidate);
	};

	const handleStringEntry = (entry: string) => {
		const trimmed = entry.trim();
		if (!trimmed) return;
		if (trimmed.includes(':')) {
			const idx = trimmed.indexOf(':');
			const name = trimmed.slice(0, idx);
			const path = trimmed.slice(idx + 1);
			addLabel(name, path);
			return;
		}
		addLabel(trimmed);
	};

	try {
		const parsed = JSON.parse(text);
		if (Array.isArray(parsed)) {
			for (const entry of parsed) {
				if (typeof entry === 'string') {
					handleStringEntry(entry);
					continue;
				}
				if (entry && typeof entry === 'object') {
					const name = typeof (entry as any).name === 'string' ? (entry as any).name : undefined;
					const path = typeof (entry as any).path === 'string' ? (entry as any).path : undefined;
					if (name || path) {
						addLabel(name, path);
					}
				}
			}
			return labels;
		}
	} catch {
		// Fallback to delimiter parsing.
	}

	for (const chunk of text.split(/[\n,]+/)) {
		handleStringEntry(chunk);
	}

	return labels;
};

const deriveStreamOptionFromPath = (path: string): string => {
	const trimmed = path.trim();
	if (!trimmed) return '';
	const normalised = trimmed.startsWith('/') ? trimmed.slice(1) : trimmed;
	const replaced = normalised.replace(/\/+/, '_');
	return replaced || 'stream';
};

export const streamOptionsAtom = atom((get) => {
	const state = get(configFormStateAtom);
	if (state.partitionStrategy === 'endpoints') {
		const options = deriveEndpointOptions(state.partitionEndpoints || '');
		if (options.length) {
			return options;
		}
	}

	const derived = deriveStreamOptionFromPath(state.streamPath);
	return derived ? [derived] : [];
});

export const configPayloadAtom = atom((get) => {
	const view = get(builderViewAtom);
	if (view === "yaml") {
		return { config: get(yamlTextAtom) };
	}
	const formState = get(configFormStateAtom);
	const config = formStateToConfig(formState);
	return { config_dict: config };
});

// Derived atom to convert form state to YAML
export const formStateToYamlAtom = atom((get) => {
  const formState = get(configFormStateAtom);
  const cfg = formStateToConfig(formState) as any;
  const ordered: any = {
    version: cfg.version,
    source: {
      type: cfg.source.type,
      base_url: cfg.source.base_url,
    },
    stream: {
      // name omitted intentionally
      path: cfg.stream.path,
      infer_schema: cfg.stream.infer_schema,
      schema: cfg.stream.schema || null,
      pagination: { type: cfg.stream.pagination.type },
      params: Object.keys(cfg.stream.params || {}).length ? cfg.stream.params : {},
      incremental: {
        mode: cfg.stream.incremental.mode,
        cursor_param: cfg.stream.incremental.cursor_param,
        cursor_field: cfg.stream.incremental.cursor_field,
      },
      record_selector: {
        field_path: cfg.stream.record_selector?.field_path || [],
        record_filter: cfg.stream.record_selector?.record_filter ?? null,
        cast_to_schema_types: !!cfg.stream.record_selector?.cast_to_schema_types,
      },
      error_handler: {
        max_retries: cfg.stream.error_handler?.max_retries ?? DEFAULT_ERROR_HANDLER.max_retries,
        retry_statuses: Array.isArray(cfg.stream.error_handler?.retry_statuses)
          ? cfg.stream.error_handler.retry_statuses
          : [...DEFAULT_ERROR_HANDLER.retry_statuses],
        retry_on_timeout: cfg.stream.error_handler?.retry_on_timeout ?? DEFAULT_ERROR_HANDLER.retry_on_timeout,
        retry_on_connection_errors:
          cfg.stream.error_handler?.retry_on_connection_errors ?? DEFAULT_ERROR_HANDLER.retry_on_connection_errors,
        backoff: {
          initial_delay_seconds:
            cfg.stream.error_handler?.backoff?.initial_delay_seconds ?? DEFAULT_ERROR_HANDLER.backoff.initial_delay_seconds,
          max_delay_seconds:
            cfg.stream.error_handler?.backoff?.max_delay_seconds ?? DEFAULT_ERROR_HANDLER.backoff.max_delay_seconds,
          multiplier:
            cfg.stream.error_handler?.backoff?.multiplier ?? DEFAULT_ERROR_HANDLER.backoff.multiplier,
        },
      },
    },
  };
  if (!Object.keys(ordered.stream.params).length) delete ordered.stream.params;
  if (!ordered.stream.schema) ordered.stream.schema = null;
  if (
    ordered.stream.record_selector &&
    !ordered.stream.record_selector.field_path.length &&
    ordered.stream.record_selector.record_filter == null &&
    !ordered.stream.record_selector.cast_to_schema_types
  ) {
    delete ordered.stream.record_selector;
  }
  const partition = (cfg.stream as any).partition;
  if (partition && partition.strategy && partition.strategy !== 'none') {
    const partitionBlock: Record<string, any> = { strategy: partition.strategy };

    if (partition.param) partitionBlock.param = partition.param;
    if (partition.values) partitionBlock.values = partition.values;

    if (partition.range_start !== undefined && partition.range_start !== null) {
      partitionBlock.range_start = partition.range_start;
    }
    if (partition.range_end !== undefined && partition.range_end !== null) {
      partitionBlock.range_end = partition.range_end;
    }
    if (partition.range_step !== undefined && partition.range_step !== null) {
      partitionBlock.range_step = partition.range_step;
    }
    if (partition.range_kind) partitionBlock.range_kind = partition.range_kind;

    if (partition.value_template) partitionBlock.value_template = partition.value_template;
    if (partition.extra_template) partitionBlock.extra_template = partition.extra_template;

    if (Array.isArray(partition.endpoints) && partition.endpoints.length) {
      partitionBlock.endpoints = [...partition.endpoints];
    }

    ordered.stream.partition = partitionBlock;
  }
  if (cfg.source.auth) {
    ordered.source.auth = { ...cfg.source.auth };
  }
  return yaml.dump(ordered, { noRefs: true, lineWidth: 120, sortKeys: false, quotingType: "'" }).trimEnd();
});


export const bearerTokenAtom = atom<string>('');
export const readerOptionsAtom = atom<Record<string, string>>({});

const INCREMENTAL_OPTION_KEYS = new Set([
  'incremental_state_path',
  'incremental_start_value',
  'incremental_state_key',
  'incremental_memory_state',
]);

const PARTITION_OPTION_KEYS = new Set([
  'partition_strategy',
  'partition_param',
  'partition_values',
  'partition_range_start',
  'partition_range_end',
  'partition_range_step',
  'partition_range_kind',
  'partition_value_template',
  'partition_extra_template',
  'partition_endpoints',
]);

export const runtimeOptionsAtom = atom((get) => {
  const formState = get(configFormStateAtom);
  const manualOptions = { ...get(readerOptionsAtom) };

  // Remove special keys managed by the incremental form fields
  for (const key of INCREMENTAL_OPTION_KEYS) {
    if (key in manualOptions) {
      delete manualOptions[key];
    }
  }

  for (const key of PARTITION_OPTION_KEYS) {
    if (key in manualOptions) {
      delete manualOptions[key];
    }
  }

  const statePath = formState.incrementalStatePath.trim();
  if (statePath) {
    manualOptions['incremental_state_path'] = statePath;
  }

  const startValue = formState.incrementalStartValue.trim();
  if (startValue) {
    manualOptions['incremental_start_value'] = startValue;
  }

  const stateKey = formState.incrementalStateKey.trim();
  if (stateKey) {
    manualOptions['incremental_state_key'] = stateKey;
  }

  if (!formState.incrementalMemoryEnabled) {
    manualOptions['incremental_memory_state'] = 'false';
  }

  // Add API key option directly so users don't have to manually add it as a Spark reader option.
  if (formState.authType === 'api_key') {
    const paramName = (formState.authApiKeyParamName || 'api_key').trim();
    const token = formState.authToken.trim();
    if (paramName && token) {
      manualOptions[paramName] = token;
    }
  }

  const partitionStrategy = formState.partitionStrategy || 'none';
  const strategy = partitionStrategy.trim() as typeof formState.partitionStrategy;
  if (strategy && strategy !== 'none') {
    manualOptions['partition_strategy'] = strategy;

    if (strategy === 'pagination') {
      // no additional options required; pagination hints come from YAML.
    } else if (strategy === 'param_range') {
      const paramName = formState.partitionParam?.trim();
      if (paramName) {
        manualOptions['partition_param'] = paramName;
      }

      const rawValues = formState.partitionValues?.trim();
      if (rawValues) {
        manualOptions['partition_values'] = rawValues;
      } else {
        const rangeStart = formState.partitionRangeStart?.trim();
        const rangeEnd = formState.partitionRangeEnd?.trim();
        if (rangeStart && rangeEnd) {
          manualOptions['partition_range_start'] = rangeStart;
          manualOptions['partition_range_end'] = rangeEnd;
          const rangeKind = formState.partitionRangeKind?.trim();
          if (rangeKind) {
            manualOptions['partition_range_kind'] = rangeKind;
          }
          const rangeStep = formState.partitionRangeStep?.trim();
          if (rangeStep) {
            manualOptions['partition_range_step'] = rangeStep;
          }
        }
      }

      const template = formState.partitionValueTemplate?.trim();
      if (template) {
        manualOptions['partition_value_template'] = template;
      }

      const extraTemplate = formState.partitionExtraTemplate?.trim();
      if (extraTemplate) {
        manualOptions['partition_extra_template'] = extraTemplate;
      }
    } else if (strategy === 'endpoints') {
      const endpoints = formState.partitionEndpoints?.trim();
      if (endpoints) {
        manualOptions['partition_endpoints'] = endpoints;
      }
    }
  }

  return manualOptions;
});

const savedConnectorsStorage = typeof window !== 'undefined'
	? createJSONStorage<SavedConnector[]>(() => localStorage)
	: undefined;

export const savedConnectorsAtom = atomWithStorage<SavedConnector[]>(
	'polymo.saved_connectors.v1',
	[],
	savedConnectorsStorage,
);

const activeConnectorStorage = typeof window !== 'undefined'
	? createJSONStorage<string | null>(() => localStorage)
	: undefined;

export const activeConnectorIdAtom = atomWithStorage<string | null>(
	'polymo.active_connector_id.v1',
	null,
	activeConnectorStorage,
);
