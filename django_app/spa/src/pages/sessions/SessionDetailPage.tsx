import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router'

import { ApiError } from '../../api/client'
import type { Session, Student, ZoomNotes } from '../../api/types'
import { applyServerErrors } from '../../components/formHelpers'
import { ErrorMessage, Loading, PageHeader, buttonDanger, buttonPrimary, buttonSecondary } from '../../components/ui'
import { useStudents } from '../students/queries'
import { useDeleteSession, useSession, useUpdateSession } from './queries'
import { DetailsFields, NotesFields } from './SessionFields'
import { ZoomSummaryPanel } from './ZoomSummaryPanel'
import {
  detailsFields,
  detailsFromSession,
  detailsSchema,
  detailsToRequest,
  notesFields,
  notesFromSession,
  notesSchema,
  emptyNotes,
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
  const noteValues = useWatch({ control: notes.control })
  const hasNotes = Object.values(noteValues).some((value) => value?.trim())
  const [zoomOpen, setZoomOpen] = useState(false)
  // A summary parsed on this page (and the Zoom meeting it was fetched from,
  // if it was), to save along with the notes it produced.
  const [parsedSummary, setParsedSummary] = useState<{ summary: string; meetingUuid: string | null } | null>(null)

  // Empties the form only; nothing changes until "Save notes".
  function clearNotes() {
    for (const field of Object.keys(emptyNotes) as (keyof NotesValues)[]) {
      notes.setValue(field, '', { shouldDirty: true })
    }
    setSavedPart(null)
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

  function handleDelete() {
    if (!window.confirm('Delete this session? This cannot be undone.')) return
    remove.mutate(undefined, { onSuccess: () => navigate('/sessions', { replace: true }) })
  }

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

          <section className="rounded-xl border border-red-200 bg-white p-4 dark:border-red-900 dark:bg-gray-800">
            <p className="mb-3 text-sm text-gray-500 dark:text-gray-400">Deleting a session is permanent and cannot be undone.</p>
            {remove.isError && <ErrorMessage>Couldn't delete the session. Please try again.</ErrorMessage>}
            <button type="button" onClick={handleDelete} disabled={remove.isPending} className={`${buttonDanger} w-full`}>
              Delete session
            </button>
          </section>
        </div>

        <section className="card p-6 lg:col-span-2">
          <h2 className="mb-4 font-semibold">Session notes</h2>
          {session.is_no_show ? (
            <p className="text-sm text-gray-400 italic">No notes recorded. The student did not attend.</p>
          ) : (
            <form onSubmit={saveNotes} noValidate className="space-y-4">
              {notesError && <ErrorMessage>{notesError}</ErrorMessage>}
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => setZoomOpen((open) => !open)} aria-expanded={zoomOpen} className={buttonSecondary}>
                  {zoomOpen ? 'Hide Zoom summary' : 'Fill from Zoom summary'}
                </button>
                <button type="button" onClick={clearNotes} disabled={!hasNotes} className={buttonSecondary}>
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
