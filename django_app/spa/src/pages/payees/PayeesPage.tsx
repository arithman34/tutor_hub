import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import { ErrorMessage, Loading, PageHeader, buttonPrimary } from '../../components/ui'
import { SearchForm } from '../../components/SearchForm'
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
      <PageHeader title="Payees" description="The people who pay for lessons, and what each one owes.">
        <Link to="/payees/new" className={buttonPrimary}>
          Add payee
        </Link>
      </PageHeader>

      <SearchForm
        id="payee-search"
        label="Search payees"
        placeholder="Search by name…"
        value={draft}
        onChange={setDraft}
        onSubmit={handleSearch}
        onClear={q ? () => {
              setDraft('')
              setSearchParams({})
            } : undefined}
        className="mb-6"
      />

      {payees.isPending && <Loading>Loading payees…</Loading>}
      {payees.isError && <ErrorMessage>Couldn't load payees: {payees.error.message}</ErrorMessage>}

      {payees.data && (
        <div className="card overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Bank reference</th>
                <th>Students</th>
                <th className="text-right">Balance</th>
              </tr>
            </thead>
            <tbody>
              {payees.data.map((payee) => (
                <tr key={payee.id}>
                  <td>
                    <Link to={`/payees/${payee.id}`} className="font-medium text-slate-900 hover:text-blue-600 dark:text-white dark:hover:text-blue-400">
                      {payee.first_name} {payee.last_name}
                    </Link>
                  </td>
                  <td>{payee.email || '—'}</td>
                  <td>{payee.phone_number || '—'}</td>
                  <td className="font-mono text-xs">{payee.bank_reference_pattern || '—'}</td>
                  <td>{payee.student_count}</td>
                  <td className={`px-6 py-4 text-right font-medium ${balanceTone(payee.balance)}`}>{formatBalance(payee.balance)}</td>
                </tr>
              ))}
              {payees.data.length === 0 && (
                <tr>
                  <td colSpan={6} className="empty">
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
