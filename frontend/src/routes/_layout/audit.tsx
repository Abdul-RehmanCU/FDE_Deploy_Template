import { useInfiniteQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { AlertTriangle, RefreshCw, Search, ShieldCheck } from "lucide-react"
import { useDeferredValue, useState } from "react"
import { UsersService } from "@/client"
import { EmptyState } from "@/components/Common/EmptyState"
import { LoadingState } from "@/components/Common/LoadingState"
import { PageHeader } from "@/components/Common/PageHeader"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { fdeApi } from "@/features/api/fdeApi"

export const Route = createFileRoute("/_layout/audit")({
  component: AuditPage,
  beforeLoad: async () => {
    const { data } = await UsersService.readUserMe()
    const user = data as typeof data & { role?: string }
    if (user.role !== "admin" && !user.is_superuser) {
      throw redirect({ to: "/" })
    }
  },
  head: () => ({ meta: [{ title: "Audit activity · FDE Deploy" }] }),
})

function AuditPage() {
  const [filter, setFilter] = useState("")
  const action = useDeferredValue(filter.trim())
  const events = useInfiniteQuery({
    queryKey: ["audit-events", action],
    queryFn: ({ pageParam }) =>
      fdeApi.listAuditEvents(action || undefined, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  })
  const rows = events.data?.pages.flatMap((page) => page.data) ?? []

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Audit activity"
        description="Review security and operational actions without exposing contact payloads or credential material."
      />
      <div className="surface-card p-4">
        <label htmlFor="audit-action" className="sr-only">
          Filter by action
        </label>
        <div className="relative max-w-lg">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            id="audit-action"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Filter by exact action"
            className="pl-9"
          />
        </div>
      </div>

      {events.isPending ? (
        <LoadingState label="Loading audit activity" />
      ) : events.isError ? (
        <EmptyState
          icon={AlertTriangle}
          title="Audit activity could not be loaded"
          description="The audit request failed. No application data was changed."
          action={
            <Button variant="outline" onClick={() => events.refetch()}>
              <RefreshCw className="size-4" />
              Retry
            </Button>
          }
        />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={ShieldCheck}
          title={
            action ? "No matching audit events" : "No audit events recorded"
          }
          description={
            action
              ? "Clear the action filter or enter another exact action name."
              : "Administrative and import actions appear here as they occur."
          }
        />
      ) : (
        <section
          className="surface-card overflow-hidden"
          aria-label="Audit events"
        >
          <div className="divide-y">
            {rows.map((event) => (
              <article
                key={event.id}
                className="grid gap-3 p-5 text-sm md:grid-cols-[190px_minmax(0,1fr)_220px] md:items-start"
              >
                <time
                  className="text-muted-foreground"
                  dateTime={event.created_at}
                >
                  {new Intl.DateTimeFormat(undefined, {
                    dateStyle: "medium",
                    timeStyle: "medium",
                  }).format(new Date(event.created_at))}
                </time>
                <div>
                  <p className="font-semibold">
                    {event.action.replaceAll("_", " ")}
                  </p>
                  <p className="mt-1 text-muted-foreground">
                    {event.resource_type}
                    {event.resource_id ? ` · ${event.resource_id}` : ""}
                  </p>
                  {Object.keys(event.metadata_json).length > 0 && (
                    <p className="mt-2 break-words rounded-lg bg-muted/50 p-2 font-mono text-xs text-muted-foreground">
                      {Object.entries(event.metadata_json)
                        .map(([key, value]) => `${key}=${String(value)}`)
                        .join(" · ")}
                    </p>
                  )}
                </div>
                <dl className="text-xs text-muted-foreground">
                  <div>
                    <dt className="inline font-medium text-foreground">
                      Actor:{" "}
                    </dt>
                    <dd className="inline">{event.actor_id || "system"}</dd>
                  </div>
                  <div className="mt-1">
                    <dt className="inline font-medium text-foreground">
                      Request:{" "}
                    </dt>
                    <dd className="inline break-all">
                      {event.request_id || "not recorded"}
                    </dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
          {events.hasNextPage && (
            <div className="flex justify-center border-t p-4">
              <Button
                variant="outline"
                disabled={events.isFetchingNextPage}
                onClick={() => events.fetchNextPage()}
              >
                {events.isFetchingNextPage ? "Loading…" : "Load older events"}
              </Button>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
