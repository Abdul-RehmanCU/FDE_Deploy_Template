import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { Activity, ArrowRight, Search } from "lucide-react"
import { useState } from "react"

import { EmptyState } from "@/components/Common/EmptyState"
import { PageHeader } from "@/components/Common/PageHeader"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export const Route = createFileRoute("/_layout/jobs/")({
  component: JobsLookupPage,
  head: () => ({ meta: [{ title: "Jobs · FDE Deploy" }] }),
})

function JobsLookupPage() {
  const navigate = useNavigate()
  const [jobId, setJobId] = useState("")

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Background processing"
        title="Job status"
        description="Open a durable validation or confirmation job. Job links are also available from each import after work starts."
      />
      <div className="surface-card p-5">
        <form
          className="flex flex-col gap-3 sm:flex-row"
          onSubmit={(event) => {
            event.preventDefault()
            if (jobId.trim()) {
              navigate({ to: "/jobs/$jobId", params: { jobId: jobId.trim() } })
            }
          }}
        >
          <label htmlFor="job-id" className="sr-only">Job ID</label>
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input id="job-id" value={jobId} onChange={(event) => setJobId(event.target.value)} placeholder="Paste a job ID" className="pl-9" />
          </div>
          <Button type="submit" disabled={!jobId.trim()}>
            Open job<ArrowRight className="size-4" />
          </Button>
        </form>
      </div>
      <EmptyState
        icon={Activity}
        title="Jobs belong to imports"
        description="Open an import to validate rows, confirm accepted contacts, retry transient failures, or inspect the latest job link."
      />
    </div>
  )
}
