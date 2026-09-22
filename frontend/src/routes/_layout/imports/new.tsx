import { useMutation, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { AlertCircle, FileCheck2, FileUp, ShieldCheck } from "lucide-react"
import { useId, useState } from "react"

import { PageHeader } from "@/components/Common/PageHeader"
import { Button } from "@/components/ui/button"
import { fdeApi } from "@/features/api/fdeApi"
import useAuth from "@/hooks/useAuth"
import { extractErrorMessage } from "@/utils"

const MAX_FILE_BYTES = 10 * 1024 * 1024

export const Route = createFileRoute("/_layout/imports/new")({
  component: NewImportPage,
  head: () => ({ meta: [{ title: "New import · FDE Deploy" }] }),
})

function NewImportPage() {
  const inputId = useId()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const [file, setFile] = useState<File | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)
  const role = (user as { role?: string } | null)?.role
  const canImport = role !== "viewer"

  const upload = useMutation({
    mutationFn: (selected: File) => fdeApi.uploadImport(selected),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["imports"] })
      navigate({
        to: "/imports/$importId",
        params: { importId: created.id },
      })
    },
  })

  const chooseFile = (selected?: File) => {
    setLocalError(null)
    if (!selected) {
      setFile(null)
      return
    }
    if (!selected.name.toLowerCase().endsWith(".csv")) {
      setFile(null)
      setLocalError(
        "Choose a CSV file. Spreadsheet and archive formats are not accepted.",
      )
      return
    }
    if (selected.size > MAX_FILE_BYTES) {
      setFile(null)
      setLocalError("The file is larger than the 10 MiB upload limit.")
      return
    }
    setFile(selected)
  }

  if (!canImport) {
    return (
      <div className="space-y-8">
        <PageHeader
          eyebrow="Data onboarding"
          title="New import"
          description="Viewer accounts have read-only access to import results and the directory."
        />
        <div className="surface-card flex items-start gap-3 border-amber-200 bg-amber-50 p-5 text-amber-900">
          <ShieldCheck className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
          <p className="text-sm leading-6">
            Ask an administrator to assign the operator role if you need to
            upload and confirm imports.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Step 1 of 4"
        title="Upload contact data"
        description="The file is stored privately and parsed only after upload. You will map columns and validate every row before any contact is created."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section className="surface-card p-6" aria-labelledby="upload-heading">
          <h2 id="upload-heading" className="text-lg font-semibold">
            Choose a CSV
          </h2>
          <label
            htmlFor={inputId}
            className="mt-5 flex min-h-64 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-primary/30 bg-primary/[0.025] px-6 text-center transition hover:border-primary/60 hover:bg-primary/[0.045] focus-within:ring-2 focus-within:ring-ring"
          >
            <span className="grid size-14 place-items-center rounded-2xl bg-primary/10 text-primary">
              {file ? (
                <FileCheck2 className="size-7" />
              ) : (
                <FileUp className="size-7" />
              )}
            </span>
            <span className="mt-4 font-semibold">
              {file ? file.name : "Select a file to upload"}
            </span>
            <span className="mt-1 text-sm text-muted-foreground">
              UTF-8 CSV with optional BOM · maximum 10 MiB · up to 10,000 data
              rows
            </span>
            {file && (
              <span className="mt-3 rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
                {(file.size / 1024).toFixed(1)} KiB
              </span>
            )}
            <input
              id={inputId}
              className="sr-only"
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => chooseFile(event.target.files?.[0])}
            />
          </label>

          {(localError || upload.isError) && (
            <div
              role="alert"
              className="mt-4 flex gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
            >
              <AlertCircle className="mt-0.5 size-4 shrink-0" />
              <span>{localError || extractErrorMessage(upload.error)}</span>
            </div>
          )}

          <div className="mt-6 flex justify-end">
            <Button
              size="lg"
              disabled={!file || upload.isPending}
              onClick={() => file && upload.mutate(file)}
            >
              {upload.isPending ? "Uploading…" : "Upload and map columns"}
            </Button>
          </div>
        </section>

        <aside className="space-y-4">
          <div className="surface-card p-5">
            <h2 className="font-semibold">Required columns</h2>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li>
                <code className="text-foreground">email</code>
              </li>
              <li>
                <code className="text-foreground">first_name</code>
              </li>
              <li>
                <code className="text-foreground">last_name</code>
              </li>
            </ul>
          </div>
          <div className="surface-card p-5">
            <h2 className="font-semibold">Optional columns</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Company, two-letter country code, and an external ID can be mapped
              during the next step.
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}
