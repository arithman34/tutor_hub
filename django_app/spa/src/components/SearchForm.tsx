import { Search, X } from 'lucide-react'
import type { FormEvent } from 'react'

/**
 * The search box at the top of a list: a field with a magnifier, a Search
 * button, and Clear once a search is applied. The page keeps the text
 * (`value`) and decides what searching and clearing do.
 */
export function SearchForm({
  id,
  label,
  placeholder,
  value,
  onChange,
  onSubmit,
  onClear,
  className = 'mb-6',
}: {
  id: string
  label: string
  placeholder: string
  value: string
  onChange: (value: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  /** Shown as a Clear button when there's a search to clear. */
  onClear?: () => void
  className?: string
}) {
  return (
    <form role="search" onSubmit={onSubmit} className={`flex flex-wrap gap-2 ${className}`}>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <div className="relative w-full sm:w-72">
        <Search aria-hidden="true" className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          id={id}
          type="search"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          className="input pl-9"
        />
      </div>
      <button type="submit" className="btn btn-secondary">
        Search
      </button>
      {onClear && (
        <button type="button" onClick={onClear} className="btn btn-secondary">
          <X aria-hidden="true" className="h-4 w-4" />
          Clear
        </button>
      )}
    </form>
  )
}
