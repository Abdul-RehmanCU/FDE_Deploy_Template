import type { LucideIcon } from "lucide-react"

interface MetricCardProps {
  label: string
  value: string | number
  detail: string
  icon: LucideIcon
  tone?: "blue" | "emerald" | "amber" | "rose"
}

const tones = {
  blue: "bg-blue-50 text-blue-700",
  emerald: "bg-emerald-50 text-emerald-700",
  amber: "bg-amber-50 text-amber-700",
  rose: "bg-rose-50 text-rose-700",
}

export function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = "blue",
}: MetricCardProps) {
  return (
    <article className="surface-card p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p>
        </div>
        <span className={`grid size-10 place-items-center rounded-xl ${tones[tone]}`}>
          <Icon className="size-5" aria-hidden="true" />
        </span>
      </div>
      <p className="mt-4 text-xs leading-5 text-muted-foreground">{detail}</p>
    </article>
  )
}
