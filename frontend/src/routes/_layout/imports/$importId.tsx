import {
  type UseQueryResult,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  FileWarning,
  LoaderCircle,
  Play,
  RefreshCw,
  RotateCcw,
  XCircle,
} from "lucide-react"
import { useMemo, useState } from "react"

import { EmptyState } from "@/components/Common/EmptyState"
import { LoadingState } from "@/components/Common/LoadingState"
import { PageHeader } from "@/components/Common/PageHeader"
import { StatusBadge } from "@/components/Common/StatusBadge"
import { Button } from "@/components/ui/button"
import { fdeApi } from "@/features/api/fdeApi"
import type {
  CursorPage,
  ImportPublic,
  ImportRowPublic,
} from "@/features/api/types"
import useAuth from "@/hooks/useAuth"
import { extractErrorMessage } from "@/utils"

const canonicalFields = [
  { key: "email", label: "Email", required: true },
  { key: "first_name", label: "First name", required: true },
  { key: "last_name", label: "Last name", required: true },
  { key: "company", label: "Company", required: false },
  { key: "country_code", label: "Country code", required: false },
  { key: "external_id", label: "External ID", required: false },
] as const

type Mapping = Record<string, string>
type OutcomeFilter =
  | "accepted"
  | "invalid"
  | "file_duplicate"
  | "existing_contact"

export const Route = createFileRoute("/_layout/imports/$importId")({
  component: ImportDetailPage,
  head: () => ({ meta: [{ title: "Import detail · FDE Deploy" }] }),
})

function ImportDetailPage() {
  const { importId } = Route.useParams()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [outcome, setOutcome] = useState<OutcomeFilter>("accepted")
  const [jobId, setJobId] = useState<string | null>(null)
  const role = (user as { role?: string } | null)?.role
  const canMutate = role !== "viewer"
  const canDownload = role !== "viewer"

  const importQuery = useQuery({
    queryKey: ["import", importId],
    queryFn: () => fdeApi.getImport(importId),
    refetchInterval: (query) =>
      ["validating", "importing"].includes(query.state.data?.status ?? "")
        ? 3_000
        : false,
  })
  const showRows = ["validated", "importing", "completed", "failed"].includes(
    importQuery.data?.status ?? "",
  )
  const rows = useQuery({
    queryKey: ["import-rows", importId, outcome],
    queryFn: () => fdeApi.listImportRows(importId, outcome),
    enabled: showRows,
  })

  const refreshImport = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["import", importId] }),
      queryClient.invalidateQueries({ queryKey: ["imports"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
    ])
  }

  const validate = useMutation({
    mutationFn: () => fdeApi.validateImport(importId),
    onSuccess: async (result) => {
      setJobId(result.job_id)
      await refreshImport()
    },
  })
  const confirm = useMutation({
    mutationFn: () => {
      const storageKey = `fde-confirm-${importId}`
      const key = localStorage.getItem(storageKey) || crypto.randomUUID()
      localStorage.setItem(storageKey, key)
      return fdeApi.confirmImport(importId, key)
    },
    onSuccess: async (result) => {
      setJobId(result.job_id)
      await refreshImport()
    },
  })
  const retry = useMutation({
    mutationFn: () => fdeApi.retryImport(importId),
    onSuccess: async (result) => {
      setJobId(result.job_id)
      await refreshImport()
    },
  })
  const cancel = useMutation({
    mutationFn: () => fdeApi.cancelImport(importId),
    onSuccess: refreshImport,
  })

  if (importQuery.isPending) return <LoadingState label="Loading import" />
  if (importQuery.isError) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Import could not be loaded"
        description="The requested import is unavailable or you do not have access to it."
        action={
          <Button variant="outline" asChild>
            <Link to="/imports">
              <ArrowLeft className="size-4" />
              Back to imports
            </Link>
          </Button>
        }
      />
    )
  }

  const item = importQuery.data
  const actionError =
    validate.error || confirm.error || retry.error || cancel.error

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Guided import"
        title={item.original_filename}
        description={`Created ${new Intl.DateTimeFormat(undefined, { dateStyle: "long", timeStyle: "short" }).format(new Date(item.created_at))}`}
        actions={<StatusBadge status={item.status} />}
      />

      <ol className="grid gap-3 sm:grid-cols-4" aria-label="Import progress">
        {[
          ["1", "Upload", true],
          ["2", "Map", item.status !== "uploaded"],
          [
            "3",
            "Validate",
            ["validated", "importing", "completed"].includes(item.status),
          ],
          ["4", "Confirm", item.status === "completed"],
        ].map(([number, label, complete]) => (
          <li
            key={String(number)}
            className={`rounded-xl border p-3 text-sm ${complete ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "bg-card text-muted-foreground"}`}
          >
            <span className="mr-2 font-semibold">{number}.</span>
            {label}
          </li>
        ))}
      </ol>

      {item.status === "uploaded" || item.status === "mapped" ? (
        <MappingPanel
          item={item}
          canMutate={canMutate}
          onSaved={refreshImport}
        />
      ) : (
        <ImportSummary item={item} />
      )}

      {actionError && (
        <div
          role="alert"
          className="flex gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          {extractErrorMessage(actionError)}
        </div>
      )}

      {canMutate && (
        <div className="surface-card flex flex-wrap items-center justify-end gap-3 p-4">
          {item.status === "mapped" && (
            <Button
              onClick={() => validate.mutate()}
              disabled={validate.isPending}
            >
              <Play className="size-4" />
              {validate.isPending ? "Starting…" : "Validate rows"}
            </Button>
          )}
          {item.status === "validated" && (
            <Button
              onClick={() => confirm.mutate()}
              disabled={confirm.isPending || item.accepted_count === 0}
            >
              <CheckCircle2 className="size-4" />
              {confirm.isPending
                ? "Confirming…"
                : `Import ${item.accepted_count} valid rows`}
            </Button>
          )}
          {item.status === "failed" && (
            <Button onClick={() => retry.mutate()} disabled={retry.isPending}>
              <RotateCcw className="size-4" />
              Retry eligible job
            </Button>
          )}
          {["uploaded", "mapped", "validating", "validated"].includes(
            item.status,
          ) && (
            <Button
              variant="outline"
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
            >
              <XCircle className="size-4" />
              Cancel
            </Button>
          )}
        </div>
      )}

      {jobId && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
          Background work started.{" "}
          <Link
            to="/jobs/$jobId"
            params={{ jobId }}
            className="font-semibold underline"
          >
            View job status
          </Link>
        </div>
      )}

      {showRows && (
        <ValidationResults
          importId={importId}
          outcome={outcome}
          setOutcome={setOutcome}
          rows={rows}
          canDownload={canDownload}
          filename={item.original_filename}
        />
      )}
    </div>
  )
}

function MappingPanel({
  item,
  canMutate,
  onSaved,
}: {
  item: ImportPublic
  canMutate: boolean
  onSaved: () => Promise<void>
}) {
  const [mapping, setMapping] = useState<Mapping>(item.mapping ?? {})
  const save = useMutation({
    mutationFn: () => fdeApi.saveMapping(item.id, mapping),
    onSuccess: onSaved,
  })
  const selectedHeaders = useMemo(
    () => new Set(Object.values(mapping).filter(Boolean)),
    [mapping],
  )
  const isComplete = canonicalFields
    .filter((field) => field.required)
    .every((field) => mapping[field.key])

  return (
    <section className="surface-card p-6" aria-labelledby="mapping-heading">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 id="mapping-heading" className="text-lg font-semibold">
            Map uploaded columns
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Each uploaded header can map to one contact field.
          </p>
        </div>
        <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
          {item.header.length} source columns
        </span>
      </div>
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {canonicalFields.map((field) => (
          <label key={field.key} className="grid gap-2 text-sm font-medium">
            <span>
              {field.label}
              {field.required ? (
                <span className="ml-1 text-red-600">*</span>
              ) : (
                <span className="ml-1 font-normal text-muted-foreground">
                  optional
                </span>
              )}
            </span>
            <select
              className="h-10 rounded-md border bg-background px-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={mapping[field.key] ?? ""}
              disabled={!canMutate}
              onChange={(event) =>
                setMapping((current) => ({
                  ...current,
                  [field.key]: event.target.value,
                }))
              }
            >
              <option value="">Do not import</option>
              {item.header.map((header) => (
                <option
                  key={header}
                  value={header}
                  disabled={
                    selectedHeaders.has(header) && mapping[field.key] !== header
                  }
                >
                  {header}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      {save.isError && (
        <p role="alert" className="mt-4 text-sm text-red-700">
          {extractErrorMessage(save.error)}
        </p>
      )}
      {canMutate && (
        <div className="mt-6 flex justify-end">
          <Button
            disabled={!isComplete || save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "Saving…" : "Save mapping"}
          </Button>
        </div>
      )}
    </section>
  )
}

function ImportSummary({ item }: { item: ImportPublic }) {
  const stats = [
    ["Total rows", item.total_rows],
    ["Accepted", item.accepted_count],
    ["Invalid", item.rejected_count],
    ["File duplicates", item.duplicate_count],
    ["Existing contacts", item.existing_contact_count],
    ["Inserted", item.inserted_count],
  ]
  return (
    <section
      className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
      aria-label="Import counts"
    >
      {stats.map(([label, value]) => (
        <div key={String(label)} className="surface-card p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
        </div>
      ))}
      {item.error_message && (
        <div className="sm:col-span-2 lg:col-span-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <strong>{item.error_code || "Import failed"}:</strong>{" "}
          {item.error_message}
        </div>
      )}
    </section>
  )
}

function ValidationResults({
  importId,
  outcome,
  setOutcome,
  rows,
  canDownload,
  filename,
}: {
  importId: string
  outcome: OutcomeFilter
  setOutcome: (value: OutcomeFilter) => void
  rows: UseQueryResult<CursorPage<ImportRowPublic>, Error>
  canDownload: boolean
  filename: string
}) {
  const download = useMutation({
    mutationFn: (report: "accepted" | "errors" | "duplicates") =>
      fdeApi.downloadImportReport(importId, report),
    onSuccess: (blob, report) => {
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `${filename.replace(/\.csv$/i, "")}-${report}.csv`
      anchor.click()
      URL.revokeObjectURL(url)
    },
  })
  return (
    <section
      className="surface-card overflow-hidden"
      aria-labelledby="validation-heading"
    >
      <div className="flex flex-col gap-4 border-b p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 id="validation-heading" className="font-semibold">
            Validation results
          </h2>
          <p className="text-sm text-muted-foreground">
            Row-level outcomes remain separate from infrastructure errors.
          </p>
        </div>
        {canDownload && (
          <div className="flex flex-wrap gap-2">
            {(["accepted", "errors", "duplicates"] as const).map((report) => (
              <Button
                key={report}
                size="sm"
                variant="outline"
                disabled={download.isPending}
                onClick={() => download.mutate(report)}
              >
                <Download className="size-3.5" />
                {report}
              </Button>
            ))}
          </div>
        )}
      </div>
      <div
        className="flex gap-2 overflow-x-auto border-b p-3"
        role="tablist"
        aria-label="Validation outcome"
      >
        {(
          ["accepted", "invalid", "file_duplicate", "existing_contact"] as const
        ).map((value) => (
          <Button
            key={value}
            size="sm"
            variant={outcome === value ? "default" : "ghost"}
            role="tab"
            aria-selected={outcome === value}
            onClick={() => setOutcome(value)}
          >
            {value.replaceAll("_", " ")}
          </Button>
        ))}
      </div>
      {rows.isPending ? (
        <div className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
          <LoaderCircle className="size-4 animate-spin" />
          Loading rows…
        </div>
      ) : rows.isError ? (
        <div className="p-5">
          <EmptyState
            icon={FileWarning}
            title="Rows could not be loaded"
            description="Retry the selected validation outcome."
            action={
              <Button variant="outline" onClick={() => rows.refetch()}>
                <RefreshCw className="size-4" />
                Retry
              </Button>
            }
          />
        </div>
      ) : rows.data.data.length === 0 ? (
        <div className="p-5">
          <EmptyState
            icon={CheckCircle2}
            title="No rows in this outcome"
            description="Choose another outcome to inspect its records."
          />
        </div>
      ) : (
        <div className="divide-y">
          {rows.data.data.map((row) => (
            <div
              key={row.row_number}
              className="grid gap-2 p-4 text-sm md:grid-cols-[100px_minmax(0,1fr)]"
            >
              <span className="font-medium">Row {row.row_number}</span>
              <div>
                <p className="break-words text-muted-foreground">
                  {Object.entries(row.clean_data)
                    .map(([key, value]) => `${key}: ${value ?? "—"}`)
                    .join(" · ")}
                </p>
                {row.errors.length > 0 && (
                  <ul className="mt-2 space-y-1 text-red-700">
                    {row.errors.map((error) => (
                      <li key={`${error.code}-${error.field}-${error.message}`}>
                        {error.field ? `${error.field}: ` : ""}
                        {error.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
