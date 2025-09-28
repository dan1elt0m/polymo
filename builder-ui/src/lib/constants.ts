export const MAX_SAMPLE_ROWS = 1000;
export const DEFAULT_SAMPLE_LIMIT = 100;
export const DEFAULT_PAGE_SIZE = 25;
export const PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const;
export const SAMPLE_VIEWS = {
	TABLE: "table" as const,
	JSON: "json" as const,
	RAW: "raw" as const,
};
