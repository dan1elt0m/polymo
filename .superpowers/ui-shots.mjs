// Drives the builder in system Chrome and saves the screenshot set used in
// the redesign report. Run: node .superpowers/ui-shots.mjs (backend on :8918).
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import path from "node:path";

const BASE = process.env.POLYMO_URL || "http://localhost:8918";
const OUT = path.resolve(".superpowers/ui-shots");
mkdirSync(OUT, { recursive: true });

const SIZES = [
	{ tag: "1440", width: 1440, height: 900 },
	{ tag: "1100", width: 1100, height: 800 },
];
const THEMES = ["light", "dark"];

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || `${process.env.HOME}/Library/Caches/ms-playwright/chromium_headless_shell-1217/chrome-headless-shell-mac-arm64/chrome-headless-shell`, headless: true });

for (const theme of THEMES) {
	for (const size of SIZES) {
		const context = await browser.newContext({
			viewport: { width: size.width, height: size.height },
			colorScheme: theme,
			deviceScaleFactor: 1,
		});
		const page = await context.newPage();
		const shot = (name) => page.screenshot({ path: path.join(OUT, `${name}-${theme}-${size.tag}.png`) });

		await page.goto(BASE, { waitUntil: "networkidle" });
		await shot("01-landing");

		await page.getByRole("heading", { name: "Start from scratch" }).click();
		await page.getByTestId("base-url-input").fill("https://jsonplaceholder.typicode.com");
		await page.getByTestId("stream-path-input").fill("/users");
		await page.getByTestId("stream-name-input").fill("users");
		await shot("02-builder-empty");

		// Authentication: API key with each secret source.
		await page.getByRole("radio", { name: "API key" }).click();
		await page.getByLabel("Preview only").check();
		await shot("03-auth-apikey-preview-only");
		await page.getByLabel("Secret scope").check();
		await page.waitForTimeout(400);
		await shot("04-auth-apikey-secret-scope");
		await page.getByLabel("UC credential").check();
		await page.waitForTimeout(400);
		await shot("05-auth-apikey-uc-credential");

		// Back to no auth so the real endpoint accepts the preview request.
		await page.getByRole("radio", { name: "None" }).click();
		await page.getByTestId("data-preview-button").click();
		await page.getByText(/Fetched \d+ sample records/).waitFor({ timeout: 60_000 });
		await page.waitForTimeout(300);
		await shot("06-preview-dataframe");

		// Advanced tier opened up.
		await page.getByRole("button", { name: /^Pagination/ }).click();
		await page.getByRole("button", { name: /^Error handling/ }).click();
		await page.getByTestId("query-params-toggle").click();
		await page.getByRole("button", { name: "Add" }).nth(1).click();
		await page.waitForTimeout(300);
		await shot("07-advanced-open");

		// Split: drag the handle left, collapse, expand, focus.
		const handle = page.getByTestId("split-handle");
		const box = await handle.boundingBox();
		await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
		await page.mouse.down();
		await page.mouse.move(box.x - 120, box.y + box.height / 2, { steps: 8 });
		await page.mouse.up();
		await page.waitForTimeout(300);
		await shot("08-split-dragged");

		await handle.hover();
		await page.getByTestId("split-collapse").click();
		await page.waitForTimeout(400);
		await shot("09-config-collapsed");
		await page.getByTestId("split-expand").click();
		await page.waitForTimeout(400);

		await page.getByTestId("focus-preview-toggle").click();
		await page.waitForTimeout(400);
		await shot("10-focus-preview");
		await page.getByTestId("focus-preview-toggle").click();
		await page.waitForTimeout(300);

		await page.getByRole("tab", { name: "Generated Code" }).click();
		await page.waitForTimeout(800);
		await shot("11-generated-code");

		await page.getByRole("tab", { name: "Deploy" }).click();
		await page.waitForTimeout(1200);
		await shot("12-deploy-stepper");

		await context.close();
	}
}

await browser.close();
console.log(`saved to ${OUT}`);
