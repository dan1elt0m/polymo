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
		});
	}),
];
