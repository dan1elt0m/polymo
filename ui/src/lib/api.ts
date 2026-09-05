import type {
	GenerateResponse,
	SamplePayload,
	ValidationPayload,
	DatabricksProfilesResponse,
	DatabricksCatalogsResponse,
	DatabricksSchemasResponse,
	DatabricksSecretScopesResponse,
	DatabricksSecretKeysResponse,
	DatabricksServiceCredentialsResponse,
	DatabricksBootstrapResponse,
	DatabricksCommandResponse,
} from "../types";

// Thrown for any non-2xx response. Carries the HTTP status so callers can
// special-case e.g. 501 ("databricks CLI not found") without string-matching
// the message.
export class ApiError extends Error {
	status: number;
	constructor(message: string, status: number) {
		super(message);
		this.name = "ApiError";
		this.status = status;
	}
}

async function errorDetail(response: Response): Promise<string> {
	const payload = (await response.json().catch(() => ({}))) as {
		detail?: string;
		message?: string;
	};
	return payload?.detail ?? payload?.message ?? `Request failed (${response.status})`;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
	const response = await fetch(path, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	});

	if (!response.ok) {
		throw new ApiError(await errorDetail(response), response.status);
	}
	return (await response.json()) as T;
}

async function getJson<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
	const entries = Object.entries(params ?? {}).filter(
		(entry): entry is [string, string] => typeof entry[1] === "string" && entry[1].length > 0,
	);
	const query = entries.map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`).join("&");
	const response = await fetch(query ? `${path}?${query}` : path);

	if (!response.ok) {
		throw new ApiError(await errorDetail(response), response.status);
	}
	return (await response.json()) as T;
}

export function validateConfigRequest(body: unknown): Promise<ValidationPayload> {
	return postJson<ValidationPayload>("/api/validate", body);
}

export function sampleRequest(body: unknown): Promise<SamplePayload> {
	return postJson<SamplePayload>("/api/sample", body);
}

export function generateScript(configDict: unknown): Promise<GenerateResponse> {
	return postJson<GenerateResponse>("/api/generate", { config_dict: configDict });
}

export function listDatabricksProfiles(): Promise<DatabricksProfilesResponse> {
	return getJson<DatabricksProfilesResponse>("/api/databricks/profiles");
}

export function listDatabricksCatalogs(profile?: string): Promise<DatabricksCatalogsResponse> {
	return getJson<DatabricksCatalogsResponse>("/api/databricks/catalogs", { profile });
}

export function listDatabricksSchemas(
	catalog: string,
	profile?: string,
): Promise<DatabricksSchemasResponse> {
	return getJson<DatabricksSchemasResponse>("/api/databricks/schemas", { catalog, profile });
}

export function listDatabricksSecretScopes(profile?: string): Promise<DatabricksSecretScopesResponse> {
	return getJson<DatabricksSecretScopesResponse>("/api/databricks/secret-scopes", { profile });
}

export function listDatabricksSecretKeys(
	scope: string,
	profile?: string,
): Promise<DatabricksSecretKeysResponse> {
	return getJson<DatabricksSecretKeysResponse>("/api/databricks/secret-keys", { scope, profile });
}

export function listDatabricksServiceCredentials(
	profile?: string,
): Promise<DatabricksServiceCredentialsResponse> {
	return getJson<DatabricksServiceCredentialsResponse>("/api/databricks/service-credentials", {
		profile,
	});
}

export interface BootstrapDatabricksProjectBody {
	config_dict: unknown;
	project_dir: string;
	project_name: string;
	catalog: string;
	schema: string;
	overwrite?: boolean;
}

export function bootstrapDatabricksProject(
	body: BootstrapDatabricksProjectBody,
): Promise<DatabricksBootstrapResponse> {
	return postJson<DatabricksBootstrapResponse>("/api/databricks/bootstrap", body);
}

export interface DatabricksCommandBody {
	project_path: string;
	profile?: string;
	target?: string;
}

export function deployDatabricksBundle(body: DatabricksCommandBody): Promise<DatabricksCommandResponse> {
	return postJson<DatabricksCommandResponse>("/api/databricks/deploy", body);
}

export function runDatabricksPipeline(body: DatabricksCommandBody): Promise<DatabricksCommandResponse> {
	return postJson<DatabricksCommandResponse>("/api/databricks/run", body);
}
