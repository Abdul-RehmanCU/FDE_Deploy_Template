import { Link } from "@tanstack/react-router"
import { DatabaseZap } from "lucide-react"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const content =
    variant === "responsive" ? (
      <>
        <span
          className={cn(
            "flex items-center gap-3 group-data-[collapsible=icon]:hidden",
            className,
          )}
        >
          <span className="grid size-9 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <DatabaseZap className="size-5" aria-hidden="true" />
          </span>
          <span className="leading-tight">
            <span className="block text-sm font-semibold tracking-tight">
              FDE Deploy
            </span>
            <span className="block text-[11px] text-muted-foreground">
              Customer operations
            </span>
          </span>
        </span>
        <span
          className={cn(
            "hidden size-9 place-items-center rounded-xl bg-primary text-primary-foreground group-data-[collapsible=icon]:grid",
            className,
          )}
        >
          <DatabaseZap className="size-5" aria-label="FDE Deploy" />
        </span>
      </>
    ) : (
      <span className={cn("flex items-center gap-3", className)}>
        <span className="grid size-10 place-items-center rounded-xl bg-primary text-primary-foreground">
          <DatabaseZap className="size-5" aria-hidden="true" />
        </span>
        {variant === "full" && (
          <span className="text-lg font-semibold tracking-tight">
            FDE Deploy
          </span>
        )}
      </span>
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
