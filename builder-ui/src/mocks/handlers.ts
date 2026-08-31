import { http, HttpResponse } from "msw";

export const handlers = [
	http.post("/api/validate", async ({ request }) => {
		try {
			await request.json();
			return HttpResponse.json({ valid: true, streams: [], config: null });
		} catch (_error) {
			return HttpResponse.json({ valid: false, message: "Malformed payload" }, { status: 400 });
		}
	}),
	http.post("/api/sample", async ({ request }) => {
		await request.json();
		return HttpResponse.json({
			stream: "orders",
			records: [
				{ id: 1, name: "Example", status: "ok" },
				{ id: 2, name: "Sample", status: "ok" },
			],
		dtypes: [
			{ column: "id", type: "BIGINT" },
			{ column: "name", type: "STRING" },
			{ column: "status", type: "STRING" },
		],
		raw_pages: [
			{
				page: 1,
				url: "https://example.com/api/orders?page=1",
				status_code: 200,
				records: [
					{ id: 1, name: "Example", status: "ok" },
					{ id: 2, name: "Sample", status: "ok" },
				],
				headers: {},
				payload: {
					data: [
						{ id: 1, name: "Example", status: "ok" },
						{ id: 2, name: "Sample", status: "ok" },
					],
				},
			},
		],
		rest_error: null,
		});
	}),
	http.get("/api/databricks/profiles", () => {
		return HttpResponse.json({ profiles: ["DEFAULT", "staging"] });
	}),
	http.get("/api/databricks/catalogs", () => {
		return HttpResponse.json({ catalogs: ["main", "samples"] });
	}),
	http.get("/api/databricks/schemas", () => {
		return HttpResponse.json({ schemas: ["default", "bronze"] });
	}),
	http.get("/api/databricks/secret-scopes", () => {
		return HttpResponse.json({ secret_scopes: ["polymo"] });
	}),
	http.get("/api/databricks/secret-keys", () => {
		return HttpResponse.json({ secret_keys: ["api-token"] });
	}),
	http.post("/api/databricks/bootstrap", async ({ request }) => {
		const body = (await request.json()) as { project_dir?: string; project_name?: string };
		const projectPath = `${body?.project_dir ?? "~/polymo-projects"}/${body?.project_name ?? "connector"}`;
		return HttpResponse.json({
			project_path: projectPath,
			files: ["databricks.yml", ".polymo-bundle.json", "src/connector/pipeline.py"],
		});
	}),
	http.post("/api/databricks/deploy", () => {
		return HttpResponse.json({ ok: true, output: "Deployment complete!" });
	}),
	http.post("/api/databricks/run", () => {
		return HttpResponse.json({ ok: true, output: "Run started." });
	}),
];
