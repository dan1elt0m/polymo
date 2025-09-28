import type { SamplePayload, ValidationPayload } from "../types";

async function postJson<T>(path: string, body: unknown): Promise<T> {
	const response = await fetch(path, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	});

	const payload = (await response.json().catch(() => ({}))) as T & {
		detail?: string;
		message?: string;
	};
	if (!response.ok) {
		const detail = payload?.detail ?? payload?.message;
		throw new Error(detail ?? `${path} failed (${response.status})`);
	}
	return payload as T;
}

export function validateConfigRequest(body: unknown): Promise<ValidationPayload> {
	return postJson<ValidationPayload>("/api/validate", body);
}

export function sampleRequest(body: unknown): Promise<SamplePayload> {
	return postJson<SamplePayload>("/api/sample", body);
}
