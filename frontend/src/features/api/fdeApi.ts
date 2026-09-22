import {
  AuditService,
  ContactsService,
  DashboardService,
  ImportsService,
  JobsService,
  UsersService,
} from "@/client"
import type {
  AuditEventPublic,
  ContactPublic,
  CursorPage,
  DashboardPublic,
  ImportActionPublic,
  ImportPreviewPublic,
  ImportPublic,
  ImportRowPublic,
  JobAttemptPublic,
  JobPublic,
  UserCreatedPublic,
  UserPublic,
} from "./types"

export const fdeApi = {
  dashboard: async () =>
    (await DashboardService.dashboard()).data as DashboardPublic,

  listImports: async (cursor?: string) =>
    (
      await ImportsService.listImports({
        query: { cursor, limit: 50 },
      })
    ).data as CursorPage<ImportPublic>,

  getImport: async (id: string) =>
    (await ImportsService.getImport({ path: { import_id: id } }))
      .data as ImportPublic,

  previewImport: async (id: string) =>
    (await ImportsService.previewImport({ path: { import_id: id } }))
      .data as ImportPreviewPublic,

  uploadImport: async (file: File) =>
    (await ImportsService.uploadImport({ body: { file } }))
      .data as ImportPublic,

  saveMapping: async (id: string, mapping: Record<string, string>) =>
    (
      await ImportsService.setMapping({
        body: { mapping },
        path: { import_id: id },
      })
    ).data as ImportPublic,

  validateImport: async (id: string) =>
    (await ImportsService.validateImport({ path: { import_id: id } }))
      .data as ImportActionPublic,

  confirmImport: async (id: string, idempotencyKey: string) =>
    (
      await ImportsService.confirmImport({
        headers: { "Idempotency-Key": idempotencyKey },
        path: { import_id: id },
      })
    ).data as ImportActionPublic,

  retryImport: async (id: string) =>
    (await ImportsService.retryImport({ path: { import_id: id } }))
      .data as ImportActionPublic,

  cancelImport: async (id: string) =>
    (await ImportsService.cancelImport({ path: { import_id: id } }))
      .data as ImportActionPublic,

  listImportRows: async (id: string, outcome?: string, cursor?: string) =>
    (
      await ImportsService.listValidationRows({
        path: { import_id: id },
        query: {
          cursor,
          limit: 50,
          outcome: outcome as
            | "accepted"
            | "invalid"
            | "file_duplicate"
            | "existing_contact"
            | undefined,
        },
      })
    ).data as unknown as CursorPage<ImportRowPublic>,

  downloadImportReport: async (
    id: string,
    report: "accepted" | "errors" | "duplicates",
  ) =>
    (
      await ImportsService.downloadReport({
        path: { import_id: id, report_name: report },
        responseType: "blob",
      })
    ).data as Blob,

  getJob: async (id: string) =>
    (await JobsService.getJob({ path: { job_id: id } })).data as JobPublic,

  listJobAttempts: async (id: string) =>
    (
      await JobsService.listAttempts({
        path: { job_id: id },
        query: { limit: 50 },
      })
    ).data as CursorPage<JobAttemptPublic>,

  listContacts: async (q?: string, cursor?: string) =>
    (
      await ContactsService.listContacts({
        query: { cursor, limit: 50, q: q || undefined },
      })
    ).data as CursorPage<ContactPublic>,

  listUsers: async (cursor?: string) =>
    (await UsersService.listUsers({ query: { cursor, limit: 50 } }))
      .data as CursorPage<UserPublic>,

  createUser: async (body: {
    email: string
    full_name?: string | null
    role: "admin" | "operator" | "viewer"
  }) => (await UsersService.createUser({ body })).data as UserCreatedPublic,

  updateUser: async (
    id: string,
    body: Partial<{
      email: string
      full_name: string | null
      role: "admin" | "operator" | "viewer"
      is_active: boolean
    }>,
  ) =>
    (
      await UsersService.updateUser({
        body,
        path: { user_id: id },
      })
    ).data as UserPublic,

  issueTemporaryPassword: async (id: string) =>
    (await UsersService.issueTemporaryPassword({ path: { user_id: id } })).data,

  listAuditEvents: async (action?: string, cursor?: string) =>
    (
      await AuditService.listAuditEvents({
        query: { action: action || undefined, cursor, limit: 50 },
      })
    ).data as CursorPage<AuditEventPublic>,
}
