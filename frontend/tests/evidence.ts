import type { Page } from "@playwright/test"

export async function captureMainContent(page: Page, path: string) {
  const stickyHeaders = page.locator("header.sticky")
  await stickyHeaders.evaluateAll((elements) => {
    for (const element of elements) {
      const htmlElement = element as HTMLElement
      htmlElement.dataset.evidenceVisibility = htmlElement.style.visibility
      htmlElement.style.visibility = "hidden"
    }
  })
  try {
    await page.locator("#main-content > div").screenshot({
      animations: "disabled",
      path,
    })
  } finally {
    await stickyHeaders.evaluateAll((elements) => {
      for (const element of elements) {
        const htmlElement = element as HTMLElement
        htmlElement.style.visibility =
          htmlElement.dataset.evidenceVisibility ?? ""
        delete htmlElement.dataset.evidenceVisibility
      }
    })
  }
}
