import { chromium } from "playwright"
import { mkdir } from "node:fs/promises"
import path from "node:path"

const required = (name: string): string => {
  const value = process.env[name]
  if (!value) throw new Error(`${name} is required`)
  return value
}

const grafanaUrl = required("GRAFANA_URL")
const alertmanagerUrl = required("ALERTMANAGER_URL")
const username = required("GRAFANA_USER")
const password = required("GRAFANA_PASSWORD")
const traceId = required("TRACE_ID")
const outputDir = required("OUTPUT_DIR")
const alertPhase = required("ALERT_PHASE")

await mkdir(outputDir, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage()

await page.goto(`${grafanaUrl}/login`, { waitUntil: "domcontentloaded" })
await page.locator('input[name="user"]').fill(username)
await page.locator('input[name="password"]').fill(password)
await page.getByRole("button", { name: /log in/i }).click()
await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 30_000 })

if (alertPhase === "firing") {
  await page.goto(`${grafanaUrl}/d/fde-operations-overview/fde-operations-overview?from=now-15m&to=now`, {
    waitUntil: "networkidle",
  })
  await page.getByText(/FDE Operations Overview/i).first().waitFor({ timeout: 30_000 })
  await page.screenshot({ path: path.join(outputDir, "grafana-dashboard.png"), fullPage: true })

  const tempoQuery = encodeURIComponent(
    JSON.stringify({
      trace: {
        datasource: "Tempo",
        queries: [{ refId: "A", queryType: "traceql", query: traceId }],
        range: { from: "now-15m", to: "now" },
      },
    }),
  )
  await page.goto(`${grafanaUrl}/explore?schemaVersion=1&panes=${tempoQuery}`, { waitUntil: "networkidle" })
  await page.getByText(/fde-worker/i).first().waitFor({ timeout: 30_000 })
  await page.screenshot({ path: path.join(outputDir, "tempo-trace.png"), fullPage: true })

  const logQuery = `{namespace="fde-staging"} | json | trace_id="${traceId}"`
  const lokiQuery = encodeURIComponent(
    JSON.stringify({
      logs: {
        datasource: "Loki",
        queries: [{ refId: "A", expr: logQuery, queryType: "range" }],
        range: { from: "now-15m", to: "now" },
      },
    }),
  )
  await page.goto(`${grafanaUrl}/explore?schemaVersion=1&panes=${lokiQuery}`, { waitUntil: "networkidle" })
  await page.getByText(traceId).first().waitFor({ timeout: 30_000 })
  await page.screenshot({ path: path.join(outputDir, "loki-trace-logs.png"), fullPage: true })
}

await page.goto(`${alertmanagerUrl}/#/alerts`, { waitUntil: "networkidle" })
if (alertPhase === "firing") {
  await page.getByText("FDEApiUnavailable").first().waitFor({ timeout: 30_000 })
} else {
  await page.waitForTimeout(2_000)
}
await page.screenshot({ path: path.join(outputDir, `alert-${alertPhase}.png`), fullPage: true })

await browser.close()
