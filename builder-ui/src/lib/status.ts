import type { BuilderState, StatusState } from "../types";

export function defaultStatusForState(state: BuilderState): StatusState {
	const hasNamedStream = state.stream.name.trim().length > 0;
	if (hasNamedStream) {
		return {
			tone: "info",
			message: "Click Preview to see sample data from your configured stream.",
		};
	}
	return {
		tone: "warn",
		message: "Add a stream name to get started.",
	};
}
