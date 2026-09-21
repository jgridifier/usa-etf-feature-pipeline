import { cn } from '../../lib/utils'

interface CardProps {
  children: React.ReactNode
  className?: string
  muted?: boolean
  interactive?: boolean
}

export function Card({ children, className, muted, interactive }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-surface shadow-card',
        'bg-[image:var(--card-shine)] bg-card-shine',
        interactive && 'transition-all hover:border-border-bright hover:shadow-glow hover:bg-raised cursor-pointer',
        muted && 'opacity-50 pointer-events-none',
        className,
      )}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('mb-3', className)}>{children}</div>
}

export function CardTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return <h3 className={cn('text-base font-semibold text-ink', className)}>{children}</h3>
}

export function CardContent({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('text-sm text-body space-y-1', className)}>{children}</div>
}
