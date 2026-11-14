import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import { ErrorMessage, Loading, PageHeader, StatusBadge, buttonPrimary } from '../../components/ui'
import { SearchForm } from '../../components/SearchForm'
import { formatMoney } from '../../format'
import { useStudents } from './queries'

export function StudentsPage() {
  // The search lives in the URL (?q=…), so it survives a reload and the back button.
  const [searchParams, setSearchParams] = useSearchParams()
  const q = searchParams.get('q') ?? ''
  const [draft, setDraft] = useState(q)
  const students = useStudents(q)

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSearchParams(draft.trim() ? { q: draft.trim() } : {})
  }

  function clear() {
    setDraft('')
    setSearchParams({})
  }

  return (
    <div>
      <PageHeader title="Students" description="Everyone you teach, with their level and hourly rate.">
        <Link to="/students/new" className={buttonPrimary}>
          Add student
        </Link>
      </PageHeader>

      <SearchForm
        id="student-search"
        label="Search students"
        placeholder="Search by name…"
        value={draft}
        onChange={setDraft}
        onSubmit={handleSearch}
        onClear={q ? clear : undefined}
        className="mb-6"
      />

      {students.isPending && <Loading>Loading students…</Loading>}
      {students.isError && <ErrorMessage>Couldn't load students: {students.error.message}</ErrorMessage>}

      {students.data && (
        <>
          {q && (
            <p className="mb-3 text-sm muted">
              {students.data.length} result{students.data.length === 1 ? '' : 's'} for “{q}”
            </p>
          )}
          <div className="card overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Level</th>
                  <th>Hourly rate</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {students.data.map((student) => (
                  <tr key={student.id}>
                    <td>
                      <Link to={`/students/${student.id}`} className="font-medium text-slate-900 hover:text-blue-600 dark:text-white dark:hover:text-blue-400">
                        {student.first_name} {student.last_name}
                      </Link>
                    </td>
                    <td>{student.level || '—'}</td>
                    <td>{student.hourly_rate ? formatMoney(student.hourly_rate) : '—'}</td>
                    <td>
                      <StatusBadge active={student.is_active} />
                    </td>
                  </tr>
                ))}
                {students.data.length === 0 && (
                  <tr>
                    <td colSpan={4} className="empty">
                      {q ? 'No students match that search' : 'No students yet'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
