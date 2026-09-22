import { client } from "@/client/client.gen"
import type {
  ApiErrorEnvelope,
  AuditEventPublic,
  ContactPublic,
  CursorPage,
  DashboardPublic,
  ImportActionPublic,
  ImportPublic,
  ImportRowPublic,
  JobAttemptPublic,
  JobPublic,
  UserPublic,
} from "./types"

const security = [{ scheme: "bearer", type: "http" }] as const
type Errors = { 400: ApiErrorEnvelope; 401: ApiErrorEnvelope; 403: ApiErrorEnvelope }

async function get<T>(url: string, query?: Record<string, unknown>): Promise<T> {
  const response = await client.get<{ 200: T }, Errors, true>({
    responseType: "json",
    security,
    throwOnError: true,
    url,
    query,
  })
  return response.data
}

async function post<T>(
  url: string,
  body?: unknown,
  headers?: Record<string, string>,
): Promise<T> {
  const response = await client.post<{ 200: T; 201: T; 202: T }, Errors, true>({
    body,
    headers,
    responseType: "json",
    security,
    throwOnError: true,
    url,
  })
  return response.data
}

export const fdeApi = {
  dashboard: () => get<DashboardPublic>("/api/v1/dashboard"),

  listImports: (cursor?: string) =>
    get<CursorPage<ImportPublic>>("/api/v1/imports", {
      cursor,
      limit: 50,
    }),

  getImport: (id: string) => get<ImportPublic>(`/api/v1/imports/${id}`),

  uploadImport: (file: File) => {
    const body = new FormData()
    body.append("file", file)
    return post<ImportPublic>("/api/v1/imports", body)
  },

  saveMapping: async (id: string, mapping: Record<string, string>) => {
    const response = await client.put<{ 200: ImportPublic }, Errors, true>({
      body: { mapping },
      headers: { "Content-Type": "application/json" },
      responseType: "json",
      security,
      throwOnError: true,
      url: `/api/v1/imports/${id}/mapping`,
    })
    return response.data
  },

  validateImport: (id: string) =>
    post<ImportActionPublic>(`/api/v1/imports/${id}/validate`),

  confirmImport: (id: string, idempotencyKey: string) =>
    post<ImportActionPublic>(`/api/v1/imports/${id}/confirm`, undefined, {
      "Idempotency-Key": idempotencyKey,
    }),

  retryImport: (id: string) =>
    post<ImportActionPublic>(`/api/v1/imports/${id}/retry`),

  cancelImport: (id: string) =>
    post<ImportActionPublic>(`/api/v1/imports/${id}/cancel`),

  listImportRows: (id: string, outcome?: string, cursor?: string) =>
    get<CursorPage<ImportRowPublic>>(`/api/v1/imports/${id}/rows`, {
      cursor,
      limit: 50,
      outcome,
    }),

  getJob: (id: string) => get<JobPublic>(`/api/v1/jobs/${id}`),

  listJobAttempts: (id: string) =>
    get<CursorPage<JobAttemptPublic>>(`/api/v1/jobs/${id}/attempts`, {
      limit: 50,
    }),

  listContacts: (q?: string, cursor?: string) =>
    get<CursorPage<ContactPublic>>("/api/v1/contacts", {
      cursor,
      limit: 50,
      q: q || undefined,
    }),

  listUsers: (cursor?: string) =>
    get<CursorPage<UserPublic>>("/api/v1/users", { cursor, limit: 50 }),

  listAuditEvents: (action?: string, cursor?: string) =>
    get<CursorPage<AuditEventPublic>>("/api/v1/audit-events", {
      action: action || undefined,
      cursor,
      limit: 50,
    }),
}
