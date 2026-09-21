import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function pct(x: number | null | undefined, digits = 1): string {
  if (x == null || isNaN(x)) return '—'
  return (100 * x).toFixed(digits) + '%'
}

export function num(x: number | null | undefined, digits = 2): string {
  if (x == null || isNaN(x)) return '—'
  return Number(x).toFixed(digits)
}

/**
 * Resolve a path relative to the app root (docs/) for data/ files.
 * Works in both dev (Vite server) and production (deployed from docs/).
 */
export function dataUrl(name: string): string {
  const base = import.meta.env.BASE_URL
  return `${base}data/${name}`
}
