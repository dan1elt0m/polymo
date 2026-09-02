import { atom } from "jotai";
import { atomWithStorage, createJSONStorage } from "jotai/utils";
import type { ConfigFormState, SampleState, StatusState, SavedConnector, WorkingState } from "../types";
import { INITIAL_FORM_STATE } from "../lib/initial-data";
import { formStateToConfig } from "../lib/transform";
import {
	DEFAULT_PAGE_SIZE,
	DEFAULT_SAMPLE_LIMIT,
	SAMPLE_VIEWS,
} from "../lib/constants";

export const configFormStateAtom = atom<ConfigFormState>(INITIAL_FORM_STATE);
export const builderViewAtom = atom<"ui" | "code" | "deploy">("ui");
export const lastEditedAtom = atom<"ui">("ui");
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
	const formState = get(configFormStateAtom);
	const config = formStateToConfig(formState);
	return { config_dict: config };
});

export interface GeneratedCodeState {
	script: string;
	stream: string;
	error: string | null;
	loading: boolean;
}

export const DEFAULT_GENERATED_CODE_STATE: GeneratedCodeState = {
	script: "",
	stream: "",
	error: null,
	loading: false,
};

// Holds the generated PySpark script for the current form-state config dict.
// Refreshed (debounced) whenever configFormStateAtom changes; replaces the
// old client-side form-state -> YAML derivation.
export const generatedCodeAtom = atom<GeneratedCodeState>(DEFAULT_GENERATED_CODE_STATE);

export const bearerTokenAtom = atom<string>('');
export const readerOptionsAtom = atom<Record<string, string>>({});

// Databricks CLI profile shared between the Deploy tab and the
// secret-scope pickers in AuthenticationSection, so picking a profile once
// in the Deploy tab is enough to browse secret scopes/keys there too.
export const databricksProfileAtom = atom<string>('');

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

  // Legacy 0.x reader-option keys: the incremental ones now live in the
  // config itself (`stream.incremental.state_path` etc.), so a stale entry
  // from an older saved connector is dropped rather than forwarded.
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

  if (formState.authType === 'oauth2') {
    const secret = formState.authToken.trim();
    if (secret) {
      manualOptions['oauth_client_secret'] = secret;
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

// Snapshot of the in-progress editor session, kept separate from
// savedConnectors so an imported-but-unsaved (or just-edited) config
// survives a reload even before the periodic save-to-savedConnectors sync
// runs. Never holds formState.authToken — callers must strip it before
// writing (see App.tsx's working-state sync effect).
const workingStateStorage = typeof window !== 'undefined'
	? createJSONStorage<WorkingState | null>(() => localStorage)
	: undefined;

export const workingStateAtom = atomWithStorage<WorkingState | null>(
	'polymo.working_state.v1',
	null,
	workingStateStorage,
);
