import path from "node:path"
import { expect, test } from "@playwright/test"

test("operator overview and directory remain usable on mobile", async ({
  page,
}) => {
  test.setTimeout(90_000)
  await page.goto("/")
  await expect(
    page.getByRole("heading", { name: "Operations overview" }),
  ).toBeVisible()
  await page.screenshot({ path: "test-results/evidence/mobile-overview.png" })

  await page.goto("/directory")
  await expect(page.getByLabel("Search contacts")).toBeVisible()

  await page.goto("/imports/new")
  await page
    .locator('input[type="file"]')
    .setInputFiles(path.resolve("../fixtures/customer-data/formula-like.csv"))
  await page.getByRole("button", { name: "Upload and map columns" }).click()
  await expect(
    page.getByRole("heading", { name: "Map uploaded columns" }),
  ).toBeVisible()

  for (const [label, expected] of [
    [/^Email/, "Email"],
    [/^First name/, "First Name"],
    [/^Last name/, "Last Name"],
  ] as const) {
    const select = page.getByLabel(label)
    await select.focus()
    await expect(select).toBeFocused()
    await page.keyboard.press("ArrowDown")
    await page.keyboard.press("Enter")
    await expect(select).toHaveValue(expected)
  }

  await page.locator("#main-content > div").screenshot({
    path: "test-results/evidence/mobile-column-mapping.png",
  })

  const save = page.getByRole("button", { name: "Save mapping" })
  await save.focus()
  await expect(save).toBeFocused()
  await page.keyboard.press("Enter")
  const validate = page.getByRole("button", { name: "Validate rows" })
  await expect(validate).toBeVisible()
  await validate.focus()
  await page.keyboard.press("Enter")
  await expect(page.getByText("validated", { exact: true })).toBeVisible({
    timeout: 30_000,
  })
  await page.locator("#main-content > div").screenshot({
    path: "test-results/evidence/mobile-validation.png",
  })

  const confirm = page.getByRole("button", { name: "Import 1 valid rows" })
  await confirm.focus()
  await expect(confirm).toBeFocused()
  await page.keyboard.press("Enter")
  await expect(page.getByText("completed", { exact: true })).toBeVisible({
    timeout: 30_000,
  })
})
