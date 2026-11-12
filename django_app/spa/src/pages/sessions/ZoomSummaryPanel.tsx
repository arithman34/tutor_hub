import { useState } from 'react'

import type { ZoomNotes } from '../../api/types'
import { buttonPrimary } from '../../components/ui'
import { useZoomParse } from './queries'

/**
 * Paste a Zoom AI summary and have it turned into session notes. The panel
 * only fills the form (via onParsed); nothing is saved until the form is.
 */
export function ZoomSummaryPanel({
  initialSummary = '',
  onParsed,
}: {
  initialSummary?: string
  onParsed: (notes: ZoomNotes, summary: string) => void
}) {
  const [summary, setSummary] = useState(initialSummary)
  const zoom = useZoomParse()

  function parse() {
    const text = summary.trim()
    if (!text) return
    zoom.mutate(text, { onSuccess: (notes) => onParsed(notes, text) })
  }

  return (
    <div className="space-y-3 rounded-xl border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-900/20">
      <label htmlFor="zoom-summary" className="block text-sm font-medium text-blue-900 dark:text-blue-200">
        Paste your Zoom AI summary
      </label>
      <p className="text-xs text-blue-700 dark:text-blue-300">It's sent to AI to fill in the notes below, which you can then edit.</p>
      <textarea
        id="zoom-summary"
        rows={8}
        value={summary}
        onChange={(event) => setSummary(event.target.value)}
        placeholder="Paste the full Zoom AI summary here…"
        className="input resize-y"
      />
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={parse} disabled={zoom.isPending || !summary.trim()} className={buttonPrimary}>
          {zoom.isPending ? 'Parsing…' : 'Parse with AI'}
        </button>
        {zoom.isSuccess && (
          <span role="status" className="text-xs text-gray-600 dark:text-gray-300">
            Done. Review and edit the notes below.
          </span>
        )}
        {zoom.isError && (
          <span role="alert" className="text-xs text-red-600 dark:text-red-400">
            Couldn't parse the summary. Try again.
          </span>
        )}
      </div>
    </div>
  )
}
