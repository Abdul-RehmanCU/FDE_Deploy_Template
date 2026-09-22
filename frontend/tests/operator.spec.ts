import path from "node:path"
import { expect, test } from "@playwright/test"

test.describe.configure({ retries: 0 })

test("operator completes upload mapping validation confirmation and search", async ({
  page,
}) => {
  test.setTimeout(90_000)
  await page.goto("/imports/new")
  await page
    .locator('input[type="file"]')
    .setInputFiles(path.resolve("../fixtures/customer-data/valid-contacts.csv"))
  await page.getByRole("button", { name: "Upload and map columns" }).click()
  await expect(
    page.getByRole("heading", { name: "Map uploaded columns" }),
  ).toBeVisible()

  await page.getByLabel(/^Email/).selectOption("Email")
  await page.getByLabel(/^First name/).selectOption("First Name")
  await page.getByLabel(/^Last name/).selectOption("Last Name")
  await page.getByLabel(/^Company/).selectOption("Company")
  await page.getByLabel(/^Country code/).selectOption("Country")
  await page.getByLabel(/^External ID/).selectOption("External ID")
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: "test-results/evidence/column-mapping.png" })
  await page.getByRole("button", { name: "Save mapping" }).click()
  await expect(
    page.getByRole("button", { name: "Validate rows" }),
  ).toBeVisible()
  await page.getByRole("button", { name: "Validate rows" }).click()

  await expect(page.getByText("validated", { exact: true })).toBeVisible({
    timeout: 30_000,
  })
  await expect(
    page.getByRole("heading", { name: "Validation results" }),
  ).toBeVisible()
  await page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: "Validation results" }) })
    .screenshot({ path: "test-results/evidence/validation-results.png" })

  await page.getByRole("button", { name: "Import 3 valid rows" }).click()
  await expect(page.getByText("completed", { exact: true })).toBeVisible({
    timeout: 30_000,
  })
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: "test-results/evidence/completed-import.png" })

  await page.goto("/directory")
  await page.getByLabel("Search contacts").fill("Amélie")
  await expect(page.getByText("amelie.tremblay@example.com")).toBeVisible()
  await page.screenshot({ path: "test-results/evidence/directory.png" })

  await page.goto("/")
  await expect(
    page.getByRole("heading", { name: "Operations overview" }),
  ).toBeVisible()
  await page.screenshot({ path: "test-results/evidence/overview.png" })
})
