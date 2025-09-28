import yaml from "js-yaml";
import type { BuilderState } from "../types";
import { stateToConfigDict } from "./transform";

export function serializeStateToYaml(state: BuilderState): string {
	const config = stateToConfigDict(state);
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
