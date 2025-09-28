import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
	testDir: "builder-ui/tests",
	retries: process.env.CI ? 2 : 0,
	reporter: [["list"], ["html", { open: "never" }]],
	use: {
		trace: "on-first-retry",
		baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8000",
	},
	projects: [
		{
			name: "chromium",
			use: { ...devices["Desktop Chrome"] },
		},
		{
			name: "firefox",
			use: { ...devices["Desktop Firefox"] },
		},
		{
			name: "webkit",
			use: { ...devices["Desktop Safari"] },
		},
	],
});
