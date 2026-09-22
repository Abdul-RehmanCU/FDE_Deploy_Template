import { expect, test } from "@playwright/test"

test("administrator sees managed users and audit activity", async ({
  page,
}) => {
  await page.goto("/admin")
  await expect(
    page.getByRole("heading", { name: "Users and roles" }),
  ).toBeVisible()
  await expect(page.getByText("e2e-operator@example.com")).toBeVisible()
  await expect(page.getByText("e2e-viewer@example.com")).toBeVisible()
  await page.screenshot({
    path: "test-results/evidence/users.png",
    fullPage: true,
  })

  await page.goto("/audit")
  await expect(
    page.getByRole("heading", { name: "Audit activity" }),
  ).toBeVisible()
  await expect(page.getByText("User created").first()).toBeVisible()
  await page.screenshot({
    path: "test-results/evidence/audit.png",
    fullPage: true,
  })
})
