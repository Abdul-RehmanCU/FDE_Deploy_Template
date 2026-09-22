import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { AlertTriangle, FileSpreadsheet, FileUp, RefreshCw } from "lucide-react"

import { EmptyState } from "@/components/Common/EmptyState"
import { LoadingState } from "@/components/Common/LoadingState"
import { PageHeader } from "@/components/Common/PageHeader"
import { StatusBadge } from "@/components/Common/StatusBadge"
import { Button } from "@/components/ui/button"
import { fdeApi } from "@/features/api/fdeApi"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/imports/")({
  component: ImportsPage,
  head: () => ({ meta: [{ title: "Imports · FDE Deploy" }] }),
})

function ImportsPage() {
  const { user } = useAuth()
  const role = (user as { role?: string } | null)?.role
  const canImport = role !== "viewer"
  const imports = useQuery({
    queryKey: ["imports"],
    queryFn: () => fdeApi.listImports(),
  })

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Data onboarding"
        title="Imports"
        description="Upload source data, review validation outcomes, and follow every durable job attempt."
        actions={
          canImport ? (
            <Button asChild>
              <Link to="/imports/new">
                <FileUp className="size-4" />
                New import
              </Link>
            </Button>
          ) : undefined
        }
      />

      {imports.isPending ? (
        <LoadingState label="Loading imports" />
      ) : imports.isError ? (
        <EmptyState
          icon={AlertTriangle}
          title="Imports could not be loaded"
          description="The import history is temporarily unavailable. No data was changed."
          action={
            <Button variant="outline" onClick={() => imports.refetch()}>
              <RefreshCw className="size-4" />
              Retry
            </Button>
          }
        />
      ) : imports.data.data.length === 0 ? (
        <EmptyState
          icon={FileSpreadsheet}
          title="No import history"
          description={
            canImport
              ? "Start with a UTF-8 CSV up to 10 MiB and 10,000 data rows. Validation does not change the directory."
              : "An administrator or operator must start the first contact import."
          }
          action={
            canImport ? (
              <Button asChild>
                <Link to="/imports/new">Upload CSV</Link>
              </Button>
            ) : undefined
          }
        />
      ) : (
        <section className="surface-card overflow-hidden" aria-label="Import history">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/45 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 font-medium">Source file</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 text-right font-medium">Rows</th>
                  <th className="px-5 py-3 text-right font-medium">Accepted</th>
                  <th className="px-5 py-3 text-right font-medium">Issues</th>
                  <th className="px-5 py-3 font-medium">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {imports.data.data.map((item) => (
                  <tr key={item.id} className="hover:bg-muted/25">
                    <td className="max-w-72 px-5 py-4 font-medium">
                      <Link
                        to="/imports/$importId"
                        params={{ importId: item.id }}
                        className="block truncate text-primary hover:underline"
                      >
                        {item.original_filename}
                      </Link>
                    </td>
                    <td className="px-5 py-4"><StatusBadge status={item.status} /></td>
                    <td className="px-5 py-4 text-right tabular-nums">{item.total_rows}</td>
                    <td className="px-5 py-4 text-right tabular-nums">{item.accepted_count}</td>
                    <td className="px-5 py-4 text-right tabular-nums">
                      {item.rejected_count + item.duplicate_count + item.existing_contact_count}
                    </td>
                    <td className="whitespace-nowrap px-5 py-4 text-muted-foreground">
                      {new Intl.DateTimeFormat(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      }).format(new Date(item.created_at))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {imports.data.has_more && (
            <div className="border-t px-5 py-3 text-xs text-muted-foreground">
              Additional history is available through cursor pagination.
            </div>
          )}
        </section>
      )}
    </div>
  )
}
