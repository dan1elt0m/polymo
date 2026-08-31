// Shared filename helpers for client-side downloads (generated script, saved config, …).

export const slugifyStreamName = (value: string): string => {
	const slug = value
		.toLowerCase()
		.trim()
		.replace(/[^a-z0-9]+/g, "_")
		.replace(/^_+|_+$/g, "");
	return slug || "connector";
};

export const slugifyName = (value: string): string => {
	return (
		value
			.toLowerCase()
			.trim()
			.replace(/[^a-z0-9]+/g, "-")
			.replace(/^-+|-+$/g, "") || "connector"
	);
};

export const CONFIG_FILE_EXTENSION = ".polymo.json";

export const configFileName = (streamName: string): string =>
	`${slugifyStreamName(streamName)}${CONFIG_FILE_EXTENSION}`;
