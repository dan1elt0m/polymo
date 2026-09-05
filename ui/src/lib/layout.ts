// Persistence for the split layout (config pane ↔ preview pane).
// Stored under a versioned key so a future shape change can simply bump it.

export const LAYOUT_STORAGE_KEY = "polymo.layout.v1";

export interface LayoutState {
	/** Fraction of the available width given to the config pane (0..1). */
	ratio: number;
	/** Config pane collapsed to a slim rail. */
	collapsed: boolean;
}

export const DEFAULT_LAYOUT: LayoutState = { ratio: 0.46, collapsed: false };
export const MIN_RATIO = 0.25;
export const MAX_RATIO = 0.75;

export const clampRatio = (value: number): number => {
	if (!Number.isFinite(value)) return DEFAULT_LAYOUT.ratio;
	return Math.min(MAX_RATIO, Math.max(MIN_RATIO, value));
};

export function loadLayout(): LayoutState {
	if (typeof window === "undefined") return DEFAULT_LAYOUT;
	try {
		const raw = window.localStorage.getItem(LAYOUT_STORAGE_KEY);
		if (!raw) return DEFAULT_LAYOUT;
		const parsed = JSON.parse(raw) as Partial<LayoutState> | null;
		if (!parsed || typeof parsed !== "object") return DEFAULT_LAYOUT;
		return {
			ratio: clampRatio(typeof parsed.ratio === "number" ? parsed.ratio : DEFAULT_LAYOUT.ratio),
			collapsed: parsed.collapsed === true,
		};
	} catch {
		return DEFAULT_LAYOUT;
	}
}

export function saveLayout(state: LayoutState): void {
	if (typeof window === "undefined") return;
	try {
		window.localStorage.setItem(
			LAYOUT_STORAGE_KEY,
			JSON.stringify({ ratio: clampRatio(state.ratio), collapsed: state.collapsed === true }),
		);
	} catch {
		/* storage unavailable (private mode, quota) — layout just won't persist */
	}
}
