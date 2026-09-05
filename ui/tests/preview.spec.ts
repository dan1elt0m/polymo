import { test, expect } from '@playwright/test';

// E2E preview test with network interception (does not rely on MSW)
// Verifies: validate call, sample call, table render, JSON view.

test.describe('Preview Data Flow', () => {
  test('fetches and displays sample data then switches to JSON view', async ({ page }) => {
    // Intercept validation
    await page.route('**/api/validate', async (route) => {
      const json = { valid: true, config: null };
      await route.fulfill({ status: 200, body: JSON.stringify(json), headers: { 'Content-Type': 'application/json' } });
    });

    // Intercept sample
    await page.route('**/api/sample', async (route) => {
      const json = {
        stream: 'orders',
        records: [
          { id: 1, name: 'Example', status: 'ok' },
          { id: 2, name: 'Sample', status: 'ok' },
        ],
        dtypes: [
          { column: 'id', type: 'BIGINT' },
          { column: 'name', type: 'STRING' },
          { column: 'status', type: 'STRING' },
        ],
      };
      await route.fulfill({ status: 200, body: JSON.stringify(json), headers: { 'Content-Type': 'application/json' } });
    });

    await page.goto('/');

    // Ensure Stream Name input is present (layout change placed it at top)
    const streamNameInput = page.getByLabel('Stream Name');
    await expect(streamNameInput).toBeVisible();

    // Optional: modify stream name to ensure form interaction
    await streamNameInput.fill('orders');

    // Trigger preview
    const previewButton = page.getByRole('button', { name: /preview/i });
    await previewButton.click();

    // Wait for status pill message (Fetched 2 sample records)
    await expect(page.getByText('Fetched 2 sample records')).toBeVisible({ timeout: 5000 });

    // Assert table cells rendered
    await expect(page.getByText('Example')).toBeVisible();
    await expect(page.getByText('Sample')).toBeVisible();

    // Switch to JSON Records view
    const recordsViewButton = page.getByRole('button', { name: /records/i });
    await recordsViewButton.click();

    // JSON output should contain the record
    await expect(page.getByText('"name": "Example"')).toBeVisible();
  });
});

