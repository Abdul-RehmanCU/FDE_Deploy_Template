import {
  Activity,
  ContactRound,
  FileUp,
  Gauge,
  ShieldCheck,
  Users,
} from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type Item, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = [
  { icon: Gauge, title: "Overview", path: "/" },
  { icon: FileUp, title: "Imports", path: "/imports" },
  { icon: ContactRound, title: "Directory", path: "/directory" },
  { icon: Activity, title: "Jobs", path: "/jobs" },
]

export function AppSidebar() {
  const { user: currentUser } = useAuth()

  const role = (currentUser as { role?: string; is_superuser?: boolean } | null)
    ?.role
  const isAdmin = role === "admin" || currentUser?.is_superuser
  const items = isAdmin
    ? [
        ...baseItems,
        { icon: Users, title: "Users", path: "/admin" },
        { icon: ShieldCheck, title: "Audit", path: "/audit" },
      ]
    : baseItems

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="border-b px-4 py-5 group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-0">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
