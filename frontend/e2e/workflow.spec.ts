import path from "node:path";
import { expect, test } from "@playwright/test";
import { loginAs, logout } from "./helpers";

const SAMPLES = path.resolve(__dirname, "../../sample-data/synthetic-invoices");

test.describe.configure({ mode: "serial" });

test("accountant dashboard, upload and duplicate detection", async ({ page }) => {
  await loginAs(page, "accountant");
  // Simulate a slow network (e.g. a cold hosted API): the supplier and PO option lists arrive after the form renders.
  await page.route(/\/api\/v1\/(suppliers|purchase-orders)\?/, async (route) => {
    await new Promise((r) => setTimeout(r, 1500));
    await route.continue();
  });
  await expect(page.getByText("Requires your attention")).toBeVisible();
  await page.getByRole("link", { name: "Upload invoices" }).first().click();
  await page.getByTestId("file-input").setInputFiles(path.join(SAMPLES, "02_wrong_gst.pdf"));
  const row = page.getByTestId("upload-row").first();
  await expect(row.getByText("Duplicate", { exact: true })).toBeVisible({ timeout: 30_000 });
  await row.getByRole("link", { name: "Review" }).click();
  const preview = page.getByTestId("document-preview");
  await expect(preview).toBeVisible();
  await expect.poll(() => preview.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(500);
  // Regression: the dropdowns must show the saved supplier link, not "Not linked", once their options have loaded.
  await expect(page.locator('select[name="supplier_id"] option:checked')).toContainText("Deccan Office Supplies");
  await page.getByRole("tab", { name: /Duplicates/ }).click();
  await expect(page.getByText("Same supplier and invoice number (DOS-INV-88213).")).toBeVisible();
  await page.getByRole("tab", { name: /Validation/ }).click();
  await expect(page.getByTestId("check-line_tax")).toContainText("6408.00");
});

test("accountant corrects missing fields and submits", async ({ page }) => {
  await loginAs(page, "accountant");
  await page.goto("/app/invoices?");
  await page.getByLabel("Search invoices").fill("Coromandel");
  await page.getByRole("link", { name: "Untitled invoice" }).first().click();
  await expect(page.getByTestId("invoice-status")).toContainText("Needs review");
  await page.getByRole("textbox").first().fill("CE-24600");
  await page.locator('input[name="invoice_date"]').fill("2026-10-20");
  await page.getByRole("button", { name: "Save corrections" }).click();
  await expect(page.getByTestId("invoice-title")).toContainText("CE-24600");
  await page.getByTestId("submit-btn").click();
  await page.getByTestId("confirm-submit").click();
  await expect(page.getByTestId("invoice-status")).toContainText("Pending approval");
  await page.getByRole("tab", { name: "Activity" }).click();
  await expect(page.getByText("Correct", { exact: true })).toBeVisible();
  await logout(page);
});

test("approver approves and rejects with a reason", async ({ page }) => {
  await loginAs(page, "approver");
  await expect(page.getByText("Your approval queue")).toBeVisible();
  await page.goto("/app/approvals");
  await page.getByRole("row", { name: /CE-24600/ }).getByRole("link", { name: "Review" }).click();
  await page.getByTestId("approve-btn").click();
  await page.getByTestId("confirm-approve").click();
  await expect(page.getByTestId("invoice-status")).toContainText("Approved");

  await page.goto("/app/approvals");
  await page.getByRole("row", { name: /KST\/26-27\/0457/ }).getByRole("link", { name: "Review" }).click();
  await page.getByTestId("reject-btn").click();
  await expect(page.getByTestId("confirm-reject")).toBeDisabled();
  await page.getByTestId("reject-reason").fill("Delivery pallets were not ordered on the PO.");
  await page.getByTestId("confirm-reject").click();
  await expect(page.getByTestId("invoice-status")).toContainText("Rejected");
});

test("approver cannot reach admin pages or upload", async ({ page }) => {
  await loginAs(page, "approver");
  await expect(page.getByRole("link", { name: "Upload invoices" })).toHaveCount(0);
  await page.goto("/app/admin/users");
  await expect(page.getByText("You don't have access to this page")).toBeVisible();
});

test("admin sees audit trail and exports Excel", async ({ page }) => {
  await loginAs(page, "admin");
  await expect(page.getByText("Recent activity")).toBeVisible();
  await page.goto("/app/admin/audit");
  await expect(page.getByRole("cell", { name: "invoice.reject" }).first()).toBeVisible();
  await page.goto("/app/reports");
  await expect(page.getByRole("columnheader", { name: "Invoice No" })).toBeVisible();
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Export full workbook" }).click()]);
  expect(dl.suggestedFilename()).toMatch(/^ledgerflow-.*\.xlsx$/);
});
