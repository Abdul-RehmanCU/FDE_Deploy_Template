import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const variants: Record<string, string> = {
  completed: "border-emerald-200 bg-emerald-50 text-emerald-700",
  healthy: "border-emerald-200 bg-emerald-50 text-emerald-700",
  ready: "border-emerald-200 bg-emerald-50 text-emerald-700",
  validating: "border-blue-200 bg-blue-50 text-blue-700",
  processing: "border-blue-200 bg-blue-50 text-blue-700",
  queued: "border-amber-200 bg-amber-50 text-amber-700",
  uploaded: "border-slate-200 bg-slate-50 text-slate-700",
  mapped: "border-indigo-200 bg-indigo-50 text-indigo-700",
  failed: "border-red-200 bg-red-50 text-red-700",
  cancelled: "border-slate-200 bg-slate-100 text-slate-600",
  disabled: "border-slate-200 bg-slate-100 text-slate-600",
  active: "border-emerald-200 bg-emerald-50 text-emerald-700",
}

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase().replaceAll("_", "-")
  return (
    <Badge
      variant="outline"
      className={cn("font-medium capitalize", variants[normalized])}
    >
      {normalized.replaceAll("-", " ")}
    </Badge>
  )
}
