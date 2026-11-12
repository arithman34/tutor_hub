import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import { ErrorMessage, Loading, PageHeader, buttonPrimary, buttonSecondary } from '../../components/ui'
import { balanceTone, formatBalance } from '../../format'
import { usePayees } from './queries'

export function PayeesPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const q = searchParams.get('q') ?? ''
  const [draft, setDraft] = useState(q)
  const payees = usePayees(q)

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSearchParams(draft.trim() ? { q: draft.trim() } : {})
  }

  return (
    <div>
      <PageHeader title="Payees">
        <Link to="/payees/new" className={buttonPrimary}>
          Add payee
        </Link>
      </PageHeader>

      <form role="search" onSubmit={handleSearch} className="mb-6 flex flex-wrap gap-2">
        <label htmlFor="payee-search" className="sr-only">
          Search payees
        </label>
        <input
          id="payee-search"
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
          <button
            type="button"
            onClick={() => {
              setDraft('')
              setSearchParams({})
            }}
            className={buttonSecondary}
          >
            Clear
          </button>
        )}
      </form>

      {payees.isPending && <Loading>Loading payees…</Loading>}
      {payees.isError && <ErrorMessage>Couldn't load payees: {payees.error.message}</ErrorMessage>}

      {payees.data && (
        <div className="card overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-600 dark:text-gray-300">
            <thead className="bg-gray-50 text-xs tracking-wider text-gray-500 uppercase dark:bg-gray-700 dark:text-gray-400">
              <tr>
                <th className="px-6 py-3">Name</th>
                <th className="px-6 py-3">Email</th>
                <th className="px-6 py-3">Phone</th>
                <th className="px-6 py-3">Bank reference</th>
                <th className="px-6 py-3">Students</th>
                <th className="px-6 py-3 text-right">Balance</th>
              </tr>
            </thead>
            <tbody>
              {payees.data.map((payee) => (
                <tr key={payee.id} className="border-b border-gray-200 last:border-0 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/50">
                  <td className="px-6 py-4">
                    <Link to={`/payees/${payee.id}`} className="font-medium text-gray-900 hover:text-blue-600 dark:text-white dark:hover:text-blue-400">
                      {payee.first_name} {payee.last_name}
                    </Link>
                  </td>
                  <td className="px-6 py-4">{payee.email || '—'}</td>
                  <td className="px-6 py-4">{payee.phone_number || '—'}</td>
                  <td className="px-6 py-4 font-mono text-xs">{payee.bank_reference_pattern || '—'}</td>
                  <td className="px-6 py-4">{payee.student_count}</td>
                  <td className={`px-6 py-4 text-right font-medium ${balanceTone(payee.balance)}`}>{formatBalance(payee.balance)}</td>
                </tr>
              ))}
              {payees.data.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-gray-400">
                    {q ? 'No payees match that search' : 'No payees yet'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
