import { expect, test } from "@playwright/test"

test("operator overview and directory remain usable on mobile", async ({
  page,
}) => {
  await page.goto("/")
  await expect(
    page.getByRole("heading", { name: "Operations overview" }),
  ).toBeVisible()
  await page.screenshot({
    path: "test-results/evidence/mobile-overview.png",
    fullPage: true,
  })

  await page.goto("/directory")
  await expect(page.getByLabel("Search contacts")).toBeVisible()
})
