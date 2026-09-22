import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ContactRound,
  FileSpreadsheet,
  FileUp,
  RefreshCw,
} from "lucide-react"

import { EmptyState } from "@/components/Common/EmptyState"
import { LoadingState } from "@/components/Common/LoadingState"
import { MetricCard } from "@/components/Common/MetricCard"
import { PageHeader } from "@/components/Common/PageHeader"
import { StatusBadge } from "@/components/Common/StatusBadge"
import { Button } from "@/components/ui/button"
import { fdeApi } from "@/features/api/fdeApi"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "Overview · FDE Deploy",
      },
    ],
  }),
})

function Dashboard() {
  const dashboard = useQuery({
    queryKey: ["dashboard"],
    queryFn: fdeApi.dashboard,
    refetchInterval: 30_000,
  })
  const imports = useQuery({
    queryKey: ["imports", "recent"],
    queryFn: () => fdeApi.listImports(),
  })

  if (dashboard.isPending || imports.isPending) {
    return <LoadingState label="Loading operational overview" />
  }

  if (dashboard.isError || imports.isError) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="The overview could not be loaded"
        description="The API did not return the current installation summary. Check readiness, then try again."
        action={
          <Button
            variant="outline"
            onClick={() => {
              dashboard.refetch()
              imports.refetch()
            }}
          >
            <RefreshCw className="size-4" />
            Retry
          </Button>
        }
      />
    )
  }

  const summary = dashboard.data
  const activeJobs = Object.entries(summary.jobs_by_status)
    .filter(([status]) =>
      ["queued", "running", "cancel_requested"].includes(status),
    )
    .reduce((total, [, count]) => total + count, 0)

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Customer installation"
        title="Operations overview"
        description="Track contact onboarding, validation quality, and background work from one place. Counts come from durable application state."
        actions={
          <Button asChild>
            <Link to="/imports/new">
              <FileUp className="size-4" />
              New import
            </Link>
          </Button>
        }
      />

      <section
        aria-label="Installation summary"
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        <MetricCard
          label="Contacts"
          value={summary.contacts_total.toLocaleString()}
          detail="Searchable records in this installation"
          icon={ContactRound}
        />
        <MetricCard
          label="Accepted rows"
          value={summary.accepted_rows_total.toLocaleString()}
          detail="Rows that passed the latest validation rules"
          icon={CheckCircle2}
          tone="emerald"
        />
        <MetricCard
          label="Rejected rows"
          value={summary.rejected_rows_total.toLocaleString()}
          detail="Rows retained with actionable validation reasons"
          icon={AlertTriangle}
          tone="rose"
        />
        <MetricCard
          label="Active jobs"
          value={activeJobs}
          detail={`${summary.imports_total.toLocaleString()} import batches recorded`}
          icon={Activity}
          tone="amber"
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <section
          className="surface-card overflow-hidden"
          aria-labelledby="recent-imports-heading"
        >
          <div className="flex items-center justify-between border-b px-5 py-4">
            <div>
              <h2 id="recent-imports-heading" className="font-semibold">
                Recent imports
              </h2>
              <p className="text-sm text-muted-foreground">
                Latest onboarding activity
              </p>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link to="/imports">View all</Link>
            </Button>
          </div>
          {imports.data.data.length === 0 ? (
            <div className="p-5">
              <EmptyState
                icon={FileSpreadsheet}
                title="No imports yet"
                description="Upload a UTF-8 CSV to begin the guided validation and confirmation flow."
                action={
                  <Button asChild>
                    <Link to="/imports/new">Start first import</Link>
                  </Button>
                }
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/45 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-5 py-3 font-medium">File</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 text-right font-medium">
                      Accepted
                    </th>
                    <th className="px-5 py-3 text-right font-medium">Issues</th>
                    <th className="px-5 py-3 font-medium">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {imports.data.data.slice(0, 6).map((item) => (
                    <tr key={item.id} className="hover:bg-muted/25">
                      <td className="max-w-64 px-5 py-4 font-medium">
                        <Link
                          to="/imports/$importId"
                          params={{ importId: item.id }}
                          className="block truncate text-primary hover:underline"
                        >
                          {item.original_filename}
                        </Link>
                      </td>
                      <td className="px-5 py-4">
                        <StatusBadge status={item.status} />
                      </td>
                      <td className="px-5 py-4 text-right tabular-nums">
                        {item.accepted_count}
                      </td>
                      <td className="px-5 py-4 text-right tabular-nums">
                        {item.rejected_count +
                          item.duplicate_count +
                          item.existing_contact_count}
                      </td>
                      <td className="whitespace-nowrap px-5 py-4 text-muted-foreground">
                        {new Intl.DateTimeFormat(undefined, {
                          dateStyle: "medium",
                        }).format(new Date(item.created_at))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <aside
          className="surface-card p-5"
          aria-labelledby="worker-status-heading"
        >
          <h2 id="worker-status-heading" className="font-semibold">
            Job pipeline
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Durable status by queue state
          </p>
          <div className="mt-5 space-y-3">
            {Object.keys(summary.jobs_by_status).length === 0 ? (
              <p className="rounded-xl bg-muted/50 p-4 text-sm text-muted-foreground">
                No background jobs have been recorded.
              </p>
            ) : (
              Object.entries(summary.jobs_by_status).map(([status, count]) => (
                <div
                  key={status}
                  className="flex items-center justify-between gap-3 rounded-xl border p-3"
                >
                  <StatusBadge status={status} />
                  <span className="font-semibold tabular-nums">{count}</span>
                </div>
              ))
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}
