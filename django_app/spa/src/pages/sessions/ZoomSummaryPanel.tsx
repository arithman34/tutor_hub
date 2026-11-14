import { useState } from 'react'

import type { ZoomNotes } from '../../api/types'
import { buttonPrimary, buttonSecondary } from '../../components/ui'
import { useZoomStatus } from '../connections/queries'
import { useZoomFetch, useZoomParse } from './queries'

/**
 * Paste a Zoom AI summary, or fetch it from Zoom for a saved session, and have
 * it turned into session notes. The panel only fills the form (via onParsed);
 * nothing is saved until the form is.
 */
export function ZoomSummaryPanel({
  sessionId,
  initialSummary = '',
  onParsed,
}: {
  /** A saved session, which can fetch its summary from Zoom when Zoom is connected. */
  sessionId?: string
  initialSummary?: string
  onParsed: (notes: ZoomNotes, summary: string, meetingUuid: string | null) => void
}) {
  const [summary, setSummary] = useState(initialSummary)
  // The Zoom meeting a fetched summary came from. Typing over the summary drops it.
  const [meetingUuid, setMeetingUuid] = useState<string | null>(null)
  const zoom = useZoomParse()
  const zoomStatus = useZoomStatus({ enabled: Boolean(sessionId) })
  const fetchSummary = useZoomFetch(sessionId ?? '')
  const canFetch = Boolean(sessionId) && zoomStatus.data?.connected

  function parse(text: string, uuid: string | null) {
    if (!text) return
    zoom.mutate(text, { onSuccess: (notes) => onParsed(notes, text, uuid) })
  }

  function fetchFromZoom() {
    zoom.reset()
    fetchSummary.mutate(undefined, {
      onSuccess: (fetched) => {
        setSummary(fetched.summary)
        setMeetingUuid(fetched.meeting_uuid)
        parse(fetched.summary, fetched.meeting_uuid)
      },
    })
  }

  const busy = zoom.isPending || fetchSummary.isPending

  return (
    <div className="alert alert-blue space-y-3 rounded-xl p-4">
      <label htmlFor="zoom-summary" className="block text-sm font-medium text-blue-900 dark:text-blue-200">
        {canFetch ? 'Fetch or paste your Zoom AI summary' : 'Paste your Zoom AI summary'}
      </label>
      <p className="text-xs text-blue-700 dark:text-blue-300">It's sent to AI to fill in the notes below, which you can then edit.</p>
      <textarea
        id="zoom-summary"
        rows={8}
        value={summary}
        onChange={(event) => {
          setSummary(event.target.value)
          setMeetingUuid(null)
        }}
        placeholder="Paste the full Zoom AI summary here…"
        className="input resize-y"
      />
      <div className="flex flex-wrap items-center gap-3">
        {canFetch && (
          <button type="button" onClick={fetchFromZoom} disabled={busy} className={buttonSecondary}>
            {fetchSummary.isPending ? 'Fetching…' : 'Fetch from Zoom'}
          </button>
        )}
        <button type="button" onClick={() => parse(summary.trim(), meetingUuid)} disabled={busy || !summary.trim()} className={buttonPrimary}>
          {zoom.isPending ? 'Parsing…' : 'Parse with AI'}
        </button>
        {zoom.isSuccess && (
          <span role="status" className="text-xs text-slate-600 dark:text-slate-300">
            Done. Review and edit the notes below.
          </span>
        )}
        {fetchSummary.isError && (
          <span role="alert" className="text-xs text-red-600 dark:text-red-400">
            {fetchSummary.error.message}
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
