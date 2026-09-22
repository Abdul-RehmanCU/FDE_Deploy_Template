import { useInfiniteQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  AlertTriangle,
  ContactRound,
  Mail,
  RefreshCw,
  Search,
} from "lucide-react"
import { useDeferredValue, useState } from "react"

import { EmptyState } from "@/components/Common/EmptyState"
import { LoadingState } from "@/components/Common/LoadingState"
import { PageHeader } from "@/components/Common/PageHeader"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { fdeApi } from "@/features/api/fdeApi"
import type { ContactPublic } from "@/features/api/types"

export const Route = createFileRoute("/_layout/directory")({
  component: DirectoryPage,
  head: () => ({ meta: [{ title: "Directory · FDE Deploy" }] }),
})

function DirectoryPage() {
  const [search, setSearch] = useState("")
  const [selected, setSelected] = useState<ContactPublic | null>(null)
  const deferredSearch = useDeferredValue(search.trim())
  const contacts = useInfiniteQuery({
    queryKey: ["contacts", deferredSearch],
    queryFn: ({ pageParam }) =>
      fdeApi.listContacts(deferredSearch || undefined, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  })
  const rows = contacts.data?.pages.flatMap((page) => page.data) ?? []

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Customer data"
        title="Contact directory"
        description="Search normalized contacts in this customer installation. Results are ordered by creation time and paginated with opaque cursors."
      />

      <div className="surface-card p-4">
        <label htmlFor="directory-search" className="sr-only">
          Search contacts
        </label>
        <div className="relative max-w-xl">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            id="directory-search"
            type="search"
            value={search}
            maxLength={200}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search name, email, company, or external ID"
            className="pl-9"
          />
        </div>
      </div>

      {contacts.isPending ? (
        <LoadingState label="Loading contacts" />
      ) : contacts.isError ? (
        <EmptyState
          icon={AlertTriangle}
          title="Directory could not be loaded"
          description="The search request failed. No contact data was changed."
          action={
            <Button variant="outline" onClick={() => contacts.refetch()}>
              <RefreshCw className="size-4" />
              Retry
            </Button>
          }
        />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={ContactRound}
          title={
            deferredSearch ? "No matching contacts" : "The directory is empty"
          }
          description={
            deferredSearch
              ? "Try a broader name, email address, company, or external ID."
              : "Contacts appear here only after a validated import is explicitly confirmed."
          }
        />
      ) : (
        <section
          className="surface-card overflow-hidden"
          aria-label="Contact results"
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/45 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Email</th>
                  <th className="px-5 py-3 font-medium">Company</th>
                  <th className="px-5 py-3 font-medium">Country</th>
                  <th className="px-5 py-3 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((contact) => (
                  <tr key={contact.id} className="hover:bg-muted/25">
                    <td className="px-5 py-4 font-medium">
                      {contact.first_name} {contact.last_name}
                    </td>
                    <td className="px-5 py-4">
                      <a
                        className="inline-flex items-center gap-1.5 text-primary hover:underline"
                        href={`mailto:${contact.email}`}
                      >
                        <Mail className="size-3.5" aria-hidden="true" />
                        {contact.email}
                      </a>
                    </td>
                    <td className="px-5 py-4 text-muted-foreground">
                      {contact.company || "—"}
                    </td>
                    <td className="px-5 py-4 text-muted-foreground">
                      {contact.country_code || "—"}
                    </td>
                    <td className="px-5 py-4 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelected(contact)}
                      >
                        View details
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {contacts.hasNextPage && (
            <div className="flex justify-center border-t p-4">
              <Button
                variant="outline"
                disabled={contacts.isFetchingNextPage}
                onClick={() => contacts.fetchNextPage()}
              >
                {contacts.isFetchingNextPage
                  ? "Loading…"
                  : "Load more contacts"}
              </Button>
            </div>
          )}
        </section>
      )}

      <Dialog
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {selected?.first_name} {selected?.last_name}
            </DialogTitle>
            <DialogDescription>
              Contact record in this installation
            </DialogDescription>
          </DialogHeader>
          {selected && (
            <dl className="grid gap-4 py-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted-foreground">Email</dt>
                <dd className="mt-1 font-medium break-all">{selected.email}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Company</dt>
                <dd className="mt-1 font-medium">
                  {selected.company || "Not provided"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Country</dt>
                <dd className="mt-1 font-medium">
                  {selected.country_code || "Not provided"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">External ID</dt>
                <dd className="mt-1 font-medium">
                  {selected.external_id || "Not provided"}
                </dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-muted-foreground">Created</dt>
                <dd className="mt-1 font-medium">
                  {new Intl.DateTimeFormat(undefined, {
                    dateStyle: "long",
                    timeStyle: "short",
                  }).format(new Date(selected.created_at))}
                </dd>
              </div>
            </dl>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
