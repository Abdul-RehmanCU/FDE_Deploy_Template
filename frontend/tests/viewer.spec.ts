import { expect, test } from "@playwright/test"

test("viewer has read-only navigation and cannot start an import", async ({
  page,
}) => {
  await page.goto("/imports/new")
  await expect(
    page.getByText("Viewer accounts have read-only access"),
  ).toBeVisible()
  await expect(page.locator('input[type="file"]')).toHaveCount(0)

  await page.goto("/admin")
  await page.waitForURL("/")
  await expect(
    page.getByRole("heading", { name: "Operations overview" }),
  ).toBeVisible()
})
