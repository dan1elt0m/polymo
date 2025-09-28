export function collectColumns(records: Array<Record<string, unknown>>): string[] {
	const columns = new Set<string>();
	for (const row of records) {
		if (row && typeof row === "object") {
			for (const key of Object.keys(row)) {
				columns.add(key);
			}
		}
	}
	if (!columns.size) {
		columns.add("value");
	}
	return Array.from(columns);
}

export function formatCell(value: unknown): string {
	if (value == null) {
		return "";
	}
	if (typeof value === "object") {
		try {
			return JSON.stringify(value);
		} catch (error) {
			console.warn("Failed to stringify table cell", error);
			return String(value);
		}
	}
	return String(value);
}

export function truncate(value: string, maxLength: number): string {
	if (value.length <= maxLength) {
		return value;
	}
	return `${value.slice(0, maxLength)}…`;
}
