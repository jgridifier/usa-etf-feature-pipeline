import { cn } from '../../lib/utils'

interface BadgeProps {
  children: React.ReactNode
  variant?: 'default' | 'quiet' | 'archive' | 'live' | 'pill'
  className?: string
}

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full text-2xs font-medium uppercase tracking-widest',
        variant === 'pill' && 'border border-border px-2 py-0.5 text-muted',
        variant === 'default' && 'bg-accent/10 text-accent px-2 py-0.5 border border-accent/20',
        variant === 'live' && 'bg-up/10 text-up px-2 py-0.5 border border-up/20',
        variant === 'quiet' && 'bg-surface text-muted px-2 py-0.5 border border-border',
        variant === 'archive' && 'bg-down/10 text-down px-2 py-0.5 border border-down/20',
        className,
      )}
    >
      {children}
    </span>
  )
}
