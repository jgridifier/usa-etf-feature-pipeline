import { cn } from '../../lib/utils'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'sm' | 'md'
}

export function Button({ variant = 'primary', size = 'md', className, children, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50',
        size === 'md' && 'px-4 py-2 text-sm',
        size === 'sm' && 'px-3 py-1.5 text-xs',
        variant === 'primary' && 'bg-accent text-white hover:bg-accent/90 active:bg-accent/80 shadow-sm',
        variant === 'secondary' && 'border border-border text-ink bg-surface hover:bg-raised hover:border-border-bright',
        variant === 'ghost' && 'text-body hover:text-ink hover:bg-raised',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}

interface LinkButtonProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'sm' | 'md'
}

export function LinkButton({ variant = 'primary', size = 'md', className, children, ...props }: LinkButtonProps) {
  return (
    <a
      className={cn(
        'inline-flex items-center justify-center font-medium transition-all no-underline',
        size === 'md' && 'px-4 py-2 text-sm',
        size === 'sm' && 'px-3 py-1.5 text-xs',
        variant === 'primary' && 'bg-accent text-white hover:bg-accent/90 shadow-sm',
        variant === 'secondary' && 'border border-border text-ink bg-surface hover:bg-raised hover:border-border-bright',
        variant === 'ghost' && 'text-body hover:text-ink',
        className,
      )}
      {...props}
    >
      {children}
    </a>
  )
}
