export type UserRole = "admin" | "operator" | "viewer"

export type ImportStatus =
  | "uploaded"
  | "mapped"
  | "validating"
  | "validated"
  | "importing"
  | "completed"
  | "failed"
  | "cancelled"

export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancel_requested"
  | "cancelled"

export interface DashboardPublic {
  imports_total: number
  contacts_total: number
  accepted_rows_total: number
  rejected_rows_total: number
  duplicate_rows_total: number
  jobs_by_status: Record<string, number>
}

export interface ImportPublic {
  id: string
  original_filename: string
  status: ImportStatus
  mapping: Record<string, string> | null
  header: string[]
  total_rows: number
  accepted_count: number
  rejected_count: number
  duplicate_count: number
  existing_contact_count: number
  inserted_count: number
  skipped_count: number
  error_code: string | null
  error_message: string | null
  created_by_id: string
  created_at: string
  updated_at: string
}

export interface ValidationErrorPublic {
  code: string
  field: string | null
  message: string
}

export interface ImportRowPublic {
  row_number: number
  outcome: "accepted" | "invalid" | "file_duplicate" | "existing_contact"
  clean_data: Record<string, string | null>
  errors: ValidationErrorPublic[]
}

export interface ImportActionPublic {
  import_batch: ImportPublic
  job_id: string | null
}

export interface JobPublic {
  id: string
  import_id: string
  kind: string
  status: JobStatus
  attempt_count: number
  max_attempts: number
  error_code: string | null
  error_message: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface JobAttemptPublic {
  attempt_number: number
  status: JobStatus
  error_code: string | null
  error_message: string | null
  started_at: string
  finished_at: string | null
}

export interface ContactPublic {
  id: string
  email: string
  first_name: string
  last_name: string
  company: string | null
  country_code: string | null
  external_id: string | null
  created_at: string
}

export interface AuditEventPublic {
  id: string
  actor_id: string | null
  action: string
  resource_type: string
  resource_id: string | null
  metadata_json: Record<string, unknown>
  request_id: string | null
  created_at: string
}

export interface UserPublic {
  id: string
  email: string
  full_name: string | null
  role: UserRole
  is_active: boolean
  must_change_password: boolean
  created_at: string
  updated_at: string
}

export interface CursorPage<T> {
  data: T[]
  next_cursor: string | null
  has_more: boolean
}

export interface ApiErrorEnvelope {
  detail: {
    code: string
    message: string
    fields?: Record<string, string>
  }
}
