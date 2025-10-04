import { expect, Locator, Page, test } from "@playwright/test";
import { readFileSync } from "fs";
import { resolve } from "path";

const EXAMPLE_YAML = readFileSync(
  resolve(process.cwd(), "src/polymo/builder/static/examples/jsonplaceholder.yml"),
  "utf8",
);

const SAMPLE_RECORDS = [
  {
    id: 1,
    userId: 1,
    title: "Leanne Graham",
    body: "Keep it human with gentle tooling demos.",
  },
  {
    id: 2,
    userId: 1,
    title: "Ervin Howell",
    body: "Playwright scripts can feel alive when paced well.",
  },
  {
    id: 3,
    userId: 2,
    title: "Patricia Lebsack",
    body: "Raw views help audiences trust the data flow.",
  },
  {
    id: 4,
    userId: 3,
    title: "John Doe",
    body: "This is a sample post for testing purposes.",
  },
  {
    id: 5,
    userId: 4,
    title: "Foo Bar",
    body: "Hope you find this example useful!",
  },
];

const SAMPLE_RESPONSE = {
  stream: "posts",
  records: SAMPLE_RECORDS,
  dtypes: [
    { column: "id", type: "BIGINT" },
    { column: "userId", type: "BIGINT" },
    { column: "title", type: "STRING" },
    { column: "body", type: "STRING" },
  ],
  raw_pages: [
    {
      page: 1,
      url: "https://jsonplaceholder.typicode.com/posts?_limit=5",
      status_code: 200,
      headers: {
        "content-type": "application/json; charset=utf-8",
      },
      records: SAMPLE_RECORDS,
      payload: SAMPLE_RECORDS,
    },
  ],
  rest_error: null,
};

test.describe("JSON Placeholder builder demo", () => {
  test("walkthrough with human-like pacing", async ({ page }) => {
    await setupDemoRoutes(page);
    await page.goto("/");
    await installHighlightEffects(page);

    await expect(page.getByRole("heading", { name: "Polymo Connector Builder" })).toBeVisible();
    await idle(page, 260, 420);

    const exampleToggle = page.getByTestId("landing-example-toggle");
    await humanClick(page, exampleToggle);

    const jsonPlaceholderOption = page.getByTestId("landing-example-json-placeholder");
    await humanClick(page, jsonPlaceholderOption);

    const baseUrlInput = page.getByTestId("base-url-input");
    await expect(baseUrlInput).toBeVisible();
    await expect(baseUrlInput).toHaveValue("https://jsonplaceholder.typicode.com");

    await idle(page, 320, 520);

    const paramsToggle = page.getByTestId("query-params-toggle");
    await humanClick(page, paramsToggle);
    await expect(page.getByTestId("param-row-limit")).toBeVisible();

    const limitValueInput = page.getByTestId("param-value-input-limit");
    await expect(limitValueInput).toHaveValue("20");
    await humanFill(page, limitValueInput, "5");

    await idle(page, 240, 400);

    const previewButton = page.getByTestId("data-preview-button");
    await humanClick(page, previewButton);

    await expect(page.getByText(/Fetched 3 sample records/i)).toBeVisible({ timeout: 5000 });
    const dataframeTab = page.getByTestId("view-tab-dataframe");
    await humanClick(page, dataframeTab);
    await expect(page.getByRole("row", { name: /Leanne Graham/ })).toBeVisible();

    const rawTab = page.getByTestId("view-tab-raw");
    await humanClick(page, rawTab);
    await expect(page.getByText(/jsonplaceholder\.typicode\.com\/posts\?_limit=5/)).toBeVisible();

    await humanClick(page, dataframeTab);

    const exportButton = page.getByTestId("open-export-modal");
    await humanClick(page, exportButton);

    const exportFileInput = page.getByTestId("export-file-name-input");
    await humanFill(page, exportFileInput, "jsonplaceholder-demo.yml");

    const downloadPromise = page.waitForEvent("download");
    const confirmExport = page.getByTestId("confirm-export");
    await humanClick(page, confirmExport);

    const download = await downloadPromise;
    const suggested = await download.suggestedFilename();
    expect(suggested).toMatch(/jsonplaceholder-demo\.yml$/);
    await download.delete();

    await expect(exportFileInput).not.toBeVisible();

    const connectorsButton = page.getByTestId("open-connector-library");
    await humanClick(page, connectorsButton);
    await expect(page.getByTestId("landing-example-toggle")).toBeVisible();

    // small pause so recordings capture landing state cleanly
    await idle(page, 260, 420);
  });
});

async function setupDemoRoutes(page: Page): Promise<void> {
  await page.route("**/api/meta", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ version: "demo" }),
    });
  });

  await page.route("**/static/examples/jsonplaceholder.yml", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/yaml",
      body: EXAMPLE_YAML,
    });
  });

  await page.route("**/api/validate", async (route) => {
    await idle(page, 120, 220);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ valid: true, config: null }),
    });
  });

  await page.route("**/api/sample", async (route) => {
    await idle(page, 160, 260);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SAMPLE_RESPONSE),
    });
  });
}

async function installHighlightEffects(page: Page): Promise<void> {
  await page.addStyleTag({
    content: `
      body.demo-highlight { cursor: none; }
      body.demo-highlight .demo-cursor {
        position: fixed;
        top: 0;
        left: 0;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        border: 2px solid rgba(37, 99, 235, 0.8);
        background: rgba(37, 99, 235, 0.12);
        box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.14);
        pointer-events: none;
        transform: translate3d(-999px, -999px, 0);
        transition: transform 120ms ease-out, opacity 200ms ease-out;
        opacity: 0;
        z-index: 9999;
      }
      body.demo-highlight .demo-cursor.active {
        transform: scale(0.9) translate3d(var(--cursor-x, 0), var(--cursor-y, 0), 0);
      }
      body.demo-highlight .demo-click-ripple {
        position: fixed;
        width: 12px;
        height: 12px;
        border-radius: 999px;
        border: 2px solid rgba(37, 99, 235, 0.55);
        pointer-events: none;
        opacity: 0.75;
        transform: translate(-50%, -50%);
        animation: demo-ripple 420ms ease-out forwards;
        z-index: 9998;
      }
      @keyframes demo-ripple {
        0% { transform: translate(-50%, -50%) scale(0.2); opacity: 0.75; }
        80% { opacity: 0.2; }
        100% { transform: translate(-50%, -50%) scale(2.4); opacity: 0; }
      }
      body.demo-highlight .demo-focus-ring {
        outline: none !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.48), 0 0 0 6px rgba(37, 99, 235, 0.18) !important;
        transition: box-shadow 140ms ease-out;
      }
    `,
  });

  await page.evaluate(() => {
    if (document.getElementById("demo-cursor")) {
      return;
    }

    const cursor = document.createElement("div");
    cursor.id = "demo-cursor";
    cursor.className = "demo-cursor";
    document.body.classList.add("demo-highlight");
    document.body.appendChild(cursor);

    const updateCursor = (event: MouseEvent) => {
      cursor.style.opacity = "1";
      cursor.style.setProperty("--cursor-x", `${event.clientX - 10}px`);
      cursor.style.setProperty("--cursor-y", `${event.clientY - 10}px`);
      cursor.style.transform = `translate3d(${event.clientX - 10}px, ${event.clientY - 10}px, 0)`;
    };

    document.addEventListener("mousemove", updateCursor, { passive: true });
    document.addEventListener("mousedown", (event) => {
      cursor.classList.add("active");
      cursor.style.transform = `translate3d(${event.clientX - 12}px, ${event.clientY - 12}px, 0)`;
      const ripple = document.createElement("div");
      ripple.className = "demo-click-ripple";
      ripple.style.left = `${event.clientX}px`;
      ripple.style.top = `${event.clientY}px`;
      document.body.appendChild(ripple);
      window.setTimeout(() => ripple.remove(), 420);
    });
    document.addEventListener("mouseup", () => {
      cursor.classList.remove("active");
    });

    document.addEventListener("focusin", (event) => {
      const target = event.target as HTMLElement | null;
      if (!target) {
        return;
      }
      target.classList.add("demo-focus-ring");
    });

    document.addEventListener("focusout", (event) => {
      const target = event.target as HTMLElement | null;
      if (!target) {
        return;
      }
      target.classList.remove("demo-focus-ring");
    });
  });
}

async function humanClick(page: Page, locator: Locator): Promise<void> {
  await locator.waitFor({ state: "visible" });
  await locator.hover();
  await idle(page, 160, 320);
  await locator.click();
  await idle(page, 140, 280);
}

async function humanFill(page: Page, locator: Locator, value: string): Promise<void> {
  await locator.waitFor({ state: "visible" });
  await locator.click();
  await idle(page, 120, 220);
  await locator.fill("");
  await idle(page, 120, 200);
  const delay = randomBetween(60, 110);
  await locator.type(value, { delay });
  await idle(page, 160, 260);
}

async function idle(page: Page, min = 120, max = 260): Promise<void> {
  await page.waitForTimeout(randomBetween(min, max));
}

function randomBetween(min: number, max: number): number {
  const lower = Math.min(min, max);
  const upper = Math.max(min, max);
  return Math.floor(lower + Math.random() * Math.max(1, upper - lower));
}
