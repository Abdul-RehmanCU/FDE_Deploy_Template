import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import {
  AlertTriangle,
  Copy,
  KeyRound,
  Plus,
  RefreshCw,
  Users,
} from "lucide-react"
import { type FormEvent, useEffect, useState } from "react"

import { UsersService } from "@/client"
import { EmptyState } from "@/components/Common/EmptyState"
import { LoadingState } from "@/components/Common/LoadingState"
import { PageHeader } from "@/components/Common/PageHeader"
import { StatusBadge } from "@/components/Common/StatusBadge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { fdeApi } from "@/features/api/fdeApi"
import type { UserPublic, UserRole } from "@/features/api/types"
import { extractErrorMessage } from "@/utils"

export const Route = createFileRoute("/_layout/admin")({
  component: AdminPage,
  beforeLoad: async () => {
    const { data } = await UsersService.readUserMe()
    const user = data as typeof data & { role?: string }
    if (user.role !== "admin" && !user.is_superuser) {
      throw redirect({ to: "/" })
    }
  },
  head: () => ({ meta: [{ title: "Users · FDE Deploy" }] }),
})

function AdminPage() {
  const queryClient = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<UserPublic | null>(null)
  const [temporaryPassword, setTemporaryPassword] = useState<string | null>(
    null,
  )
  const users = useQuery({
    queryKey: ["users"],
    queryFn: () => fdeApi.listUsers(),
  })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["users"] })
  const password = useMutation({
    mutationFn: (id: string) => fdeApi.issueTemporaryPassword(id),
    onSuccess: (result) => setTemporaryPassword(result.temporary_password),
  })

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Users and roles"
        description="Create named accounts, assign least-privilege roles, disable access, and issue one-time temporary passwords."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" />
            Add user
          </Button>
        }
      />

      {users.isPending ? (
        <LoadingState label="Loading users" />
      ) : users.isError ? (
        <EmptyState
          icon={AlertTriangle}
          title="Users could not be loaded"
          description="The administrator request failed."
          action={
            <Button variant="outline" onClick={() => users.refetch()}>
              <RefreshCw className="size-4" />
              Retry
            </Button>
          }
        />
      ) : users.data.data.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No managed users"
          description="Create an operator or viewer account for this installation."
          action={
            <Button onClick={() => setCreating(true)}>Add first user</Button>
          }
        />
      ) : (
        <section
          className="surface-card overflow-hidden"
          aria-label="Managed users"
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/45 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 font-medium">User</th>
                  <th className="px-5 py-3 font-medium">Role</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Password</th>
                  <th className="px-5 py-3">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {users.data.data.map((user) => (
                  <tr key={user.id} className="hover:bg-muted/25">
                    <td className="px-5 py-4">
                      <p className="font-medium">
                        {user.full_name || "Unnamed user"}
                      </p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {user.email}
                      </p>
                    </td>
                    <td className="px-5 py-4 capitalize">{user.role}</td>
                    <td className="px-5 py-4">
                      <StatusBadge
                        status={user.is_active ? "active" : "disabled"}
                      />
                    </td>
                    <td className="px-5 py-4 text-muted-foreground">
                      {user.must_change_password
                        ? "Change required"
                        : "Current"}
                    </td>
                    <td className="px-5 py-4 text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => password.mutate(user.id)}
                          disabled={password.isPending}
                        >
                          <KeyRound className="size-3.5" />
                          Temporary password
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setEditing(user)}
                        >
                          Edit
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {password.isError && (
        <p
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
        >
          {extractErrorMessage(password.error)}
        </p>
      )}
      <CreateUserDialog
        open={creating}
        setOpen={setCreating}
        onCreated={(value) => {
          setTemporaryPassword(value)
          refresh()
        }}
      />
      <EditUserDialog user={editing} setUser={setEditing} onSaved={refresh} />
      <TemporaryPasswordDialog
        password={temporaryPassword}
        onClose={() => setTemporaryPassword(null)}
      />
    </div>
  )
}

function CreateUserDialog({
  open,
  setOpen,
  onCreated,
}: {
  open: boolean
  setOpen: (open: boolean) => void
  onCreated: (password: string) => void
}) {
  const [email, setEmail] = useState("")
  const [fullName, setFullName] = useState("")
  const [role, setRole] = useState<UserRole>("viewer")
  const create = useMutation({
    mutationFn: () =>
      fdeApi.createUser({ email, full_name: fullName || null, role }),
    onSuccess: (result) => {
      setOpen(false)
      setEmail("")
      setFullName("")
      setRole("viewer")
      onCreated(result.temporary_password)
    },
  })
  const submit = (event: FormEvent) => {
    event.preventDefault()
    create.mutate()
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a user</DialogTitle>
          <DialogDescription>
            A temporary password is generated and shown once.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={submit}>
          <label
            htmlFor="new-user-email"
            className="grid gap-2 text-sm font-medium"
          >
            Email
            <Input
              id="new-user-email"
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label
            htmlFor="new-user-name"
            className="grid gap-2 text-sm font-medium"
          >
            Full name
            <Input
              id="new-user-name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
            />
          </label>
          <label className="grid gap-2 text-sm font-medium">
            Role
            <select
              className="h-10 rounded-md border bg-background px-3"
              value={role}
              onChange={(event) => setRole(event.target.value as UserRole)}
            >
              <option value="viewer">Viewer</option>
              <option value="operator">Operator</option>
              <option value="admin">Administrator</option>
            </select>
          </label>
          {create.isError && (
            <p role="alert" className="text-sm text-red-700">
              {extractErrorMessage(create.error)}
            </p>
          )}
          <DialogFooter>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create user"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function EditUserDialog({
  user,
  setUser,
  onSaved,
}: {
  user: UserPublic | null
  setUser: (user: UserPublic | null) => void
  onSaved: () => Promise<void>
}) {
  const [role, setRole] = useState<UserRole>("viewer")
  const [active, setActive] = useState(true)
  const update = useMutation({
    mutationFn: () =>
      user
        ? fdeApi.updateUser(user.id, { role, is_active: active })
        : Promise.reject(new Error("No user selected")),
    onSuccess: async () => {
      setUser(null)
      await onSaved()
    },
  })
  useEffect(() => {
    if (user) {
      setRole(user.role)
      setActive(user.is_active)
    }
  }, [user])
  const open = user !== null
  const openChange = (next: boolean) => {
    if (!next) setUser(null)
  }
  return (
    <Dialog open={open} onOpenChange={openChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit access</DialogTitle>
          <DialogDescription>{user?.email}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <label className="grid gap-2 text-sm font-medium">
            Role
            <select
              className="h-10 rounded-md border bg-background px-3"
              value={role}
              onChange={(event) => setRole(event.target.value as UserRole)}
            >
              <option value="viewer">Viewer</option>
              <option value="operator">Operator</option>
              <option value="admin">Administrator</option>
            </select>
          </label>
          <label className="flex items-center gap-3 rounded-xl border p-3 text-sm">
            <input
              type="checkbox"
              checked={active}
              onChange={(event) => setActive(event.target.checked)}
            />
            Account is active
          </label>
          {update.isError && (
            <p role="alert" className="text-sm text-red-700">
              {extractErrorMessage(update.error)}
            </p>
          )}
          <DialogFooter>
            <Button onClick={() => update.mutate()} disabled={update.isPending}>
              {update.isPending ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function TemporaryPasswordDialog({
  password,
  onClose,
}: {
  password: string | null
  onClose: () => void
}) {
  return (
    <Dialog
      open={password !== null}
      onOpenChange={(open) => !open && onClose()}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Temporary password</DialogTitle>
          <DialogDescription>
            Copy this password now. It will not be shown again and the user must
            change it after signing in.
          </DialogDescription>
        </DialogHeader>
        {password && (
          <div className="flex items-center gap-2 rounded-xl border bg-muted/50 p-3">
            <code className="min-w-0 flex-1 break-all text-sm">{password}</code>
            <Button
              size="icon"
              variant="outline"
              aria-label="Copy temporary password"
              onClick={() => navigator.clipboard.writeText(password)}
            >
              <Copy className="size-4" />
            </Button>
          </div>
        )}
        <DialogFooter>
          <Button onClick={onClose}>I saved it</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
