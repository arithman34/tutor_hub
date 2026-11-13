import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router'

import { ApiError } from '../../api/client'
import type { Session, Student, ZoomNotes } from '../../api/types'
import { applyServerErrors } from '../../components/formHelpers'
import { ErrorMessage, Loading, PageHeader, buttonPrimary, buttonSecondary } from '../../components/ui'
import { formatDate } from '../../format'
import { useStudents } from '../students/queries'
import { useDeleteSession, useSession, useUpdateSession } from './queries'
import { DetailsFields, NotesFields } from './SessionFields'
import { ZoomSummaryPanel } from './ZoomSummaryPanel'
import { zoomOutcomeLabel } from './zoomOutcome'
import {
  detailsFields,
  detailsFromSession,
  detailsSchema,
  detailsToRequest,
  notesFields,
  notesFromSession,
  notesSchema,
  notesToRequest,
  type DetailsValues,
  type NotesValues,
} from './sessionForm'

export function SessionDetailPage() {
  const { sessionId = '' } = useParams()
  const session = useSession(sessionId)
  const students = useStudents('')

  if (session.isPending || students.isPending) return <Loading>Loading session…</Loading>
  if (session.isError) {
    const missing = session.error instanceof ApiError && session.error.status === 404
    return (
      <div>
        <PageHeader title="Session" backTo="/sessions" />
        <ErrorMessage>{missing ? 'That session doesn’t exist, or was deleted.' : `Couldn't load the session: ${session.error.message}`}</ErrorMessage>
      </div>
    )
  }
  if (students.isError) return <ErrorMessage>Couldn't load your students: {students.error.message}</ErrorMessage>

  return <SessionDetail key={session.data.id} session={session.data} students={students.data} />
}

function SessionDetail({ session, students }: { session: Session; students: Student[] }) {
  const navigate = useNavigate()
  const update = useUpdateSession(session.id)
  const remove = useDeleteSession(session.id)
  const [savedPart, setSavedPart] = useState<'details' | 'notes' | null>(null)
  const [detailsError, setDetailsError] = useState<string | null>(null)
  const [notesError, setNotesError] = useState<string | null>(null)

  const student = students.find((candidate) => candidate.id === session.student)
  const details = useForm<DetailsValues>({ resolver: zodResolver(detailsSchema), defaultValues: detailsFromSession(session) })
  const notes = useForm<NotesValues>({ resolver: zodResolver(notesSchema), defaultValues: notesFromSession(session) })
  const [zoomOpen, setZoomOpen] = useState(false)
  // A summary parsed on this page (and the Zoom meeting it was fetched from,
  // if it was), to save along with the notes it produced.
  const [parsedSummary, setParsedSummary] = useState<{ summary: string; meetingUuid: string | null } | null>(null)

  // Clearing un-logs the lesson: the session (its notes, Zoom summary and
  // billing) is removed, and its calendar event shows as Not logged again.
  function clearSession() {
    if (
      !window.confirm(
        'Clear this session? Its notes and Zoom summary are deleted, it stops being billed, and its calendar event goes back to Not logged. This cannot be undone.',
      )
    )
      return
    remove.mutate(undefined, {
      onSuccess: () =>
        navigate('/sessions', { replace: true, state: { notice: 'Session cleared. Its calendar event is back to Not logged.' } }),
    })
  }

  function fillFromZoom(parsed: ZoomNotes, summary: string, meetingUuid: string | null) {
    for (const [field, value] of Object.entries(parsed) as [keyof NotesValues, string][]) {
      notes.setValue(field, value, { shouldDirty: true })
    }
    setParsedSummary({ summary, meetingUuid })
    setSavedPart(null)
  }

  // Each form only sends its own fields (a PATCH), so fixing the time can never
  // wipe the notes, and saving the notes can't move the session.
  const saveDetails = details.handleSubmit((values) => {
    setDetailsError(null)
    update.mutate(detailsToRequest(values), {
      onSuccess: (saved) => {
        details.reset(detailsFromSession(saved))
        setSavedPart('details')
      },
      onError: (error) => setDetailsError(applyServerErrors(error, details.setError, detailsFields)),
    })
  })

  const saveNotes = notes.handleSubmit((values) => {
    setNotesError(null)
    const zoomFields = parsedSummary && {
      zoom_summary_raw: parsedSummary.summary,
      ...(parsedSummary.meetingUuid !== null && { zoom_meeting_uuid: parsedSummary.meetingUuid }),
    }
    update.mutate({ ...notesToRequest(values), ...zoomFields }, {
      onSuccess: (saved) => {
        notes.reset(notesFromSession(saved))
        setParsedSummary(null)
        setZoomOpen(false)
        setSavedPart('notes')
      },
      onError: (error) => setNotesError(applyServerErrors(error, notes.setError, notesFields)),
    })
  })

  return (
    <div>
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-3">
            Session —{' '}
            {student ? (
              <Link to={`/students/${student.id}`} className="hover:text-blue-600 dark:hover:text-blue-400">
                {student.first_name} {student.last_name}
              </Link>
            ) : (
              'Unknown student'
            )}
            {session.is_no_show && (
              <span className="rounded-full bg-red-100 px-3 py-1 text-sm font-medium text-red-700 dark:bg-red-900/50 dark:text-red-300">No show</span>
            )}
          </span>
        }
        backTo="/sessions"
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-1">
          <section className="card p-6">
            <h2 className="mb-4 font-semibold">Details</h2>
            <form onSubmit={saveDetails} noValidate className="space-y-4">
              {detailsError && <ErrorMessage>{detailsError}</ErrorMessage>}
              <DetailsFields form={details} students={students} compact />
              <p className="text-xs text-gray-400">Duration: {session.minutes} min</p>
              <button type="submit" disabled={update.isPending || !details.formState.isDirty} className={`${buttonPrimary} w-full`}>
                Save changes
              </button>
              {savedPart === 'details' && !details.formState.isDirty && (
                <p role="status" className="text-center text-xs text-green-600 dark:text-green-400">
                  Saved
                </p>
              )}
            </form>
            {session.calendar_html_link && (
              <a href={session.calendar_html_link} target="_blank" rel="noopener noreferrer" className="mt-4 block text-xs text-blue-600 hover:underline dark:text-blue-400">
                Open in Google Calendar
              </a>
            )}
          </section>
        </div>

        <section className="card p-6 lg:col-span-2">
          <h2 className="mb-4 font-semibold">Session notes</h2>
          {session.zoom_outcome !== null && (
            <p className="-mt-2 mb-4 text-xs text-blue-700 dark:text-blue-300">
              {zoomOutcomeLabel(session.zoom_outcome)}
              {session.zoom_outcome_at && ` on ${formatDate(session.zoom_outcome_at)}`}.
            </p>
          )}
          {remove.isError && <ErrorMessage>Couldn't clear the session. Please try again.</ErrorMessage>}
          {session.is_no_show ? (
            <div className="space-y-4">
              <p className="text-sm text-gray-400 italic">No notes recorded. The student did not attend.</p>
              <button type="button" onClick={clearSession} disabled={remove.isPending} className={buttonSecondary}>
                Clear session
              </button>
            </div>
          ) : (
            <form onSubmit={saveNotes} noValidate className="space-y-4">
              {notesError && <ErrorMessage>{notesError}</ErrorMessage>}
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => setZoomOpen((open) => !open)} aria-expanded={zoomOpen} className={buttonSecondary}>
                  {zoomOpen ? 'Hide Zoom summary' : 'Fill from Zoom summary'}
                </button>
                <button type="button" onClick={clearSession} disabled={remove.isPending} className={buttonSecondary}>
                  Clear notes
                </button>
              </div>
              {zoomOpen && <ZoomSummaryPanel sessionId={session.id} initialSummary={session.zoom_summary_raw ?? ''} onParsed={fillFromZoom} />}
              <NotesFields form={notes} />
              <div className="flex flex-wrap items-center gap-3">
                <button type="submit" disabled={update.isPending || !notes.formState.isDirty} className={buttonPrimary}>
                  Save notes
                </button>
                {notes.formState.isDirty && (
                  <button
                    type="button"
                    onClick={() => {
                      notes.reset()
                      setParsedSummary(null)
                    }}
                    className="text-sm text-gray-500 hover:underline dark:text-gray-400"
                  >
                    Discard changes
                  </button>
                )}
              </div>
              {savedPart === 'notes' && !notes.formState.isDirty && (
                <p role="status" className="text-xs text-green-600 dark:text-green-400">
                  Saved
                </p>
              )}
            </form>
          )}
        </section>
      </div>
    </div>
  )
}
