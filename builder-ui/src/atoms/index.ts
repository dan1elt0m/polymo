import { atom } from "jotai";
import type { ConfigFormState, SampleState, StatusState } from "../types";
import { INITIAL_FORM_STATE } from "../lib/initial-data";
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

const defaultSampleState: SampleState = {
	data: [],
	dtypes: [],
	stream: "",
	limit: DEFAULT_SAMPLE_LIMIT,
	view: SAMPLE_VIEWS.TABLE,
	wrap: false,
	page: 1,
	pageSize: DEFAULT_PAGE_SIZE,
	loading: false,
};
export const sampleAtom = atom<SampleState>(defaultSampleState);

export const streamOptionsAtom = atom((get) => {
	const state = get(configFormStateAtom);
	const name = state.streamName.trim();
	return name ? [name] : [];
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
  const cfg = formStateToConfig(formState);
  // Build ordered object to preserve desired key ordering
  const ordered: any = {
    version: cfg.version,
    source: {
      type: cfg.source.type,
      base_url: cfg.source.base_url,
    },
    stream: {
      name: cfg.stream.name,
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
    },
  };
  if (!Object.keys(ordered.stream.params).length) delete ordered.stream.params;
  if (!ordered.stream.schema) ordered.stream.schema = null;
  // Auth optional
  if (cfg.source.auth) {
    ordered.source.auth = { ...cfg.source.auth };
  }
  return yaml.dump(ordered, { noRefs: true, lineWidth: 120, sortKeys: false, quotingType: "'" }).trimEnd();
});
