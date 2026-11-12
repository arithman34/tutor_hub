import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'

import { ApiError } from '../api/client'

/** Props that link an input to its Field's error message for screen readers. */
export function describedBy(id: string, error?: string) {
  return { id, 'aria-invalid': error ? true : undefined, 'aria-describedby': error ? `${id}-error` : undefined }
}

/**
 * Show Django's validation errors (a 400 like {"first_name": ["..."]}) on
 * the matching form fields. Returns a message for anything that isn't tied
 * to a field, or null when every error found its field.
 */
export function applyServerErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly Path<T>[],
): string | null {
  if (!(error instanceof ApiError)) return 'Something went wrong. Please try again.'
  if (error.status !== 400 || !error.body || typeof error.body !== 'object') return error.message

  const leftover: string[] = []
  for (const [key, value] of Object.entries(error.body)) {
    const message = Array.isArray(value) ? value.join(' ') : String(value)
    if ((fields as readonly string[]).includes(key)) {
      setError(key as Path<T>, { type: 'server', message })
    } else {
      leftover.push(message)
    }
  }
  return leftover.length ? leftover.join(' ') : null
}
