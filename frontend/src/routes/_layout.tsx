import {
  createFileRoute,
  Outlet,
  redirect,
  useRouterState,
} from "@tanstack/react-router"
import { CircleCheck, Cloud } from "lucide-react"

import { Footer } from "@/components/Common/Footer"
import AppSidebar from "@/components/Sidebar/AppSidebar"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({
        to: "/login",
      })
    }
  },
})

function Layout() {
  const path = useRouterState({ select: (state) => state.location.pathname })
  const section =
    path === "/"
      ? "Overview"
      : path.split("/").filter(Boolean)[0]?.replace(/-/g, " ") || "Workspace"

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center justify-between gap-3 border-b bg-background/95 px-4 backdrop-blur md:px-8">
          <div className="flex min-w-0 items-center gap-3">
          <SidebarTrigger className="-ml-1 text-muted-foreground" />
            <div className="h-5 w-px bg-border" aria-hidden="true" />
            <p className="truncate text-sm font-medium capitalize">{section}</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="hidden items-center gap-1.5 rounded-full border bg-card px-2.5 py-1 sm:flex">
              <Cloud className="size-3.5" aria-hidden="true" />
              Customer environment
            </span>
            <span className="flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-emerald-700">
              <CircleCheck className="size-3.5" aria-hidden="true" />
              Connected
            </span>
          </div>
        </header>
        <main id="main-content" className="flex-1 p-4 md:p-8" tabIndex={-1}>
          <div className="mx-auto max-w-[1440px]">
            <Outlet />
          </div>
        </main>
        <Footer />
      </SidebarInset>
    </SidebarProvider>
  )
}
