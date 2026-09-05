import { test, expect } from "@playwright/test";

test.describe("Polymo", () => {
	test("renders the shell", async ({ page }) => {
		await page.goto("/");
		await expect(page.getByRole("heading", { name: "Polymo" })).toBeVisible();
		await expect(page.getByRole("button", { name: "Preview" })).toBeVisible();
	});
});
