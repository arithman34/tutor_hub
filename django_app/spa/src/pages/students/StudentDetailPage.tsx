import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router'

import { ApiError } from '../../api/client'
import type { Student } from '../../api/types'
import { applyServerErrors } from '../../components/formHelpers'
import { ErrorMessage, Loading, PageHeader, StatusBadge, buttonDanger, buttonPrimary, buttonSecondary } from '../../components/ui'
import { formatDate } from '../../format'
import { StudentFields } from './StudentFields'
import { useDeleteStudent, useRecentSessions, useStudent, useToggleActive, useUpdateStudent } from './queries'
import { fromStudent, studentFormFields, studentFormSchema, toRequest, type StudentFormValues } from './studentForm'

export function StudentDetailPage() {
  // The :studentId part of the URL (see App.tsx).
  const { studentId = '' } = useParams()
  const student = useStudent(studentId)

  if (student.isPending) return <Loading>Loading student…</Loading>
  if (student.isError) {
    const missing = student.error instanceof ApiError && student.error.status === 404
    return (
      <div>
        <PageHeader title="Student" backTo="/students" />
        <ErrorMessage>{missing ? 'That student doesn’t exist, or was deleted.' : `Couldn't load the student: ${student.error.message}`}</ErrorMessage>
      </div>
    )
  }

  // Keyed by id, so moving to another student starts with a fresh form.
  return <StudentDetail key={student.data.id} student={student.data} />
}

function StudentDetail({ student }: { student: Student }) {
  const navigate = useNavigate()
  const update = useUpdateStudent(student.id)
  const toggle = useToggleActive(student.id)
  const remove = useDeleteStudent(student.id)
  const sessions = useRecentSessions(student.id)
  const [formError, setFormError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const form = useForm<StudentFormValues>({ resolver: zodResolver(studentFormSchema), defaultValues: fromStudent(student) })

  const onSubmit = form.handleSubmit((values) => {
    setFormError(null)
    setSaved(false)
    update.mutate(toRequest(values), {
      onSuccess: (updated) => {
        // Make the saved values the new baseline, so the form isn't "dirty".
        form.reset(fromStudent(updated))
        setSaved(true)
      },
      onError: (error) => setFormError(applyServerErrors(error, form.setError, studentFormFields)),
    })
  })

  function handleDelete() {
    if (!window.confirm(`Delete ${student.first_name} ${student.last_name}? This also deletes their sessions and can't be undone.`)) return
    remove.mutate(undefined, { onSuccess: () => navigate('/students', { replace: true }) })
  }

  return (
    <div>
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            {student.first_name} {student.last_name} <StatusBadge active={student.is_active} />
          </span>
        }
        backTo="/students"
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="card lg:col-span-1">
          <div className="card-header">
            <div className="min-w-0">
              <h2 className="section-title">Student info</h2>
            </div>
          </div>
          <div className="p-5">
          <form onSubmit={onSubmit} noValidate className="space-y-4">
            {formError && <ErrorMessage>{formError}</ErrorMessage>}
            <StudentFields form={form} savedDocId={student.google_doc_id ?? null} />
            <button type="submit" disabled={update.isPending || !form.formState.isDirty} className={`${buttonPrimary} w-full`}>
              {update.isPending ? 'Saving…' : 'Save changes'}
            </button>
            {saved && !form.formState.isDirty && (
              <p role="status" className="text-center text-xs text-green-600 dark:text-green-400">
                Saved
              </p>
            )}
          </form>

          <div className="mt-4 space-y-2 border-t border-slate-200 pt-4 dark:border-white/5">
            {(toggle.isError || remove.isError) && <ErrorMessage>That didn't work. Please try again.</ErrorMessage>}
            <button type="button" onClick={() => toggle.mutate()} disabled={toggle.isPending} className={`${buttonSecondary} w-full`}>
              {student.is_active ? 'Deactivate' : 'Activate'}
            </button>
            <button type="button" onClick={handleDelete} disabled={remove.isPending} className={`${buttonDanger} w-full`}>
              Delete student
            </button>
          </div>
          </div>
        </section>

        <section className="card lg:col-span-2">
          <div className="card-header">
            <h2 className="section-title">Recent sessions</h2>
            <Link to={`/sessions/new?student_id=${student.id}`} className={`${buttonPrimary} py-1.5`}>
              Log session
            </Link>
          </div>
          {sessions.isPending && <div className="p-6"><Loading>Loading sessions…</Loading></div>}
          {sessions.isError && <div className="p-6"><ErrorMessage>Couldn't load sessions.</ErrorMessage></div>}
          {sessions.data && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Duration</th>
                  <th>
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sessions.data.results.map((session) => (
                  <tr key={session.id}>
                    <td>{formatDate(session.session_date)}</td>
                    <td>{session.is_no_show ? 'No-show' : `${session.minutes} min`}</td>
                    <td className="text-right">
                      <Link to={`/sessions/${session.id}`} className="text-xs text-blue-600 hover:underline dark:text-blue-400">
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
                {sessions.data.results.length === 0 && (
                  <tr>
                    <td colSpan={3} className="empty">
                      No sessions yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  )
}
