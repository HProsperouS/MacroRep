import type { ReactNode } from "react"

type PageHeaderProps = {
  eyebrow?: string
  title: string
  actions?: ReactNode
}

export function PageHeader({ eyebrow, title, actions }: PageHeaderProps) {
  return (
    <header className="flex items-center justify-between gap-4">
      <div className="flex flex-col gap-1">
        {eyebrow && (
          <span className="text-[11px] font-semibold tracking-widest text-muted-foreground uppercase">{eyebrow}</span>
        )}
        <h1 className="text-2xl font-semibold md:text-3xl">{title}</h1>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  )
}
