import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import { ErrorMessage, Loading, PageHeader, StatusBadge, buttonPrimary, buttonSecondary } from '../../components/ui'
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
      <PageHeader title="Students">
        <Link to="/students/new" className={buttonPrimary}>
          Add student
        </Link>
      </PageHeader>

      <form role="search" onSubmit={handleSearch} className="mb-6 flex flex-wrap gap-2">
        <label htmlFor="student-search" className="sr-only">
          Search students
        </label>
        <input
          id="student-search"
          type="search"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Search by name…"
          className="input sm:!w-64"
        />
        <button type="submit" className={buttonPrimary}>
          Search
        </button>
        {q && (
          <button type="button" onClick={clear} className={buttonSecondary}>
            Clear
          </button>
        )}
      </form>

      {students.isPending && <Loading>Loading students…</Loading>}
      {students.isError && <ErrorMessage>Couldn't load students: {students.error.message}</ErrorMessage>}

      {students.data && (
        <>
          {q && (
            <p className="mb-3 text-sm text-gray-500 dark:text-gray-400">
              {students.data.length} result{students.data.length === 1 ? '' : 's'} for “{q}”
            </p>
          )}
          <div className="card overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600 dark:text-gray-300">
              <thead className="bg-gray-50 text-xs tracking-wider text-gray-500 uppercase dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <th className="px-6 py-3">Name</th>
                  <th className="px-6 py-3">Level</th>
                  <th className="px-6 py-3">Hourly rate</th>
                  <th className="px-6 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {students.data.map((student) => (
                  <tr key={student.id} className="border-b border-gray-200 last:border-0 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/50">
                    <td className="px-6 py-4">
                      <Link to={`/students/${student.id}`} className="font-medium text-gray-900 hover:text-blue-600 dark:text-white dark:hover:text-blue-400">
                        {student.first_name} {student.last_name}
                      </Link>
                    </td>
                    <td className="px-6 py-4">{student.level || '—'}</td>
                    <td className="px-6 py-4">{student.hourly_rate ? formatMoney(student.hourly_rate) : '—'}</td>
                    <td className="px-6 py-4">
                      <StatusBadge active={student.is_active} />
                    </td>
                  </tr>
                ))}
                {students.data.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-6 py-8 text-center text-gray-400">
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
