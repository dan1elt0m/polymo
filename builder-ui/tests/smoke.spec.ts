import { test, expect } from "@playwright/test";

test.describe("Connector Builder", () => {
	test("renders builder shell", async ({ page }) => {
		await page.goto("/");
		await expect(page.getByRole("heading", { name: "Connector Builder" })).toBeVisible();
		await expect(page.getByRole("button", { name: "Preview" })).toBeVisible();
	});
});
