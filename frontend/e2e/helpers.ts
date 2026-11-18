import { expect, type Page } from "@playwright/test";

export async function loginAs(page: Page, role: "accountant" | "approver" | "admin") {
  await page.goto("/login");
  await page.getByTestId(`demo-${role}`).click();
  await page.waitForURL("**/app");
  await expect(page.getByTestId("current-user")).toBeVisible();
}

export async function logout(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.waitForURL("**/login");
}
