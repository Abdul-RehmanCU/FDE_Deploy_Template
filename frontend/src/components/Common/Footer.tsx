import { brandName } from "@/config/runtime"

export function Footer() {
  return (
    <footer className="border-t px-6 py-4">
      <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
        <p className="text-sm text-muted-foreground">
          {brandName} · Customer operations
        </p>
        <p className="text-xs text-muted-foreground">
          Controlled delivery · Observable by design
        </p>
      </div>
    </footer>
  )
}
