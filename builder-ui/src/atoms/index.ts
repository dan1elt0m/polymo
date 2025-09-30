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

export const streamOptionsAtom = atom((get) => {
	const state = get(configFormStateAtom);
	const path = state.streamPath.trim();
	if (!path) return [] as string[];
	const derived = (path.startsWith('/') ? path.slice(1) : path).replace(/\/+/, '_') || 'stream';
	return [derived];
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

export const runtimeOptionsAtom = atom((get) => {
  const formState = get(configFormStateAtom);
  const manualOptions = { ...get(readerOptionsAtom) };

  // Remove special keys managed by the incremental form fields
  for (const key of INCREMENTAL_OPTION_KEYS) {
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
