import yaml from "js-yaml";
import type { BuilderState } from "../types";
import { formStateToConfig } from "./transform";

export function serializeStateToYaml(state: BuilderState): string {
	// state is expected to have a formState property; fall back if shape differs
	// @ts-ignore Runtime safeguard if BuilderState typing differs
	const formState = state.formState ?? state;
	const config = formStateToConfig(formState as any);
	try {
		return yaml.dump(config, { noRefs: true, lineWidth: 120, quotingType: '"' });
	} catch (error) {
		console.warn("Failed to serialize YAML", error);
		return "";
	}
}

export function parseYamlToState(source: string): unknown {
	if (!source.trim()) {
		return {};
	}
	return yaml.load(source);
}
