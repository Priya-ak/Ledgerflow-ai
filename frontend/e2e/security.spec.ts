import { expect, test } from "@playwright/test";
import { totp } from "./totp";

test("user enables two-factor authentication and signs in with a code", async ({ page }) => {
  const email = `mfa-${Date.now()}@e2e-test.example`;
  await page.goto("/register");
  await page.getByLabel("Company name").fill("MFA Test Co");
  await page.getByLabel("Your full name").fill("Mira Test");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill("Password1234");
  await page.getByRole("button", { name: "Create workspace" }).click();
  await page.waitForURL("**/app");

  await page.goto("/app/account");
  await page.getByTestId("mfa-start").click();
  const secret = (await page.getByTestId("mfa-secret").innerText()).replace(/\s/g, "");
  await expect(page.getByAltText("Two-factor QR code")).toBeVisible();
  const enrolmentCode = totp(secret);
  await page.getByTestId("mfa-setup-code").fill(enrolmentCode);
  await page.getByTestId("mfa-confirm").click();
  await expect(page.getByTestId("recovery-codes")).toBeVisible();
  await page.getByRole("button", { name: "I've saved them" }).click();
  await expect(page.getByText("Recovery codes remaining:")).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await page.waitForURL("**/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("Password1234");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Two-factor verification" })).toBeVisible();
  // replaying the exact enrolment code is always rejected; a later code works
  await page.getByTestId("mfa-code").fill(enrolmentCode);
  await page.getByRole("button", { name: "Verify and sign in" }).click();
  await expect(page.getByText("Invalid or already-used code.")).toBeVisible();
  await page.getByTestId("mfa-code").fill(totp(secret, Date.now(), 1));
  await page.getByRole("button", { name: "Verify and sign in" }).click();
  await page.waitForURL("**/app");
  await expect(page.getByTitle("Account & security")).toContainText("2FA on");
});

test("PDF with embedded JavaScript is blocked at upload", async ({ page, request }) => {
  await page.goto("/login");
  await page.getByTestId("demo-accountant").click();
  await page.waitForURL("**/app");
  await page.goto("/app/invoices/upload");
  const pdf = Buffer.from(
    "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R/OpenAction 4 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n" +
    "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n4 0 obj<</S/JavaScript/JS(app.alert(1))>>endobj\n" +
    "trailer<</Root 1 0 R>>\n%%EOF\n");
  await page.getByTestId("file-input").setInputFiles({ name: "evil-invoice.pdf", mimeType: "application/pdf", buffer: pdf });
  await expect(page.getByTestId("upload-row").first()).toContainText("active content", { timeout: 20_000 });
});
