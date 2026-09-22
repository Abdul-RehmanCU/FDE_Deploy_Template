import { mkdir, writeFile } from "node:fs/promises"
import { type APIRequestContext, expect, test as setup } from "@playwright/test"

const apiURL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000"
const appURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173"
const adminEmail = "e2e-admin@example.com"
const operatorEmail = "e2e-operator@example.com"
const viewerEmail = "e2e-viewer@example.com"
const adminPassword =
  process.env.E2E_ADMIN_PASSWORD ?? "E2E-Admin-Password-2026!"
const operatorPassword = "E2E-Operator-Password-2026!"
const viewerPassword = "E2E-Viewer-Password-2026!"

async function login(
  request: APIRequestContext,
  email: string,
  password: string,
) {
  const response = await request.post(`${apiURL}/api/v1/login/access-token`, {
    form: { username: email, password },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  return (await response.json()) as {
    access_token: string
    must_change_password: boolean
  }
}

async function changePassword(
  request: APIRequestContext,
  token: string,
  currentPassword: string,
  newPassword: string,
) {
  const response = await request.post(`${apiURL}/api/v1/users/me/password`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { current_password: currentPassword, new_password: newPassword },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
}

async function writeStorage(name: string, token: string) {
  await writeFile(
    `playwright/.auth/${name}.json`,
    JSON.stringify({
      cookies: [],
      origins: [
        {
          origin: appURL,
          localStorage: [{ name: "access_token", value: token }],
        },
      ],
    }),
  )
}

setup("create deterministic role sessions", async ({ request }) => {
  const temporaryAdminPassword = process.env.E2E_ADMIN_TEMP_PASSWORD
  expect(temporaryAdminPassword, "bootstrap password is required").toBeTruthy()
  await mkdir("playwright/.auth", { recursive: true })

  const initialAdmin = await login(request, adminEmail, temporaryAdminPassword!)
  await changePassword(
    request,
    initialAdmin.access_token,
    temporaryAdminPassword!,
    adminPassword,
  )
  const admin = await login(request, adminEmail, adminPassword)

  for (const account of [
    { email: operatorEmail, role: "operator", password: operatorPassword },
    { email: viewerEmail, role: "viewer", password: viewerPassword },
  ] as const) {
    const created = await request.post(`${apiURL}/api/v1/users`, {
      headers: { Authorization: `Bearer ${admin.access_token}` },
      data: {
        email: account.email,
        full_name: `E2E ${account.role}`,
        role: account.role,
      },
    })
    expect(created.status(), await created.text()).toBe(201)
    const { temporary_password } = (await created.json()) as {
      temporary_password: string
    }
    const temporary = await login(request, account.email, temporary_password)
    await changePassword(
      request,
      temporary.access_token,
      temporary_password,
      account.password,
    )
    const ready = await login(request, account.email, account.password)
    await writeStorage(account.role, ready.access_token)
  }

  await writeStorage("admin", admin.access_token)
})
