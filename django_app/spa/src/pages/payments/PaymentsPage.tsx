import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import { ErrorMessage, Loading, PageHeader, buttonPrimary, buttonSecondary } from '../../components/ui'
import { formatDate, formatMoney } from '../../format'
import { PAYMENTS_PAGE_SIZE, usePayments } from '../payees/queries'

export function PaymentsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const q = searchParams.get('q') ?? ''
  const page = Math.max(1, Number(searchParams.get('page')) || 1)
  const [draft, setDraft] = useState(q)
  const payments = usePayments(q, page)

  function go(changes: { q?: string; page?: number }) {
    const next = new URLSearchParams(searchParams)
    if (changes.q !== undefined) {
      if (changes.q) next.set('q', changes.q)
      else next.delete('q')
      next.delete('page')
    }
    if (changes.page !== undefined) {
      if (changes.page > 1) next.set('page', String(changes.page))
      else next.delete('page')
    }
    setSearchParams(next)
  }

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    go({ q: draft.trim() })
  }

  const count = payments.data?.count ?? 0
  const totalPages = Math.max(1, Math.ceil(count / PAYMENTS_PAGE_SIZE))
  const rows = payments.data?.results ?? []
  const first = (page - 1) * PAYMENTS_PAGE_SIZE + 1

  return (
    <div>
      <PageHeader title="Payments">
        <Link to="/payments/new" className={buttonPrimary}>
          Add payment
        </Link>
      </PageHeader>

      <form role="search" onSubmit={handleSearch} className="mb-6 flex flex-wrap gap-2">
        <label htmlFor="payment-search" className="sr-only">
          Search payments
        </label>
        <input
          id="payment-search"
          type="search"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Search by payee name…"
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
              go({ q: '' })
            }}
            className={buttonSecondary}
          >
            Clear
          </button>
        )}
      </form>

      {payments.isPending && <Loading>Loading payments…</Loading>}
      {payments.isError && <ErrorMessage>Couldn't load payments: {payments.error.message}</ErrorMessage>}

      {payments.data && (
        <>
          <div className="card overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600 dark:text-gray-300">
              <thead className="bg-gray-50 text-xs tracking-wider text-gray-500 uppercase dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <th className="px-6 py-3">Payee</th>
                  <th className="px-6 py-3">Date</th>
                  <th className="px-6 py-3 text-right">Amount</th>
                  <th className="px-6 py-3">Reference</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((payment) => (
                  <tr key={payment.id} className="border-b border-gray-200 last:border-0 dark:border-gray-700">
                    <td className="px-6 py-4">
                      <Link to={`/payees/${payment.payee}`} className="font-medium text-gray-900 hover:text-blue-600 dark:text-white dark:hover:text-blue-400">
                        {payment.payee_name}
                      </Link>
                    </td>
                    <td className="px-6 py-4">{formatDate(payment.payment_date)}</td>
                    <td className="px-6 py-4 text-right font-medium text-green-600 dark:text-green-400">+{formatMoney(Number(payment.amount))}</td>
                    <td className="px-6 py-4">{payment.payment_reference || '—'}</td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-6 py-8 text-center text-gray-400">
                      {q ? 'No payments match that search' : 'No payments yet'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {count > 0 && (
            <nav aria-label="Pages" className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Showing {first}–{first + rows.length - 1} of {count}
              </p>
              {totalPages > 1 && (
                <div className="flex items-center gap-2">
                  <button type="button" disabled={page <= 1} onClick={() => go({ page: page - 1 })} className={buttonSecondary}>
                    Previous
                  </button>
                  <span className="px-2 text-sm text-gray-500 dark:text-gray-400">
                    Page {page} of {totalPages}
                  </span>
                  <button type="button" disabled={page >= totalPages} onClick={() => go({ page: page + 1 })} className={buttonSecondary}>
                    Next
                  </button>
                </div>
              )}
            </nav>
          )}
        </>
      )}
    </div>
  )
}
