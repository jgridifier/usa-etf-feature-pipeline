import { useState, useEffect } from 'react'
import { dataUrl } from '../lib/utils'

type Status = 'idle' | 'loading' | 'ok' | 'error'

export function useJsonData<T>(filename: string) {
  const [data, setData] = useState<T | null>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    fetch(dataUrl(filename), { credentials: 'same-origin' })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status} loading ${filename}`)
        return r.json()
      })
      .then(json => {
        if (!cancelled) {
          setData(json)
          setStatus('ok')
        }
      })
      .catch(err => {
        if (!cancelled) {
          setError(String(err))
          setStatus('error')
        }
      })
    return () => { cancelled = true }
  }, [filename])

  return { data, status, error }
}
