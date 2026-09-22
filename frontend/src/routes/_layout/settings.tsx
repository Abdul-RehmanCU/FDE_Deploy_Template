import { createFileRoute } from "@tanstack/react-router"

import { PageHeader } from "@/components/Common/PageHeader"
import { StatusBadge } from "@/components/Common/StatusBadge"
import ChangePassword from "@/components/UserSettings/ChangePassword"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
  head: () => ({
    meta: [
      {
        title: "Account settings · FDE Deploy",
      },
    ],
  }),
})

function UserSettings() {
  const { user: currentUser } = useAuth()
  if (!currentUser) {
    return null
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Account"
        title="Profile and password"
        description="Review the identity and role assigned by your administrator, or change your password."
      />
      {currentUser.must_change_password && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          You are using a temporary password. Change it before continuing with
          protected operations.
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="surface-card p-6" aria-labelledby="profile-heading">
          <div className="flex items-center justify-between gap-3">
            <h2 id="profile-heading" className="text-lg font-semibold">
              Profile
            </h2>
            <StatusBadge
              status={currentUser.is_active ? "active" : "disabled"}
            />
          </div>
          <dl className="mt-5 space-y-4 text-sm">
            <div>
              <dt className="text-muted-foreground">Full name</dt>
              <dd className="mt-1 font-medium">
                {currentUser.full_name || "Not provided"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Email</dt>
              <dd className="mt-1 break-all font-medium">
                {currentUser.email}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Role</dt>
              <dd className="mt-1 capitalize">{currentUser.role}</dd>
            </div>
          </dl>
          <p className="mt-6 text-xs leading-5 text-muted-foreground">
            An administrator manages profile details, roles, and account status.
          </p>
        </section>
        <section
          className="surface-card p-6"
          aria-labelledby="password-heading"
        >
          <h2 id="password-heading" className="sr-only">
            Password
          </h2>
          <ChangePassword />
        </section>
      </div>
    </div>
  )
}
