import { expect, test } from "@playwright/test";

test("landing page and public navigation", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("checked, matched and audited");
  for (const [link, heading] of [["Pricing", "Start free on your own machine"], ["FAQ", "Frequently asked questions"], ["Features", "Everything between"]] as const) {
    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: link }).click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText(heading);
  }
});

test("protected routes redirect to login", async ({ page }) => {
  await page.goto("/app/invoices");
  await expect(page).toHaveURL(/\/login\?next=%2Fapp%2Finvoices/);
});

test("invalid login shows an error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("accountant@ledgerflow-demo.example");
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Invalid email or password.")).toBeVisible();
});

test("registration creates a workspace", async ({ page }) => {
  const email = `owner-${Date.now()}@e2e-test.example`;
  await page.goto("/register");
  await page.getByLabel("Company name").fill("E2E Traders");
  await page.getByLabel("Your full name").fill("Esha Test");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill("Password1234");
  await page.getByRole("button", { name: "Create workspace" }).click();
  await page.waitForURL("**/app");
  await expect(page.getByText("Total invoices")).toBeVisible();
});
