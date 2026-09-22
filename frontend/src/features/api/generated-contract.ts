import type {
  AuditEventPublic as GeneratedAuditEvent,
  ContactPublic as GeneratedContact,
  DashboardPublic as GeneratedDashboard,
  ImportPublic as GeneratedImport,
  ImportAction as GeneratedImportAction,
  ImportPreview as GeneratedImportPreview,
  JobPublic as GeneratedJob,
  JobAttemptPublic as GeneratedJobAttempt,
  UserPublic as GeneratedUser,
  UserCreated as GeneratedUserCreated,
} from "@/client"
import type {
  AuditEventPublic,
  ContactPublic,
  DashboardPublic,
  ImportActionPublic,
  ImportPreviewPublic,
  ImportPublic,
  JobAttemptPublic,
  JobPublic,
  UserCreatedPublic,
  UserPublic,
} from "./types"

type Assert<T extends true> = T
type Assignable<Source, Target> = Source extends Target ? true : false

type DashboardMatches = Assert<Assignable<GeneratedDashboard, DashboardPublic>>
type ImportMatches = Assert<Assignable<GeneratedImport, ImportPublic>>
type ImportActionMatches = Assert<
  Assignable<GeneratedImportAction, ImportActionPublic>
>
type ImportPreviewMatches = Assert<
  Assignable<GeneratedImportPreview, ImportPreviewPublic>
>
type JobMatches = Assert<Assignable<GeneratedJob, JobPublic>>
type JobAttemptMatches = Assert<
  Assignable<GeneratedJobAttempt, JobAttemptPublic>
>
type ContactMatches = Assert<Assignable<GeneratedContact, ContactPublic>>
type UserMatches = Assert<Assignable<GeneratedUser, UserPublic>>
type UserCreatedMatches = Assert<
  Assignable<GeneratedUserCreated, UserCreatedPublic>
>
type AuditMatches = Assert<Assignable<GeneratedAuditEvent, AuditEventPublic>>

export type GeneratedContractAssertions = [
  DashboardMatches,
  ImportMatches,
  ImportActionMatches,
  ImportPreviewMatches,
  JobMatches,
  JobAttemptMatches,
  ContactMatches,
  UserMatches,
  UserCreatedMatches,
  AuditMatches,
]
