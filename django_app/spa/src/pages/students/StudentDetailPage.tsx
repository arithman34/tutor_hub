import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate, useParams } from 'react-router'

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
        <section className="card p-6 lg:col-span-1">
          <h2 className="mb-4 font-semibold">Student info</h2>
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

          <div className="mt-4 space-y-2 border-t border-gray-200 pt-4 dark:border-gray-700">
            {(toggle.isError || remove.isError) && <ErrorMessage>That didn't work. Please try again.</ErrorMessage>}
            <button type="button" onClick={() => toggle.mutate()} disabled={toggle.isPending} className={`${buttonSecondary} w-full`}>
              {student.is_active ? 'Deactivate' : 'Activate'}
            </button>
            <button type="button" onClick={handleDelete} disabled={remove.isPending} className={`${buttonDanger} w-full`}>
              Delete student
            </button>
          </div>
        </section>

        <section className="card lg:col-span-2">
          <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
            <h2 className="font-semibold">Recent sessions</h2>
            {/* Logging sessions is still a classic page; a full-page link until it moves. */}
            <a href={`/sessions/new?student_id=${student.id}`} className={`${buttonPrimary} py-1.5`}>
              Log session
            </a>
          </div>
          {sessions.isPending && <div className="p-6"><Loading>Loading sessions…</Loading></div>}
          {sessions.isError && <div className="p-6"><ErrorMessage>Couldn't load sessions.</ErrorMessage></div>}
          {sessions.data && (
            <table className="w-full text-left text-sm text-gray-600 dark:text-gray-300">
              <thead className="bg-gray-50 text-xs tracking-wider text-gray-500 uppercase dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <th className="px-6 py-3">Date</th>
                  <th className="px-6 py-3">Duration</th>
                  <th className="px-6 py-3">
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sessions.data.results.map((session) => (
                  <tr key={session.id} className="border-b border-gray-200 last:border-0 dark:border-gray-700">
                    <td className="px-6 py-4">{formatDate(session.session_date)}</td>
                    <td className="px-6 py-4">{session.is_no_show ? 'No-show' : `${session.minutes} min`}</td>
                    <td className="px-6 py-4 text-right">
                      <a href={`/sessions/${session.id}`} className="text-xs text-blue-600 hover:underline dark:text-blue-400">
                        View
                      </a>
                    </td>
                  </tr>
                ))}
                {sessions.data.results.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-6 py-8 text-center text-gray-400">
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
