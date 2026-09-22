import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { AlertTriangle, ArrowLeft, Clock3, RefreshCw } from "lucide-react"

import { EmptyState } from "@/components/Common/EmptyState"
import { LoadingState } from "@/components/Common/LoadingState"
import { PageHeader } from "@/components/Common/PageHeader"
import { StatusBadge } from "@/components/Common/StatusBadge"
import { Button } from "@/components/ui/button"
import { fdeApi } from "@/features/api/fdeApi"

export const Route = createFileRoute("/_layout/jobs/$jobId")({
  component: JobDetailPage,
  head: () => ({ meta: [{ title: "Job detail · FDE Deploy" }] }),
})

function JobDetailPage() {
  const { jobId } = Route.useParams()
  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => fdeApi.getJob(jobId),
    refetchInterval: (query) =>
      ["queued", "running", "cancel_requested"].includes(
        query.state.data?.status ?? "",
      )
        ? 2_000
        : false,
  })
  const attempts = useQuery({
    queryKey: ["job-attempts", jobId],
    queryFn: () => fdeApi.listJobAttempts(jobId),
  })

  if (job.isPending || attempts.isPending) {
    return <LoadingState label="Loading job status" />
  }
  if (job.isError || attempts.isError) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Job could not be loaded"
        description="Check the job ID and your access, then retry."
        action={
          <Button
            variant="outline"
            onClick={() => {
              job.refetch()
              attempts.refetch()
            }}
          >
            <RefreshCw className="size-4" />
            Retry
          </Button>
        }
      />
    )
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Background processing"
        title={`${job.data.kind.replaceAll("_", " ")} job`}
        description={`Attempt ${job.data.attempt_count} of ${job.data.max_attempts}. Status comes from PostgreSQL durable state.`}
        actions={<StatusBadge status={job.data.status} />}
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="surface-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            Created
          </p>
          <p className="mt-2 text-sm font-medium">
            {formatTime(job.data.created_at)}
          </p>
        </div>
        <div className="surface-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            Started
          </p>
          <p className="mt-2 text-sm font-medium">
            {formatTime(job.data.started_at)}
          </p>
        </div>
        <div className="surface-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            Finished
          </p>
          <p className="mt-2 text-sm font-medium">
            {formatTime(job.data.finished_at)}
          </p>
        </div>
        <div className="surface-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            Attempts
          </p>
          <p className="mt-2 text-2xl font-semibold">
            {job.data.attempt_count}
          </p>
        </div>
      </div>

      {job.data.error_message && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <strong>{job.data.error_code || "Job failed"}:</strong>{" "}
          {job.data.error_message}
        </div>
      )}

      <section
        className="surface-card overflow-hidden"
        aria-labelledby="attempts-heading"
      >
        <div className="border-b p-5">
          <h2 id="attempts-heading" className="font-semibold">
            Attempt history
          </h2>
          <p className="text-sm text-muted-foreground">
            Bounded retries are recorded separately.
          </p>
        </div>
        {attempts.data.data.length === 0 ? (
          <div className="p-5">
            <EmptyState
              icon={Clock3}
              title="No attempt has started"
              description="The job is waiting to be claimed by a worker."
            />
          </div>
        ) : (
          <ol className="divide-y">
            {attempts.data.data.map((attempt) => (
              <li
                key={attempt.attempt_number}
                className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="font-medium">
                    Attempt {attempt.attempt_number}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {formatTime(attempt.started_at)} →{" "}
                    {formatTime(attempt.finished_at)}
                  </p>
                  {attempt.error_message && (
                    <p className="mt-2 text-sm text-red-700">
                      {attempt.error_message}
                    </p>
                  )}
                </div>
                <StatusBadge status={attempt.status} />
              </li>
            ))}
          </ol>
        )}
      </section>

      <Button variant="outline" asChild>
        <Link to="/imports/$importId" params={{ importId: job.data.import_id }}>
          <ArrowLeft className="size-4" />
          Back to import
        </Link>
      </Button>
    </div>
  )
}

function formatTime(value: string | null) {
  return value
    ? new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "Not yet"
}
