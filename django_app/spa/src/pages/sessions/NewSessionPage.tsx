import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { applyServerErrors } from '../../components/formHelpers'
import { Tabs } from '../../components/Tabs'
import { ErrorMessage, Loading, PageHeader, buttonPrimary, buttonSecondary } from '../../components/ui'
import { useStudents } from '../students/queries'
import type { ZoomNotes } from '../../api/types'
import { useCreateSession } from './queries'
import { DetailsFields, NotesFields } from './SessionFields'
import { ZoomSummaryPanel } from './ZoomSummaryPanel'
import {
  detailsFields,
  detailsSchema,
  detailsToRequest,
  emptyNotes,
  notesSchema,
  notesToRequest,
  type DetailsValues,
  type NotesValues,
} from './sessionForm'

type Mode = 'manual' | 'zoom'
const MODES = [
  { value: 'manual', label: 'Manual' },
  { value: 'zoom', label: 'Zoom summary' },
] as const satisfies readonly { value: Mode; label: string }[]

export function NewSessionPage() {
  const navigate = useNavigate()
  // "Log session" on the sessions list passes the calendar event's details here.
  const [searchParams] = useSearchParams()
  const eventId = searchParams.get('event_id') ?? ''
  const htmlLink = searchParams.get('html_link') ?? ''

  const students = useStudents('')
  const create = useCreateSession()
  const [mode, setMode] = useState<Mode>('manual')
  const [parsedSummary, setParsedSummary] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const details = useForm<DetailsValues>({
    resolver: zodResolver(detailsSchema),
    defaultValues: {
      student: searchParams.get('student_id') ?? '',
      date: searchParams.get('date') ?? '',
      start_time: searchParams.get('start_time') ?? '',
      end_time: searchParams.get('end_time') ?? '',
      is_no_show: false,
    },
  })
  const notes = useForm<NotesValues>({ resolver: zodResolver(notesSchema), defaultValues: emptyNotes })
  const noShow = useWatch({ control: details.control, name: 'is_no_show' })

  function fillFromZoom(parsed: ZoomNotes, summary: string) {
    for (const [field, value] of Object.entries(parsed) as [keyof NotesValues, string][]) {
      notes.setValue(field, value, { shouldDirty: true })
    }
    setParsedSummary(summary)
  }

  function send(detailValues: DetailsValues, noteValues: NotesValues | null) {
    setFormError(null)
    create.mutate(
      {
        ...detailsToRequest(detailValues),
        ...(noteValues && notesToRequest(noteValues)),
        zoom_summary_raw: noteValues ? parsedSummary : null,
        calendar_event_id: eventId || null,
        calendar_html_link: htmlLink || null,
      },
      {
        onSuccess: () => navigate('/sessions'),
        onError: (error) => setFormError(applyServerErrors(error, details.setError, detailsFields)),
      },
    )
  }

  // Validate the details, then the notes, then send one request. A no-show
  // has no notes (they're hidden), so those aren't checked or sent.
  const onSubmit = details.handleSubmit((detailValues) => {
    if (detailValues.is_no_show) return send(detailValues, null)
    return notes.handleSubmit((noteValues) => send(detailValues, noteValues))()
  })

  if (students.isPending) return <Loading>Loading students…</Loading>
  if (students.isError) return <ErrorMessage>Couldn't load your students: {students.error.message}</ErrorMessage>

  return (
    <div>
      <PageHeader title="Log session" backTo="/sessions" />

      <form onSubmit={onSubmit} noValidate className="max-w-2xl space-y-5">
        {eventId && (
          <p className="alert alert-blue">
            Pre-filled from your Google Calendar event.
          </p>
        )}
        {formError && <ErrorMessage>{formError}</ErrorMessage>}

        <DetailsFields form={details} students={students.data} />

        {!noShow && (
          <>
            <Tabs label="How to fill in the notes" options={MODES} value={mode} onChange={setMode} />

            {mode === 'zoom' && <ZoomSummaryPanel onParsed={fillFromZoom} />}

            <NotesFields form={notes} />
          </>
        )}

        <div className="flex gap-3 pt-2">
          <button type="submit" disabled={create.isPending} className={buttonPrimary}>
            {create.isPending ? 'Saving…' : 'Save session'}
          </button>
          <Link to="/sessions" className={buttonSecondary}>
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}
